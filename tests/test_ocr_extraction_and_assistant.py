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

    def test_passport_fields_without_labels(self):
        """Phone-photo OCR often drops labels — recover FIO / ID / date."""
        fields = extract_passport_fields(
            "РЕСПУБЛИКА БЕЛАРУСЬ\n"
            "ИВАНОВ ИВАН ИВАНОВИЧ\n"
            "PD 0000000\n"
            "12.03.2019\n"
        )
        self.assertEqual(fields["full_name"]["value"], "ИВАНОВ ИВАН ИВАНОВИЧ")
        self.assertEqual(fields["series"]["value"], "PD")
        self.assertEqual(fields["number"]["value"], "0000000")
        self.assertEqual(fields["issue_date"]["value"], "12.03.2019")

    def test_russian_passport_multiline_labels(self):
        """RF passport: labels on one line, values on the next; series 45 11."""
        fields = extract_passport_fields(
            "ПАСПОРТ\n"
            "Фамилия\n"
            "АНАНД\n"
            "Имя\n"
            "ОМКАР\n"
            "Отчество\n"
            "ВИКТОРОВИЧ\n"
            "Пол\n"
            "МУЖ.\n"
            "Дата рождения\n"
            "16.09.1988\n"
            "Место рождения\n"
            "ГОРОД МОСКВА\n"
            "45 11 532704\n"
        )
        self.assertEqual(fields["full_name"]["value"], "АНАНД ОМКАР ВИКТОРОВИЧ")
        self.assertEqual(fields["surname"]["value"], "АНАНД")
        self.assertEqual(fields["given_name"]["value"], "ОМКАР")
        self.assertEqual(fields["patronymic"]["value"], "ВИКТОРОВИЧ")
        self.assertEqual(fields["series"]["value"], "45 11")
        self.assertEqual(fields["number"]["value"], "532704")
        self.assertEqual(fields["birth_date"]["value"], "16.09.1988")
        self.assertNotEqual(fields["full_name"]["value"], "ГОРОД МОСКВА")

    def test_belarus_passport_mrz_not_header(self):
        """English header + MRZ: FIO from MRZ, not REPUBLIC OF BELARUS."""
        fields = extract_passport_fields(
            "REPUBLIC OF BELARUS\n"
            "PASSPORT\n"
            "Surname\nSAYAPIN\n"
            "Given names\nANDREI\n"
            "Nationality\nREPUBLIC OF BELARUS\n"
            "Passport No. MP2417879\n"
            "P<BLRSAYAPIN<<ANDREI<<<<<<<<<<<<<<<<<<<<<<<<<<\n"
            "MP24178795BLR8304265M28042683260483A011PB648\n"
        )
        self.assertEqual(fields["full_name"]["value"], "SAYAPIN ANDREI")
        self.assertEqual(fields["surname"]["value"], "SAYAPIN")
        self.assertEqual(fields["given_name"]["value"], "ANDREI")
        self.assertEqual(fields["series"]["value"], "MP")
        self.assertEqual(fields["number"]["value"], "2417879")
        self.assertEqual(fields["document_number"]["value"], "MP2417879")
        self.assertEqual(fields["birth_date"]["value"], "26.04.1983")
        self.assertNotEqual(fields["full_name"]["value"], "REPUBLIC OF BELARUS")

    def test_noisy_english_header_without_labels(self):
        fields = extract_passport_fields(
            "REPUBLIC OF BELARUS\n"
            "PASSPORT\n"
            "P<BLRSAYAPIN<<ANDREI<<<<<<<<<<<<<<<<<<<<<<<<<<\n"
            "MP24178795BLR8304265M28042683260483A011PB648\n"
        )
        self.assertEqual(fields["full_name"]["value"], "SAYAPIN ANDREI")
        self.assertEqual(fields["document_number"]["value"], "MP2417879")

    def test_icao_sample_us_passport_mrz(self):
        """Public ICAO TD3 example (Wikipedia / industry docs)."""
        fields = extract_passport_fields(
            "P<USASMITH<<JOHN<MICHAEL<<<<<<<<<<<<<<<<<<<<\n"
            "1234567897USA8501011M2501019<<<<<<<<<<<<<<06\n"
        )
        self.assertEqual(fields["full_name"]["value"], "SMITH JOHN MICHAEL")
        self.assertEqual(fields["document_number"]["value"], "123456789")
        self.assertEqual(fields["birth_date"]["value"], "01.01.1985")

    def test_azerbaijan_noisy_photo_ocr(self):
        """Real GitHub sample: Tesseract splits MRZ; recover FIO + number."""
        fields = extract_passport_fields(
            "C94630262\n"
            "QAQARIN\nQAQARIN\n"
            "FIDAN BƏŞİR QIZI\nFIDAN\n"
            "AZORBAYCAN/AZERBAIJAN\n"
            "PCAZEQA\n"
            "C94630262\n"
            "OAZE6707297F23031072W12IMJ <<<<<<<4O\n"
        )
        self.assertEqual(fields["full_name"]["value"], "QAQARIN FIDAN")
        self.assertEqual(fields["document_number"]["value"], "C94630262")
        self.assertEqual(fields["birth_date"]["value"], "29.07.1967")
        self.assertEqual(fields["expiry_date"]["value"], "10.03.2023")
        doc_type, detected = extract_fields(
            "C94630262\nQAQARIN\nQAQARIN\nFIDAN\nFIDAN\n"
            "AZORBAYCAN/AZERBAIJAN\n"
            "C946302620AZE67 (O7297F23031072W12IMJ\n",
            filename="scan.jpg",
        )
        self.assertEqual(doc_type, "passport")
        self.assertEqual(detected["full_name"]["value"], "QAQARIN FIDAN")
        self.assertEqual(detected["document_number"]["value"], "C94630262")

    def test_german_td3_adenauer_sample(self):
        """Wikimedia public-domain ICAO graphic (P<D<< + 9-digit number)."""
        fields = extract_passport_fields(
            "P<D<<ADENAUER<<KONRAD<HERMANN<JOSEPH<<<<<<<<\n"
            "1234567897D<<7601059M6704115<<<<<<<<<<<<<<<2\n"
        )
        self.assertEqual(fields["full_name"]["value"], "ADENAUER KONRAD HERMANN JOSEPH")
        self.assertEqual(fields["document_number"]["value"], "123456789")
        self.assertEqual(fields["birth_date"]["value"], "05.01.1976")


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
