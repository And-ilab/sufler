import ast
import importlib
import json
import os
import sys
from pathlib import Path

from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sufler.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Group  # noqa: E402
from django.test import Client, TestCase  # noqa: E402

from auth.roles import ROLES_BY_CODE  # noqa: E402
from hub.models import DialogScenario  # noqa: E402
from hub.scenario_catalog import (  # noqa: E402
    ALL_SCENARIOS,
    DRAFT_SCENARIOS,
    REFERENCE_SCENARIOS,
)
from hub.scenario_service import upsert_from_catalog  # noqa: E402
from hub.scenario_service import attach_semantic_expansion  # noqa: E402
from orchestrator.scenario_engine import (  # noqa: E402
    _match_start,
    _score,
    _semantic_profile,
    _topic_boost,
    classify_turn,
    clear_scenario_session,
    enter_scenario,
)
from orchestrator.sufler import suggest  # noqa: E402


class DialogScenarioCatalogTest(TestCase):
    def test_catalog_has_ten_reference_and_fifty_total(self):
        self.assertEqual(len(REFERENCE_SCENARIOS), 10)
        self.assertGreaterEqual(len(ALL_SCENARIOS), 50)
        codes = [item["code"] for item in ALL_SCENARIOS]
        self.assertEqual(len(codes), len(set(codes)))

    def test_seed_upserts_production_graphs(self):
        for payload in REFERENCE_SCENARIOS:
            upsert_from_catalog(payload, username="test")
        self.assertEqual(
            DialogScenario.objects.filter(status=DialogScenario.STATUS_PRODUCTION).count(),
            10,
        )
        item = DialogScenario.objects.get(code="CC-SCR-005")
        nodes = item.current_version.graph["nodes"]
        self.assertTrue(any(node["id"] == "card_rf" for node in nodes))

    def test_every_catalog_edge_has_natural_matching_reply(self):
        edges = [
            edge
            for scenario in ALL_SCENARIOS
            for node in scenario["graph"]["nodes"]
            for edge in node.get("edges", [])
        ]
        self.assertEqual(len(edges), 118)
        for edge in edges:
            with self.subTest(label=edge["label"]):
                reply = edge.get("reply", "").strip()
                self.assertTrue(reply)
                self.assertNotIn("Выбираю вариант", reply)
                self.assertGreater(_score(reply, edge["keywords"], []), 0)

    def test_all_linear_drafts_define_explicit_clarify_replies(self):
        catalog_path = BACKEND_ROOT / "hub" / "scenario_catalog.py"
        tree = ast.parse(catalog_path.read_text(encoding="utf-8"))
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "linear_draft"
        ]
        self.assertEqual(len(calls), 40)
        self.assertTrue(
            all(
                any(keyword.arg == "reply" for keyword in call.keywords)
                for call in calls
            )
        )

        self.assertEqual(len(DRAFT_SCENARIOS), 40)
        for scenario in DRAFT_SCENARIOS:
            start = scenario["graph"]["nodes"][0]
            reply = start["edges"][0]["reply"]
            with self.subTest(code=scenario["code"]):
                self.assertNotEqual(reply.casefold(), start["examples"][0].casefold())
        by_code = {scenario["code"]: scenario for scenario in DRAFT_SCENARIOS}
        self.assertEqual(
            by_code["CC-SCR-012"]["graph"]["nodes"][0]["edges"][0]["reply"],
            "Карту ещё не блокировал, после утери нужен перевыпуск",
        )
        self.assertEqual(
            by_code["CC-SCR-015"]["graph"]["nodes"][0]["edges"][0]["reply"],
            "Нужен лимит на оплату в интернете",
        )

    def test_reply_backfill_preserves_manual_edge_fields(self):
        payload = REFERENCE_SCENARIOS[0]
        item = upsert_from_catalog(payload, username="test")
        graph = item.current_version.graph
        edges = graph["nodes"][0]["edges"]
        edges[0].pop("reply")
        edges[0]["label"] = "Пользовательская подпись"
        edges[0]["custom"] = {"keep": True}
        edges[1]["reply"] = "Моя ручная реплика"
        item.current_version.graph = graph
        item.current_version.save(update_fields=["graph"])

        migration = importlib.import_module(
            "hub.migrations.0016_backfill_scenario_edge_replies"
        )
        from django.apps import apps

        migration.backfill_scenario_edge_replies(apps, None)

        item.current_version.refresh_from_db()
        saved_edges = item.current_version.graph["nodes"][0]["edges"]
        self.assertEqual(saved_edges[0]["reply"], "Мне нужна карточка к счёту")
        self.assertEqual(saved_edges[0]["label"], "Пользовательская подпись")
        self.assertEqual(saved_edges[0]["custom"], {"keep": True})
        self.assertEqual(saved_edges[1]["reply"], "Моя ручная реплика")


