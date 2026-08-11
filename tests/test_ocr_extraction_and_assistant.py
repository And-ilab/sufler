import json
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
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.test import Client, TestCase, override_settings  # noqa: E402

from auth.roles import ROLES_BY_CODE  # noqa: E402
from ocr.extraction import extract_passport_fields, extract_fields  # noqa: E402
from ocr.models import OcrDocumentTemplate, OcrJob  # noqa: E402
from ocr.templates_registry import seed_templates_from_yaml  # noqa: E402


PASSPORT_TEXT = """\
ПАСПОРТ РЕСПУБЛИКИ БЕЛАРУСЬ
Фамилия: ИВАНОВ
Имя: ИВАН
Отчество: ИВАНОВИЧ
Серия: MP
Номер: 4123456
Дата выдачи: 12.03.2019
"""


class OcrExtractionUnitTest(TestCase):
    def test_passport_fields_and_confidence(self):
        fields = extract_passport_fields(PASSPORT_TEXT)
        self.assertEqual(fields["full_name"]["value"], "ИВАНОВ ИВАН ИВАНОВИЧ")
        self.assertGreaterEqual(fields["full_name"]["confidence"], 0.9)
        self.assertEqual(fields["series"]["value"], "MP")
        self.assertEqual(fields["number"]["value"], "4123456")
        self.assertEqual(fields["issue_date"]["value"], "12.03.2019")

    def test_detect_type_from_filename(self):
        doc_type, fields = extract_fields(
            "Фамилия: ПЕТРОВ\nИмя: ПЁТР\nСерия: AB\nНомер: 7654321\n"
            "Дата выдачи: 01.01.2020",
            filename="passport_scan.png",
        )
        self.assertEqual(doc_type, "passport")
        self.assertIn("full_name", fields)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    OCR_OBJECT_STORE_BACKEND="fs",
)
class OcrAssistantAndTemplatesTest(TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(
            OCR_OBJECT_STORE_ROOT=Path(self._tmpdir.name),
            MINIO_OCR_BUCKET="sufler-ocr-test",
        )
        self.settings_override.enable()
        seed_templates_from_yaml()

    def tearDown(self):
        self.settings_override.disable()
        self._tmpdir.cleanup()

    def user_for_role(self, role_code):
        role = ROLES_BY_CODE[role_code]
        user = get_user_model().objects.create_user(
            username=f"ocr-asst-{role_code}",
            password="test-password",
        )
        group, _ = Group.objects.get_or_create(name=role.mock_ad_group)
        user.groups.add(group)
        return user

    def test_pipeline_structures_passport_fields(self):
        client = Client()
        client.force_login(self.user_for_role("document_recognition_user"))
        upload = SimpleUploadedFile(
            "passport_demo.png",
            PASSPORT_TEXT.encode("utf-8"),
            content_type="image/png",
        )
        response = client.post(
            "/api/v1/ocr/documents/",
            {"file": upload, "document_type": "passport", "sync": "1"},
        )
        self.assertIn(response.status_code, {200, 202}, response.content)
        body = response.json()
        job = OcrJob.objects.get(pk=body["job_id"])
        self.assertEqual(job.status, OcrJob.STATUS_COMPLETED)
        result = body.get("result")
        if result is None:
            result_resp = client.get(f"/api/v1/ocr/jobs/{job.job_id}/result/")
            self.assertEqual(result_resp.status_code, 200)
            result = result_resp.json()
        self.assertEqual(result["document_type"], "passport")
        self.assertEqual(result["fields"]["series"]["value"], "MP")
        self.assertIn("confidence", result["fields"]["full_name"])
        self.assertEqual(result["validation_status"], "valid")

    def test_assistant_ocr_endpoint(self):
        client = Client()
        client.force_login(self.user_for_role("ai_assistant_user"))
        upload = SimpleUploadedFile(
            "passport_ivanov.png",
            PASSPORT_TEXT.encode("utf-8"),
            content_type="image/png",
        )
        response = client.post(
            "/api/v1/assistant/attachments/ocr",
            {"file": upload, "document_type": "passport"},
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertIn("ocr", body)
        self.assertEqual(body["ocr"]["document_type"], "passport")
        self.assertEqual(body["ocr"]["fields"]["number"]["value"], "4123456")
        self.assertIn("ИВАНОВ", body["text"])

    def test_admin_template_publish_and_sample(self):
        client = Client()
        client.force_login(
            self.user_for_role("document_recognition_module_administrator")
        )
        response = client.get("/api/v1/ocr/templates/?seed=1")
        self.assertEqual(response.status_code, 200, response.content)
        items = response.json()["items"]
        self.assertTrue(any(item["doc_type"] == "passport" for item in items))

        put = client.put(
            "/api/v1/ocr/templates/passport/",
            data=json.dumps(
                {
                    "title": "Паспорт (обучение)",
                    "confidence_min": 0.55,
                    "publish": True,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(put.status_code, 200, put.content)
        template = OcrDocumentTemplate.objects.get(doc_type="passport")
        self.assertEqual(template.status, OcrDocumentTemplate.STATUS_PUBLISHED)
        self.assertGreaterEqual(template.template_version, 1)

        sample = client.post(
            "/api/v1/ocr/templates/passport/samples/",
            {
                "file": SimpleUploadedFile(
                    "train_passport.png",
                    PASSPORT_TEXT.encode("utf-8"),
                    content_type="image/png",
                )
            },
        )
        self.assertEqual(sample.status_code, 201, sample.content)
        payload = sample.json()
        self.assertEqual(payload["expected_fields"].get("series"), "MP")
