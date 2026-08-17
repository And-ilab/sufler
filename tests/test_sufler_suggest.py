import json
import logging
import os
import sys
import unittest
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
from core.embeddings import EmbeddingError  # noqa: E402
from core.model_gateway import ModelGateway  # noqa: E402
from ingest.models import CCProductionChunk  # noqa: E402
from ingest.pipeline import deterministic_embedding  # noqa: E402
from orchestrator.sufler import (  # noqa: E402
    SuflerOrchestratorError,
    suggest,
)


class SuflerSuggestPipelineTest(TestCase):
    @staticmethod
    def add_chunk(article_id, title, content):
        return CCProductionChunk.objects.create(
            article_id=article_id,
            version_id=1,
            chunk_index=0,
            title=title,
            content=content,
            permalink=f"https://suz.local/articles/{article_id}",
            locale="ru",
            visibility_scope=["kc_operator"],
            checksum=f"sha256:{article_id:064x}",
            embedding_model="deterministic-dev",
            embedding=deterministic_embedding(content),
        )

    def test_pipeline_returns_hints_citations_and_latency(self):
        query = "как оформить банковскую карту"
        self.add_chunk(11, "Оформление карты", query)
        self.add_chunk(22, "Кредитный договор", "условия кредита")

        with self.assertLogs("orchestrator.sufler", level=logging.INFO) as logs:
            result = suggest(query, limit=3, gateway=ModelGateway.from_registry())

        self.assertEqual(result["profile"], "sufler_cc")
        self.assertEqual(result["kb_id"], "cc_production")
        self.assertGreaterEqual(len(result["hints"]), 1)
        hint = result["hints"][0]
        self.assertTrue(hint["text"].strip())
        self.assertNotIn("Подсказка оператору", hint["text"])
        self.assertIn("СУЗ", hint["text"])
        self.assertTrue(hint["citations"])
        self.assertEqual(hint["citations"][0]["title"], "Оформление карты")
        self.assertTrue(
            hint["citations"][0]["permalink"].startswith("https://suz.local/")
        )
        for key in ("qu", "rag", "llm", "total"):
            self.assertIn(key, result["latency_ms"])
            self.assertGreaterEqual(result["latency_ms"][key], 0)
        self.assertTrue(
            any("sufler_suggest_latency" in message for message in logs.output)
        )
        self.assertEqual(result["gateway_model"], "qwen2.5-1.5b-instruct")
        self.assertIsNone(result["blocked_reason"])

    def test_empty_text_rejected(self):
        with self.assertRaises(SuflerOrchestratorError):
            suggest("   ")

    def test_limit_five_accepted_limit_six_rejected(self):
        query = "как оформить банковскую карту"
        self.add_chunk(11, "Оформление карты", query)
        result = suggest(query, limit=5, gateway=ModelGateway.from_registry())
        self.assertGreaterEqual(len(result["hints"]), 1)
        with self.assertRaises(SuflerOrchestratorError) as raised:
            suggest(query, limit=6, gateway=ModelGateway.from_registry())
        self.assertIn("between 1 and 5", str(raised.exception))

    def test_no_relevant_documents_skip_llm(self):
        # Empty index → unavailable. Irrelevant seeded docs → no_relevant_knowledge.
        with patch(
            "orchestrator.sufler.ModelGateway.chat",
            side_effect=AssertionError("LLM must not be called"),
        ):
            empty = suggest(
                "астрология гороскоп",
                limit=3,
                gateway=ModelGateway.from_registry(),
            )
        self.assertEqual(empty["hints"], [])
        self.assertEqual(empty["blocked_reason"], "sufler_unavailable")
        self.assertEqual(empty["latency_ms"]["llm"], 0.0)

        self.add_chunk(99, "Кредитный договор", "условия потребительского кредита")
        with patch(
            "orchestrator.sufler.ModelGateway.chat",
            side_effect=AssertionError("LLM must not be called"),
        ):
            result = suggest(
                "астрология гороскоп",
                limit=3,
                gateway=ModelGateway.from_registry(),
            )
        self.assertEqual(result["hints"], [])
        self.assertEqual(result["blocked_reason"], "no_relevant_knowledge")
        self.assertEqual(result["latency_ms"]["llm"], 0.0)

    def test_commission_fixtures_ignored_and_llm_answers(self):
        self.add_chunk(
            12845,
            "Komissiya za perevod3",
            "Komissiya za perevod mezhdu schetami banka "
            "sostavlyaet 0.5 procenta ot summy operacii.",
        )
        result = suggest(
            "Как оформить карту беларусбанка?",
            limit=3,
            gateway=ModelGateway.from_registry(),
        )
        titles = [
            citation["title"]
            for hint in result["hints"]
            for citation in hint["citations"]
        ]
        self.assertFalse(any("Komissiya" in title for title in titles))
        self.assertTrue(result["hints"])
        self.assertNotIn("0.5 procenta", result["hints"][0]["text"])
        self.assertIsNone(result["blocked_reason"])


