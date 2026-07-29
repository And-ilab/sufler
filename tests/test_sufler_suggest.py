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
        self.assertIn("Подсказка оператору", hint["text"])
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
        self.assertEqual(result["gateway_model"], "stub:sufler_cc")
        self.assertIsNone(result["blocked_reason"])

    def test_empty_text_rejected(self):
        with self.assertRaises(SuflerOrchestratorError):
            suggest("   ")

    def test_no_relevant_documents_skip_llm(self):
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


if __name__ == "__main__":
    unittest.main()