class ScenarioEngineGatingTest(TestCase):
    def setUp(self):
        for payload in REFERENCE_SCENARIOS:
            upsert_from_catalog(payload, username="test")
        env = patch.dict(
            os.environ,
            {
                "SUFLER_ALLOW_UNGROUNDED": "0",
                "MODEL_GATEWAY_MODE": "stub",
            },
            clear=False,
        )
        env.start()
        self.addCleanup(env.stop)

    def test_greeting_skips_hints(self):
        self.assertEqual(classify_turn("здравствуйте"), "no_hint.greeting")
        result = suggest("здравствуйте")
        self.assertEqual(result["blocked_reason"], "no_hint_needed")
        self.assertEqual(result["hints"], [])
        self.assertIsNone(result["scenario"])

    def test_thanks_skips_hints(self):
        result = suggest("спасибо")
        self.assertEqual(result["blocked_reason"], "no_hint_needed")
        self.assertEqual(result["hints"], [])

    def test_incomplete_final_fragment_skips_hints(self):
        for replica in ("Терминал не.", "Хочу взять деньги в."):
            with self.subTest(replica=replica):
                result = suggest(replica, session_id=f"incomplete-{replica}")
                self.assertEqual(result["blocked_reason"], "no_hint_needed")
                self.assertEqual(result["hints"], [])
                self.assertIsNone(result["scenario"])

    def test_identity_and_personal_facts_skip_hints(self):
        for index, replica in enumerate(
            ("Меня зовут Никита", "Я Никита", "Мне 14 лет", "У меня вопрос"),
            start=1,
        ):
            with self.subTest(replica=replica):
                result = suggest(replica, session_id=f"identity-{index}")
                self.assertEqual(result["blocked_reason"], "no_hint_needed")
                self.assertEqual(result["hints"], [])
                self.assertIsNone(result["scenario"])

    def test_short_ack_does_not_start_scenario_on_clean_session(self):
        for replica in ("да", "нет", "ну"):
            with self.subTest(replica=replica):
                result = suggest(replica, session_id=f"ack-{replica}")
                self.assertEqual(result["blocked_reason"], "no_hint_needed")
                self.assertIsNone(result["scenario"])

    def test_unrelated_turn_does_not_repeat_active_scenario_hint(self):
        started = suggest(
            "надо отправить деньги в россию",
            session_id="call-not-sticky",
        )
        self.assertEqual(started["scenario"]["code"], "CC-SCR-005")
        unrelated = suggest("Меня зовут Никита", session_id="call-not-sticky")
        self.assertEqual(unrelated["blocked_reason"], "no_hint_needed")
        self.assertEqual(unrelated["hints"], [])
        self.assertIsNone(unrelated["scenario"])

    def test_session_keys_are_isolated(self):
        suggest("надо отправить деньги в россию", session_id="isolated-a")
        result = suggest("Меня зовут Никита", session_id="isolated-b")
        self.assertIsNone(result["scenario"])
        self.assertEqual(result["blocked_reason"], "no_hint_needed")

    def test_generic_card_and_phone_questions_do_not_start_rf_scenario(self):
        for index, replica in enumerate(
            (
                "как оформить карту на моё имя",
                "как перевести деньги по номеру телефона",
                "когда видна комиссия перевода по номеру телефона",
            ),
            start=1,
        ):
            with self.subTest(replica=replica):
                result = suggest(replica, session_id=f"generic-payment-{index}")
                self.assertIsNone(result["scenario"])

    def test_semantic_match_starts_clear_scenario_paraphrase(self):
        scenarios = list(DialogScenario.objects.all())
        vectors = {
            scenario.pk: (
                [1.0, 0.0]
                if scenario.code == "CC-SCR-002"
                else [0.0, 1.0]
            )
            for scenario in scenarios
        }
        signature = ((1, "test"),)

        with (
            patch(
                "orchestrator.scenario_engine._semantic_signature",
                return_value=signature,
            ),
            patch(
                "orchestrator.scenario_engine._semantic_cache_signature",
                signature,
            ),
            patch(
                "orchestrator.scenario_engine._semantic_cache_backend",
                "http",
            ),
            patch(
                "orchestrator.scenario_engine._semantic_cache_vectors",
                vectors,
            ),
            patch(
                "core.embeddings.embed_query_with_backend",
                return_value=([1.0, 0.0], "http"),
            ),
        ):
            matched = _match_start(
                "Нужно оформить банковский продукт для шестилетнего внука"
            )
        self.assertIsNotNone(matched)
        self.assertEqual(matched[0].code, "CC-SCR-002")

    def test_semantic_match_rejects_ambiguous_candidates(self):
        scenarios = list(DialogScenario.objects.all())
        vectors = {scenario.pk: [0.0, 1.0] for scenario in scenarios}
        by_code = {scenario.code: scenario.pk for scenario in scenarios}
        vectors[by_code["CC-SCR-001"]] = [0.999, 0.04]
        vectors[by_code["CC-SCR-002"]] = [1.0, 0.0]
        signature = ((1, "test"),)

        with (
            patch(
                "orchestrator.scenario_engine._semantic_signature",
                return_value=signature,
            ),
            patch(
                "orchestrator.scenario_engine._semantic_cache_signature",
                signature,
            ),
            patch(
                "orchestrator.scenario_engine._semantic_cache_backend",
                "http",
            ),
            patch(
                "orchestrator.scenario_engine._semantic_cache_vectors",
                vectors,
            ),
            patch(
                "core.embeddings.embed_query_with_backend",
                return_value=([1.0, 0.0], "http"),
            ),
        ):
            matched = _match_start(
                "Нужно оформить банковский продукт несовершеннолетнему"
            )
        self.assertIsNone(matched)

    def test_greeting_with_question_still_matches_scenario(self):
        result = suggest(
            "здравствуйте, надо отправить деньги в россию",
            session_id="call-rf-1",
        )
        self.assertIsNone(result["blocked_reason"])
        self.assertEqual(result["scenario"]["code"], "CC-SCR-005")
        self.assertTrue(result["hints"])

    def test_grandchild_account_spoken_variant_starts_scenario(self):
        result = suggest(
            "Хочу открыть счет, внук ему 6 лет.",
            session_id="call-grandchild-1",
        )
        self.assertEqual(result["scenario"]["code"], "CC-SCR-002")
        self.assertIn("законный представитель", result["hints"][0]["text"])

    def test_question_only_scenario_does_not_repeat_operator_tip(self):
        result = suggest(
            "Мне нужна выписка со счёта для визы",
            session_id="question-only-scenario",
        )
        self.assertEqual(result["scenario"]["code"], "CC-SCR-007")
        self.assertIn("За какой период", result["hints"][0]["text"])
        self.assertEqual(result["hints"][0]["operator_tip"], "")

    def test_transfer_to_rf_walks_card_then_mobile_bank(self):
        first = suggest(
            "надо отправить деньги в россию маме на карту сбера",
            session_id="call-rf-2",
        )
        self.assertEqual(first["scenario"]["code"], "CC-SCR-005")
        second = suggest("на карту сбера", session_id="call-rf-2")
        self.assertIn("карта", " ".join(second["scenario"]["path"]).casefold())
        third = suggest("через мобильный банк", session_id="call-rf-2")
        self.assertIn("М-банкинг", " ".join(third["scenario"]["path"]))
        self.assertIn("интернет-банке", third["hints"][0]["text"].casefold())

    def test_reference_starts_match_all_ten(self):
        cases = [
            ("CC-SCR-001", "сыну 14, можно счёт открыть"),
            ("CC-SCR-002", "внуку шесть, можно счёт открыть"),
            ("CC-SCR-003", "хочу оплачивать покупки телефоном"),
            ("CC-SCR-004", "хочу кредит на машину"),
            ("CC-SCR-005", "надо отправить деньги в россию"),
            ("CC-SCR-006", "пин забыл, картой расплачиваюсь"),
            ("CC-SCR-007", "нужна выписка со счёта для визы"),
            ("CC-SCR-008", "заканчивается срок вклада по стройсбережениям"),
            ("CC-SCR-009", "перечислить деньги на криптобиржу"),
            ("CC-SCR-010", "проверить российские рубли"),
        ]
        for code, replica in cases:
            with self.subTest(code=code):
                result = suggest(replica, session_id=f"start-{code}")
                self.assertEqual(result["scenario"]["code"], code)
                self.assertTrue(result["hints"])

    def test_qu_no_hint_examples_seeded(self):
        from qu.models import QuReferenceExample

        self.assertTrue(
            QuReferenceExample.objects.filter(intent_id="no_hint.greeting").exists()
        )
        suggest(
            "заканчивается срок вклада по стройсбережениям",
            session_id="call-ss-1",
        )
        yes = suggest("да, сумму накопил", session_id="call-ss-1")
        self.assertEqual(yes["scenario"]["code"], "CC-SCR-008")
        self.assertTrue(
            any("накоп" in part.casefold() for part in yes["scenario"]["path"])
        )

    def test_moscow_transfer_starts_rf_scenario(self):
        for index, replica in enumerate(
            (
                "Перевести деньги в Москву?",
                "перевод в питер",
                "кинуть деньги в Санкт-Петербург",
            ),
            start=1,
        ):
            with self.subTest(replica=replica):
                result = suggest(replica, session_id=f"rf-city-{index}")
                self.assertEqual(result["scenario"]["code"], "CC-SCR-005")
                self.assertEqual(result["hints"][0]["source_type"], "scenario")

    def test_ethereum_starts_crypto_scenario_without_example_word(self):
        result = suggest("Хочу перевести эфириум", session_id="crypto-eth")
        self.assertEqual(result["scenario"]["code"], "CC-SCR-009")
        self.assertEqual(result["hints"][0]["source_type"], "scenario")

    def test_minor_wants_card_starts_teen_account_scenario(self):
        result = suggest(
            "Я маленький, хочу оформить карту.",
            session_id="minor-card",
        )
        self.assertEqual(result["scenario"]["code"], "CC-SCR-001")
        self.assertEqual(result["hints"][0]["source_type"], "scenario")

    def test_apple_pay_starts_nfc_not_crypto(self):
        for index, replica in enumerate(
            (
                "хочу оплачивать apple pay",
                "Хочу оплачивать Apple Pay",
                "можно платить айфоном",
            ),
            start=1,
        ):
            with self.subTest(replica=replica):
                result = suggest(replica, session_id=f"apple-pay-{index}")
                self.assertEqual(result["scenario"]["code"], "CC-SCR-003")
                self.assertEqual(result["hints"][0]["source_type"], "scenario")
                self.assertNotEqual(
                    (result.get("suggested_scenario") or {}).get("code"),
                    "CC-SCR-009",
                )

    def test_car_loan_paraphrases_start_scenario(self):
        for index, replica in enumerate(
            (
                "Хочу взять автокредит",
                "кредит на автомобиль",
                "хочу кредит на машину",
            ),
            start=1,
        ):
            with self.subTest(replica=replica):
                result = suggest(replica, session_id=f"car-loan-{index}")
                self.assertEqual(result["scenario"]["code"], "CC-SCR-004")
                self.assertEqual(result["hints"][0]["source_type"], "scenario")

    def test_under_fourteen_age_paraphrase_starts_grandchild_scenario(self):
        result = suggest(
            "ребёнку 12 с половиной лет, хочу открыть счёт",
            session_id="child-age-12",
        )
        self.assertEqual(result["scenario"]["code"], "CC-SCR-002")

    def test_off_script_reply_leaves_scenario_instead_of_repeating_step(self):
        started = suggest(
            "хочу взять автокредит",
            session_id="car-off-script",
        )
        self.assertEqual(started["scenario"]["code"], "CC-SCR-004")
        partner = suggest(
            "Покупаю автомобиль у партнёра банка",
            session_id="car-off-script",
        )
        self.assertIn("партнёр", " ".join(partner["scenario"]["path"]).casefold())
        declined = suggest("Нет, не оформляем.", session_id="car-off-script")
        self.assertIsNone(declined["scenario"])
        self.assertFalse(
            any(hint.get("source_type") == "scenario" for hint in declined["hints"])
        )
        suggested = declined.get("suggested_scenario")
        self.assertIsNotNone(suggested)
        self.assertEqual(suggested["code"], "CC-SCR-004")

    def test_explicit_no_partner_still_takes_regular_loan_branch(self):
        suggest("хочу взять автокредит", session_id="car-no-partner")
        suggest("Покупаю новый автомобиль в салоне", session_id="car-no-partner")
        regular = suggest(
            "Нет, продавец не партнёр, нужен обычный кредит",
            session_id="car-no-partner",
        )
        self.assertEqual(regular["scenario"]["code"], "CC-SCR-004")
        self.assertTrue(
            any("приобретен" in part.casefold() for part in regular["scenario"]["path"])
        )
        self.assertEqual(regular["hints"][0]["source_type"], "scenario")

    def test_mid_scenario_question_does_not_repeat_scenario_hint(self):
        started = suggest(
            "хочу взять автокредит",
            session_id="car-no-repeat",
        )
        self.assertEqual(started["scenario"]["code"], "CC-SCR-004")
        mid = suggest(
            "Скольки лет действует льготный кредит?",
            session_id="car-no-repeat",
        )
        self.assertIsNone(mid["scenario"])
        self.assertFalse(
            any(hint.get("source_type") == "scenario" for hint in mid["hints"])
        )

    def test_neither_option_takes_fallback_branch(self):
        started = suggest(
            "сыну 14, можно счёт открыть",
            session_id="neither-card",
        )
        self.assertEqual(started["scenario"]["code"], "CC-SCR-001")
        other = suggest("ни то ни другое", session_id="neither-card")
        self.assertEqual(other["scenario"]["code"], "CC-SCR-001")
        self.assertTrue(
            any("друг" in part.casefold() for part in other["scenario"]["path"])
        )
        self.assertTrue(other["hints"])
        self.assertEqual(other["hints"][0]["source_type"], "scenario")

    def test_weak_phrase_suggests_scenario_without_auto_enter(self):
        result = suggest("про авто", session_id="lamp-car")
        self.assertIsNone(result["scenario"])
        suggested = result.get("suggested_scenario")
        self.assertIsNotNone(suggested)
        self.assertEqual(suggested["code"], "CC-SCR-004")

    def test_operator_can_enter_and_exit_suggested_scenario(self):
        entered = enter_scenario(
            "CC-SCR-004",
            session_key="manual-enter",
            channel="telephony",
        )
        self.assertIsNotNone(entered)
        self.assertEqual(entered.code, "CC-SCR-004")
        inside = suggest("новое авто в салоне", session_id="manual-enter")
        self.assertEqual(inside["scenario"]["code"], "CC-SCR-004")
        clear_scenario_session("manual-enter")
        after_exit = suggest(
            "как оформить карту на моё имя",
            session_id="manual-enter",
        )
        self.assertIsNone(after_exit["scenario"])

    def test_published_graph_gets_semantic_expansion_without_manual_synonyms(self):
        item = DialogScenario.objects.get(code="CC-SCR-009")
        expansion = (item.current_version.graph or {}).get("semantic_expansion") or ""
        self.assertIn("криптобирж", expansion.casefold())
        start = next(
            node
            for node in item.current_version.graph["nodes"]
            if node["id"] == "start"
        )
        profile = _semantic_profile(item, item.current_version.graph, start)
        self.assertIn("криптобирж", profile.casefold())
        self.assertNotIn("эфириум", expansion.casefold())

    def test_related_concept_uses_semantic_profile_not_keyword_list(self):
        scenarios = list(DialogScenario.objects.all())
        vectors = {
            scenario.pk: (
                [1.0, 0.0]
                if scenario.code == "CC-SCR-009"
                else [0.0, 1.0]
            )
            for scenario in scenarios
        }
        signature = ((1, "related-concept"),)
        with (
            patch(
                "orchestrator.scenario_engine._semantic_signature",
                return_value=signature,
            ),
            patch(
                "orchestrator.scenario_engine._semantic_cache_signature",
                signature,
            ),
            patch(
                "orchestrator.scenario_engine._semantic_cache_backend",
                "http",
            ),
            patch(
                "orchestrator.scenario_engine._semantic_cache_vectors",
                vectors,
            ),
            patch(
                "core.embeddings.embed_query_with_backend",
                return_value=([1.0, 0.0], "http"),
            ),
        ):
            matched = _match_start("Хочу перевести эфириум")
        self.assertIsNotNone(matched)
        self.assertEqual(matched[0].code, "CC-SCR-009")

    def test_brand_paraphrase_uses_embeddings_not_hardcoded_list(self):
        car = DialogScenario.objects.get(code="CC-SCR-004")
        start = next(
            node
            for node in car.current_version.graph["nodes"]
            if node["id"] == "start"
        )
        self.assertEqual(
            _topic_boost("хочу кредит на джили", _semantic_profile(car, car.current_version.graph, start)),
            0,
        )
        scenarios = list(DialogScenario.objects.all())
        vectors = {
            scenario.pk: (
                [1.0, 0.0]
                if scenario.code == "CC-SCR-004"
                else [0.0, 1.0]
            )
            for scenario in scenarios
        }
        signature = ((1, "brand-paraphrase"),)
        with (
            patch(
                "orchestrator.scenario_engine._semantic_signature",
                return_value=signature,
            ),
            patch(
                "orchestrator.scenario_engine._semantic_cache_signature",
                signature,
            ),
            patch(
                "orchestrator.scenario_engine._semantic_cache_backend",
                "http",
            ),
            patch(
                "orchestrator.scenario_engine._semantic_cache_vectors",
                vectors,
            ),
            patch(
                "core.embeddings.embed_query_with_backend",
                return_value=([1.0, 0.0], "http"),
            ),
        ):
            matched = _match_start("хочу кредит на джили")
        self.assertIsNotNone(matched)
        self.assertEqual(matched[0].code, "CC-SCR-004")

    def test_generic_phone_transfer_not_rf_even_with_embeddings(self):
        scenarios = list(DialogScenario.objects.all())
        vectors = {
            scenario.pk: (
                [1.0, 0.0]
                if scenario.code == "CC-SCR-005"
                else [0.0, 1.0]
            )
            for scenario in scenarios
        }
        signature = ((1, "generic-phone-transfer"),)
        with (
            patch(
                "orchestrator.scenario_engine._semantic_signature",
                return_value=signature,
            ),
            patch(
                "orchestrator.scenario_engine._semantic_cache_signature",
                signature,
            ),
            patch(
                "orchestrator.scenario_engine._semantic_cache_backend",
                "http",
            ),
            patch(
                "orchestrator.scenario_engine._semantic_cache_vectors",
                vectors,
            ),
            patch(
                "core.embeddings.embed_query_with_backend",
                return_value=([1.0, 0.0], "http"),
            ),
        ):
            matched = _match_start("хочу просто перевод по телефону")
        self.assertIsNone(matched)
        with (
            patch(
                "orchestrator.scenario_engine._semantic_signature",
                return_value=signature,
            ),
            patch(
                "orchestrator.scenario_engine._semantic_cache_signature",
                signature,
            ),
            patch(
                "orchestrator.scenario_engine._semantic_cache_backend",
                "http",
            ),
            patch(
                "orchestrator.scenario_engine._semantic_cache_vectors",
                {
                    scenario.pk: (
                        [1.0, 0.0]
                        if scenario.code == "CC-SCR-009"
                        else [0.0, 1.0]
                    )
                    for scenario in scenarios
                },
            ),
            patch(
                "core.embeddings.embed_query_with_backend",
                return_value=([1.0, 0.0], "http"),
            ),
        ):
            matched_crypto = _match_start(
                "как перевести деньги по номеру телефона"
            )
        self.assertIsNone(matched_crypto)

    def test_attach_semantic_expansion_uses_title_without_hardcoded_aliases(self):
        graph = attach_semantic_expansion(
            "Перевод на криптобиржу",
            "Мне нужно перечислить деньги на криптобиржу?",
            {"nodes": [{"id": "start", "type": "start", "label": "Криптобиржа"}]},
        )
        expansion = graph["semantic_expansion"]
        self.assertIn("криптобирж", expansion.casefold())
        self.assertNotIn("эфириум", expansion.casefold())
        self.assertNotIn("binance", expansion.casefold())


