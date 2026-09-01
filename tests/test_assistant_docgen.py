import io
import json
import os
import sys
import zipfile
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

from assistant.docgen import build_document, render_body  # noqa: E402
from auth.roles import ROLES_BY_CODE  # noqa: E402
from hub.models import AssistantDocumentTemplate  # noqa: E402


class AssistantDocgenTest(TestCase):
    def user_for_role(self, role_code):
        role = ROLES_BY_CODE[role_code]
        user = get_user_model().objects.create_user(
            username=f"docgen-{role_code}",
            password="test-password",
        )
        group, _ = Group.objects.get_or_create(name=role.mock_ad_group)
        user.groups.add(group)
        return user

    def test_seed_templates_and_fill_docx(self):
        leave = AssistantDocumentTemplate.objects.get(name="Заявление на отпуск")
        self.assertEqual(leave.output_format, "docx")
        text = render_body(
            leave,
            {
                "full_name": "Сидоров Пётр Константинович",
                "department": "Департамент ИТ",
                "start_date": "15.07.2026",
            },
        )
        self.assertIn("Сидоров Пётр Константинович", text)
        self.assertIn("Департамент ИТ", text)
        data, filename, content_type = build_document(
            leave,
            {
                "full_name": "Сидоров Пётр Константинович",
                "department": "Департамент ИТ",
                "start_date": "15.07.2026",
            },
        )
        self.assertTrue(filename.endswith(".docx"))
        self.assertIn("wordprocessingml", content_type)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml = archive.read("word/document.xml").decode("utf-8")
        self.assertIn("Сидоров", xml)
        self.assertIn("15.07.2026", xml)

    def test_required_fields_rejected(self):
        leave = AssistantDocumentTemplate.objects.get(name="Заявление на отпуск")
        with self.assertRaises(ValueError):
            render_body(leave, {"full_name": "Иванов"})

    def test_admin_crud_and_chat_generate(self):
        admin = Client()
        admin.force_login(
            self.user_for_role("ai_assistant_module_administrator")
        )
        listed = admin.get("/api/admin/assistant/doc-templates/")
        self.assertEqual(listed.status_code, 200)
        names = {item["name"] for item in listed.json()["items"]}
        self.assertIn("Заявление на отпуск", names)
        self.assertIn("Служебная записка", names)

        created = admin.post(
            "/api/admin/assistant/doc-templates/",
            data=json.dumps(
                {
                    "name": "Реестр заявок",
                    "category": "Операции",
                    "output_format": "xlsx",
                    "body": "Клиент: {{client}}\nСумма: {{amount}}",
                    "fields": [
                        {"id": "client", "label": "Клиент", "required": True},
                        {"id": "amount", "label": "Сумма", "required": False},
                    ],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201, created.content)
        template_id = created.json()["id"]

        updated = admin.put(
            f"/api/admin/assistant/doc-templates/{template_id}/",
            data=json.dumps({"active": False}),
            content_type="application/json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertFalse(updated.json()["active"])

        chat = Client()
        chat.force_login(self.user_for_role("ai_assistant_user"))
        catalog = chat.get("/api/v1/assistant/doc-templates/")
        self.assertEqual(catalog.status_code, 200)
        active_ids = {item["id"] for item in catalog.json()["items"]}
        self.assertNotIn(template_id, active_ids)

        leave_id = AssistantDocumentTemplate.objects.get(
            name="Заявление на отпуск"
        ).pk
        fields = {
            "full_name": "Сидоров Пётр Константинович",
            "department": "Департамент ИТ",
            "start_date": "15.07.2026",
        }
        draft = chat.post(
            f"/api/v1/assistant/doc-templates/{leave_id}/generate/",
            data=json.dumps({"mode": "draft", "fields": fields}),
            content_type="application/json",
        )
        self.assertEqual(draft.status_code, 200, draft.content)
        self.assertIn("Сидоров", draft.json()["text"])
        self.assertEqual(draft.json()["mode"], "draft")

        download = chat.post(
            f"/api/v1/assistant/doc-templates/{leave_id}/generate/",
            data=json.dumps({"mode": "download", "fields": fields}),
            content_type="application/json",
        )
        self.assertEqual(download.status_code, 200, download.content)
        self.assertTrue(download.content.startswith(b"PK"))
        self.assertIn(
            "wordprocessingml",
            download["Content-Type"],
        )

        memo_id = AssistantDocumentTemplate.objects.get(
            name="Служебная записка"
        ).pk
        pdf = chat.post(
            f"/api/v1/assistant/doc-templates/{memo_id}/generate/",
            data=json.dumps(
                {
                    "mode": "download",
                    "fields": {
                        "full_name": "Иванов Иван",
                        "department": "HR",
                        "memo_date": "01.09.2026",
                        "subject": "Отпуск",
                        "body_text": "Прошу согласовать.",
                    },
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(pdf.status_code, 200, pdf.content)
        self.assertTrue(pdf.content.startswith(b"%PDF"))

        missing = chat.post(
            f"/api/v1/assistant/doc-templates/{leave_id}/generate/",
            data=json.dumps({"mode": "draft", "fields": {"full_name": "А"}}),
            content_type="application/json",
        )
        self.assertEqual(missing.status_code, 400)

        denied = Client()
        denied.force_login(self.user_for_role("ai_assistant_analyst"))
        forbidden = denied.post(
            "/api/admin/assistant/doc-templates/",
            data=json.dumps(
                {
                    "name": "Нет прав",
                    "body": "{{x}}",
                    "fields": [{"id": "x", "label": "X"}],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(forbidden.status_code, 403)
