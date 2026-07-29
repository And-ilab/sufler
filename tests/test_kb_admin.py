import io
import json
import os
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sufler.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Group  # noqa: E402
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.test import Client, TestCase  # noqa: E402

from auth.roles import ROLES_BY_CODE  # noqa: E402
from hub.models import ContactCenterKnowledgeBase  # noqa: E402
from ingest.models import CCProductionChunk  # noqa: E402


def build_docx(text: str) -> bytes:
    document = ET.Element(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document"
    )
    body = ET.SubElement(
        document,
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}body",
    )
    paragraph = ET.SubElement(
        body,
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p",
    )
    run = ET.SubElement(
        paragraph,
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r",
    )
    node = ET.SubElement(
        run,
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t",
    )
    node.text = text
    xml_bytes = ET.tostring(document, encoding="utf-8", xml_declaration=True)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr("word/document.xml", xml_bytes)
    return buffer.getvalue()


class KnowledgeBaseAdminApiTest(TestCase):
    def user_for_role(self, role_code):
        role = ROLES_BY_CODE[role_code]
        user = get_user_model().objects.create_user(
            username=f"kb-admin-{role_code}",
            password="test-password",
        )
        group, _ = Group.objects.get_or_create(name=role.mock_ad_group)
        user.groups.add(group)
        return user

    def test_crud_upload_reindex_and_status(self):
        client = Client()
        client.force_login(
            self.user_for_role("llm_knowledge_base_administrator")
        )

        create_response = client.post(
            "/api/admin/kb/",
            data=json.dumps(
                {
                    "name": "Регламенты КЦ",
                    "description": "Основные инструкции",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        kb = create_response.json()
        self.assertEqual(kb["name"], "Регламенты КЦ")
        self.assertEqual(kb["status"], "idle")
        kb_id = kb["id"]

        list_response = client.get("/api/admin/kb/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()["items"]), 1)

        upload_response = client.post(
            f"/api/admin/kb/{kb_id}/upload/",
            data={
                "file": SimpleUploadedFile(
                    "rules.docx",
                    build_docx("Оформление банковской карты для клиента КЦ"),
                    content_type=(
                        "application/vnd.openxmlformats-officedocument"
                        ".wordprocessingml.document"
                    ),
                )
            },
        )
        self.assertEqual(upload_response.status_code, 201)
        payload = upload_response.json()
        self.assertEqual(payload["knowledge_base"]["status"], "ready")
        self.assertEqual(payload["document"]["status"], "indexed")
        self.assertGreater(payload["document"]["chunk_count"], 0)
        self.assertTrue(
            CCProductionChunk.objects.filter(
                title="rules.docx",
                is_active=True,
            ).exists()
        )

        reindex_response = client.post(f"/api/admin/kb/{kb_id}/reindex/")
        self.assertEqual(reindex_response.status_code, 200)
        self.assertEqual(reindex_response.json()["status"], "ready")

        detail = client.get(f"/api/admin/kb/{kb_id}/").json()
        document_id = detail["documents"][0]["id"]
        delete_doc = client.delete(
            f"/api/admin/kb/{kb_id}/documents/{document_id}/"
        )
        self.assertEqual(delete_doc.status_code, 200)
        self.assertEqual(delete_doc.json()["document_count"], 0)

        delete_kb = client.delete(f"/api/admin/kb/{kb_id}/")
        self.assertEqual(delete_kb.status_code, 200)
        self.assertFalse(
            ContactCenterKnowledgeBase.objects.filter(pk=kb_id).exists()
        )

    def test_txt_upload_accepted(self):
        client = Client()
        client.force_login(
            self.user_for_role("llm_knowledge_base_administrator")
        )
        kb_id = client.post(
            "/api/admin/kb/",
            data=json.dumps({"name": "FAQ КЦ"}),
            content_type="application/json",
        ).json()["id"]
        response = client.post(
            f"/api/admin/kb/{kb_id}/upload/",
            data={
                "file": SimpleUploadedFile(
                    "faq.txt",
                    "Как заменить ПИН-код карты".encode("utf-8"),
                    content_type="text/plain",
                )
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["knowledge_base"]["status"], "ready")

    def test_role_without_kb_permission_rejected(self):
        client = Client()
        client.force_login(
            self.user_for_role("contact_center_telephony_operator")
        )
        response = client.get("/api/admin/kb/")
        self.assertEqual(response.status_code, 403)