class ScenarioAdminApiTest(TestCase):
    url = "/api/admin/scenarios/"

    def user_for_role(self, role_code):
        role = ROLES_BY_CODE[role_code]
        user = get_user_model().objects.create_user(
            username=f"scenario-admin-{role_code}",
            password="test-password",
        )
        group, _ = Group.objects.get_or_create(name=role.mock_ad_group)
        user.groups.add(group)
        return user

    def setUp(self):
        upsert_from_catalog(REFERENCE_SCENARIOS[4], username="test")

    def test_list_and_detail(self):
        client = Client()
        client.force_login(self.user_for_role("contact_center_module_administrator"))
        response = client.get(self.url)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertGreaterEqual(body["counts"]["production"], 1)
        detail = client.get(f"{self.url}CC-SCR-005/")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("nodes", detail.json()["graph"])

    def test_publish_creates_new_version_without_changing_code(self):
        client = Client()
        client.force_login(self.user_for_role("contact_center_module_administrator"))
        detail = client.get(f"{self.url}CC-SCR-005/").json()
        first_version = detail["version_number"]
        response = client.put(
            f"{self.url}CC-SCR-005/",
            data=json.dumps(
                {
                    "title": detail["title"],
                    "graph": detail["graph"],
                    "system_prompt": detail["system_prompt"],
                    "publish": True,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["code"], "CC-SCR-005")
        self.assertGreaterEqual(body["version_number"], first_version)
        self.assertTrue(body["is_published"])

    def test_test_run_reports_path(self):
        client = Client()
        client.force_login(self.user_for_role("software_administrator"))
        response = client.post(
            f"{self.url}CC-SCR-005/test-run/",
            data=json.dumps(
                {
                    "lines": [
                        "надо отправить деньги в россию",
                        "на карту",
                        "через мобильный банк",
                    ]
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["steps"]), 3)
        self.assertTrue(body["ok"])
        self.assertGreaterEqual(len(body["path"]), 3)
        self.assertEqual(body["steps"][0]["selected_edge"], "")
        self.assertTrue(body["steps"][0]["available_choices"])
        self.assertEqual(
            body["steps"][0]["available_choices"][0],
            {
                "label": "Карта банка РФ",
                "reply": "Хочу перевести деньги на карту Сбербанка",
            },
        )
        self.assertEqual(body["steps"][1]["selected_edge"], "Карта банка РФ")
        self.assertTrue(body["steps"][2]["terminal"])
        self.assertTrue(body["steps"][2]["hint_text"])
        self.assertGreaterEqual(body["version_number"], 1)

    def test_test_run_keeps_current_node_for_unknown_branch(self):
        client = Client()
        client.force_login(self.user_for_role("software_administrator"))
        response = client.post(
            f"{self.url}CC-SCR-005/test-run/",
            data=json.dumps(
                {
                    "lines": [
                        "надо отправить деньги в россию",
                        "совсем другой ответ",
                    ]
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertFalse(body["steps"][1]["ok"])
        self.assertEqual(body["steps"][0]["node_id"], body["steps"][1]["node_id"])
        self.assertIn("Ожидалось", body["errors"][0])

    def test_scenario_graph_preserves_safe_node_position(self):
        client = Client()
        client.force_login(self.user_for_role("contact_center_module_administrator"))
        detail = client.get(f"{self.url}CC-SCR-005/").json()
        detail["graph"]["nodes"][0]["position"] = {"x": 125.4, "y": 88}
        response = client.put(
            f"{self.url}CC-SCR-005/",
            data=json.dumps(
                {
                    "title": detail["title"],
                    "root_question": detail["root_question"],
                    "graph": detail["graph"],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["graph"]["nodes"][0]["position"],
            {"x": 125.4, "y": 88.0},
        )

    def test_create_draft(self):
        client = Client()
        client.force_login(self.user_for_role("contact_center_module_administrator"))
        response = client.post(
            self.url,
            data=json.dumps(
                {
                    "code": "CC-SCR-099",
                    "title": "Тестовый черновик",
                    "root_question": "Проверка",
                    "graph": {"nodes": [{"id": "start", "type": "start", "label": "Старт"}]},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "draft")
        self.assertEqual(response.json()["code"], "CC-SCR-099")

    def test_draft_save_preserves_variant_before_continuation_is_created(self):
        client = Client()
        client.force_login(self.user_for_role("contact_center_module_administrator"))
        response = client.post(
            self.url,
            data=json.dumps(
                {
                    "code": "CC-SCR-098",
                    "title": "Неполный черновик",
                    "root_question": "Хочу проверить черновик",
                    "graph": {
                        "nodes": [
                            {
                                "id": "start",
                                "type": "start",
                                "label": "Начало",
                                "edges": [
                                    {
                                        "to": "",
                                        "label": "Да",
                                        "reply": "Да, хочу продолжить",
                                        "keywords": ["продолжить"],
                                    }
                                ],
                            }
                        ]
                    },
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        edge = response.json()["graph"]["nodes"][0]["edges"][0]
        self.assertEqual(edge["to"], "")
        self.assertEqual(edge["reply"], "Да, хочу продолжить")

    def test_create_and_update_preserve_edge_reply(self):
        client = Client()
        client.force_login(
            self.user_for_role("contact_center_module_administrator")
        )
        graph = {
            "nodes": [
                {
                    "id": "start",
                    "type": "start",
                    "label": "Старт",
                    "edges": [
                        {
                            "to": "answer",
                            "label": "Android",
                            "reply": "У меня Android",
                            "keywords": ["android"],
                        }
                    ],
                },
                {"id": "answer", "type": "answer", "label": "Ответ"},
            ]
        }
        created = client.post(
            self.url,
            data=json.dumps(
                {
                    "code": "CC-SCR-098",
                    "title": "Проверка reply",
                    "graph": graph,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(
            created.json()["graph"]["nodes"][0]["edges"][0]["reply"],
            "У меня Android",
        )

        graph["nodes"][0]["edges"][0]["reply"] = "У меня Android-смартфон"
        updated = client.put(
            f"{self.url}CC-SCR-098/",
            data=json.dumps({"title": "Проверка reply", "graph": graph}),
            content_type="application/json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(
            updated.json()["graph"]["nodes"][0]["edges"][0]["reply"],
            "У меня Android-смартфон",
        )
