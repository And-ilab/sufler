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
from hub.scenario_catalog import ALL_SCENARIOS, REFERENCE_SCENARIOS  # noqa: E402
from hub.scenario_service import upsert_from_catalog  # noqa: E402
from orchestrator.scenario_engine import _match_start, classify_turn  # noqa: E402
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
        self.assertTrue(body["steps"])
        self.assertGreaterEqual(len(body["path"]), 1)

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