class SuflerSuggestApiTest(TestCase):
    url = "/api/v1/sufler/suggest"

    def user_for_role(self, role_code):
        role = ROLES_BY_CODE[role_code]
        user = get_user_model().objects.create_user(
            username=f"sufler-suggest-{role_code}",
            password="test-password",
        )
        group, _ = Group.objects.get_or_create(name=role.mock_ad_group)
        user.groups.add(group)
        return user

    @staticmethod
    def add_chunk(article_id, title, content):
        return CCProductionChunk.objects.create(
            article_id=article_id,
            version_id=1,
            chunk_index=0,
            title=title,
            content=content,
            permalink=f"https://suz.local/articles/{article_id}",
            locale="ru",
            visibility_scope=["kc_operator"],
            checksum=f"sha256:{article_id:064x}",
            embedding_model="deterministic-dev",
            embedding=deterministic_embedding(content),
        )

    def test_telephony_operator_receives_hints(self):
        query = "замена пин-кода карты"
        self.add_chunk(44, "Смена ПИН-кода", query)
        client = Client()
        client.force_login(
            self.user_for_role("contact_center_telephony_operator")
        )
        response = client.post(
            self.url,
            data=json.dumps({"text": query, "limit": 3}),
            content_type="application/json",
            HTTP_X_REQUEST_ID="test-suggest-1",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["profile"], "sufler_cc")
        self.assertGreaterEqual(len(body["hints"]), 1)
        self.assertTrue(body["hints"][0]["citations"])
        self.assertIn("latency_ms", body)
        self.assertEqual(response["X-Request-ID"], body["request_id"])

    def test_chat_operator_allowed(self):
        query = "открытие вклада"
        self.add_chunk(55, "Вклады", query)
        client = Client()
        client.force_login(
            self.user_for_role("contact_center_online_chat_operator")
        )
        response = client.post(
            self.url,
            data=json.dumps({"text": query}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["kb_id"], "cc_production")

    def test_empty_text_is_rejected(self):
        client = Client()
        client.force_login(
            self.user_for_role("contact_center_telephony_operator")
        )
        response = client.post(
            self.url,
            data=json.dumps({"text": "  "}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "validation_error")

    def test_role_without_sufler_permission_is_rejected(self):
        client = Client()
        client.force_login(
            self.user_for_role("document_recognition_module_administrator")
        )
        response = client.post(
            self.url,
            data=json.dumps({"text": "карта"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "permission_denied")

    def test_http_embedding_outage_ranks_by_text_not_mixed_vectors(self):
        query = "Как оформить карту Беларусь банка?"
        self.add_chunk(
            12845,
            "Komissiya za perevod3",
            "Komissiya za perevod mezhdu schetami banka "
            "sostavlyaet 0.5 procenta ot summy operacii.",
        )
        self.add_chunk(
            91008,
            "Кредитная карта",
            "Как оформить кредитную карту Беларусбанка? "
            "Подайте заявку в отделении или онлайн.",
        )
        client = Client()
        client.force_login(
            self.user_for_role("contact_center_telephony_operator")
        )
        with patch.dict(
            os.environ,
            {
                "EMBEDDING_MODE": "http",
                "EMBEDDING_BASE_URL": "http://embedding:8090",
            },
            clear=False,
        ):
            with patch(
                "core.embeddings._http_embed",
                side_effect=EmbeddingError("down"),
            ):
                response = client.post(
                    self.url,
                    data=json.dumps({"text": query, "limit": 3}),
                    content_type="application/json",
                )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        titles = [
            citation["title"]
            for hint in body["hints"]
            for citation in hint["citations"]
        ]
        self.assertTrue(titles)
        self.assertTrue(any("карта" in title.casefold() for title in titles))
        self.assertFalse(any("Komissiya" in title for title in titles))


if __name__ == "__main__":
    unittest.main()
