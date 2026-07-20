import json
import os
import sys
from pathlib import Path


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
from ingest.models import CCProductionChunk  # noqa: E402
from ingest.pipeline import deterministic_embedding  # noqa: E402
from qu.models import QuReferenceExample  # noqa: E402


class QuPreviewIntegrationTest(TestCase):
    url = "/api/admin/qu/preview/"

    def user_for_role(self, role_code):
        role = ROLES_BY_CODE[role_code]
        user = get_user_model().objects.create_user(
            username=f"qu-preview-{role_code}",
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

    def test_admin_receives_ranked_percent_and_matched_example(self):
        query = "оформление отпуска сотруднику"
        self.add_chunk(101, "Положение об отпусках", query)
        self.add_chunk(202, "Регламент банковских карт", "замена банковской карты")
        example = QuReferenceExample.objects.create(
            question="Как оформить отпуск сотруднику?",
            article_id=101,
            intent_id="HR-LEAVE",
        )
        QuReferenceExample.objects.create(
            question="Как заменить банковскую карту?",
            article_id=202,
            intent_id="CARD-REPLACE",
        )
        client = Client()
        client.force_login(
            self.user_for_role("llm_knowledge_base_administrator")
        )

        response = client.post(
            self.url,
            data=json.dumps({"query": query, "limit": 5}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["kb_id"], "cc_production")
        self.assertEqual(body["documents"][0]["article_id"], 101)
        self.assertEqual(body["documents"][0]["relevance_percent"], 100)
        self.assertEqual(
            body["documents"][0]["matched_example"],
            example.question,
        )
        self.assertEqual(
            body["documents"][0]["matched_example_id"],
            example.pk,
        )
        scores = [
            document["relevance_score"] for document in body["documents"]
        ]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_empty_query_is_rejected(self):
        client = Client()
        client.force_login(
            self.user_for_role("llm_knowledge_base_administrator")
        )
        response = client.post(
            self.url,
            data=json.dumps({"query": "   "}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "validation_error")

    def test_role_without_qu_permission_is_rejected(self):
        client = Client()
        client.force_login(
            self.user_for_role("contact_center_module_administrator")
        )
        response = client.post(
            self.url,
            data=json.dumps({"query": "отпуск"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_request_is_rejected(self):
        response = Client().post(
            self.url,
            data=json.dumps({"query": "отпуск"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
