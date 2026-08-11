import os
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sufler.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Group  # noqa: E402
from django.test import Client, TestCase, override_settings  # noqa: E402

from auth.roles import ROLES_BY_CODE  # noqa: E402
from hub.assistant_admin import (  # noqa: E402
    create_assistant_kb,
    upload_assistant_document,
)
from hub.models import AssistantKnowledgeBaseDocument  # noqa: E402


@override_settings()
class AssistantSourceDownloadTest(TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(
            ASSISTANT_KB_STORAGE_ROOT=Path(self._tmpdir.name),
        )
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        try:
            self._tmpdir.cleanup()
        except PermissionError:
            pass

    def user_for_role(self, role_code):
        role = ROLES_BY_CODE[role_code]
        user = get_user_model().objects.create_user(
            username=f"src-{role_code}",
            password="test-password",
        )
        group, _ = Group.objects.get_or_create(name=role.mock_ad_group)
        user.groups.add(group)
        return user

    def test_download_original_from_chat_source(self):
        create_assistant_kb(
            {
                "name": "HR demo",
                "slug": "assistant_hr_dl",
                "description": "test",
            },
            username="tester",
        )
        from hub.models import AssistantKnowledgeBase

        kb = AssistantKnowledgeBase.objects.get(slug="assistant_hr_dl")
        payload = b"Hello source document content"
        upload_assistant_document(
            kb.pk,
            filename="zaiavlenie_ob_okazanii_fp040225.txt",
            content_type="text/plain",
            data=payload,
            username="tester",
            reindex=False,
        )
        document = AssistantKnowledgeBaseDocument.objects.get(
            knowledge_base=kb
        )
        self.assertTrue(document.original_relpath)

        client = Client()
        client.force_login(self.user_for_role("ai_assistant_user"))
        response = client.get(
            "/api/v1/assistant/sources/download",
            {
                "kb_slug": kb.slug,
                "article_id": document.article_id,
            },
        )
        self.assertEqual(response.status_code, 200)
        body = b"".join(response.streaming_content)
        response.close()
        self.assertEqual(body, payload)
        disposition = response["Content-Disposition"]
        self.assertIn("zaiavlenie_ob_okazanii_fp040225.txt", disposition)
