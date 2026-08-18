"""IV.8 validation + JSON/CSV export — DOC-T-03/04/08 subset."""

from __future__ import annotations

import csv
import io
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
from ocr.export import build_csv_export, build_json_export  # noqa: E402
from ocr.validation import (  # noqa: E402
    STATUS_PENDING_REVIEW,
    STATUS_VALID,
    ValidationRequestError,
    assert_downstream_ready,
    list_document_types,
    validate_document,
)


# Acceptance IDs covered by this suite (IV.8 subset).
DOC_T_SUBSET = ("DOC-T-03", "DOC-T-04", "DOC-T-08")


class OcrValidationEngineTest(TestCase):
    """DOC-T-04 — required fields + regex/format validation per doc_type."""

    def test_doc_t_03_unknown_type_rejected_and_catalog_lists_types(self):
        # DOC-T-03: document_type must be known / reclassifiable via catalog.
        types = {item["doc_type"] for item in list_document_types()}
        self.assertIn("passport", types)
        self.assertIn("payment_order", types)
        with self.assertRaises(ValidationRequestError):
            validate_document("not_a_real_type", {"amount": "1"})

    def test_doc_t_04_valid_payment_order_passes(self):
        result = validate_document(
            "payment_order",
            {
                "document_number": "42",
                "date": "20.07.2026",
                "payer": "ООО Альфа",
                "beneficiary": "ООО Бета",
                "amount": "1 500,00",
                "purpose": "оплата услуг",
                "currency": "BYN",
            },
            job_id="ocrjob-demo",
            document_id="doc-demo",
        )
        self.assertEqual(result.status, STATUS_VALID)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.normalized_fields["amount"], "1500.00")
        self.assertEqual(result.normalized_fields["date"], "2026-07-20")
        self.assertEqual(result.missing_required_fields, [])
        self.assertEqual(result.anomalies, [])
        self.assertIn("DOC-T-04", result.acceptance)
        assert_downstream_ready(result)

    def test_doc_t_04_rejects_invalid_and_missing_fields(self):
        result = validate_document(
            "passport",
            {
                "full_name": "Ив",
                "series": "123",
                "number": "ABC",
            },
        )
        self.assertEqual(result.status, STATUS_PENDING_REVIEW)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.missing_required_fields, [])
        codes = {item.code for item in result.anomalies}
        self.assertIn("invalid_format", codes)
        rejected = set(result.rejected_fields)
        self.assertTrue({"series", "number", "full_name"} <= rejected)
        with self.assertRaises(ValidationRequestError):
            assert_downstream_ready(result)

    def test_doc_t_04_unknown_field_is_rejected(self):
        result = validate_document(
            "payment_receipt",
            {
                "operation_date": "20.07.2026",
                "operation_id": "OP-9001",
                "amount": "75.30",
                "currency": "BYN",
                "status": "выполнено",
                "secret_extra": "should-not-pass",
            },
        )
        self.assertEqual(result.status, STATUS_PENDING_REVIEW)
        self.assertIn("secret_extra", result.rejected_fields)

    def test_doc_t_08_json_and_csv_export_only_when_valid(self):
        valid = validate_document(
            "banking_application",
            {
                "application_number": "APP-104",
                "application_date": "18.07.2026",
                "product": "платёжная карта",
                "signature_present": True,
            },
            job_id="ocrjob-app",
            document_id="doc-app",
        )
        json_bytes = build_json_export(valid)
        payload = json.loads(json_bytes.decode("utf-8"))
        self.assertEqual(payload["status"], "valid")
        self.assertTrue(payload["validation"]["downstream_allowed"])
        self.assertEqual(payload["fields"]["application_number"], "APP-104")

        csv_bytes = build_csv_export(valid)
        rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
        self.assertEqual(rows[0][0], "document_type")
        self.assertTrue(any(row[2] == "product" for row in rows[1:]))

        invalid = validate_document("passport", {"series": "MP"})
        with self.assertRaises(ValidationRequestError):
            build_json_export(invalid)
        with self.assertRaises(ValidationRequestError):
            build_csv_export(invalid)


class OcrValidationApiTest(TestCase):
    def user_for_role(self, role_code):
        role = ROLES_BY_CODE[role_code]
        user = get_user_model().objects.create_user(
            username=f"ocr-val-{role_code}",
            password="test-password",
        )
        group, _ = Group.objects.get_or_create(name=role.mock_ad_group)
        user.groups.add(group)
        return user

    def test_api_validate_and_export_doc_t_subset(self):
        client = Client()
        client.force_login(self.user_for_role("document_recognition_user"))

        catalog = client.get("/api/v1/ocr/doc-types/")
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual(catalog.json()["acceptance"], ["DOC-T-04", "FR-OCR-14"])

        bad = client.post(
            "/api/v1/ocr/validate/",
            data=json.dumps(
                {
                    "document_type": "payment_order",
                    "fields": {"document_number": "XX", "amount": "-1"},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(bad.json()["status"], STATUS_PENDING_REVIEW)
        self.assertFalse(bad.json()["validation"]["downstream_allowed"])

        good_body = {
            "document_type": "payment_order",
            "fields": {
                "document_number": "42",
                "date": "2026-07-20",
                "payer": "ООО Альфа",
                "beneficiary": "ООО Бета",
                "amount": "1500.00",
                "purpose": "оплата услуг",
            },
            "job_id": "ocrjob-api",
            "document_id": "doc-api",
        }
        good = client.post(
            "/api/v1/ocr/validate/",
            data=json.dumps(good_body),
            content_type="application/json",
        )
        self.assertEqual(good.status_code, 200)
        self.assertEqual(good.json()["status"], STATUS_VALID)

        export_json = client.post(
            "/api/v1/ocr/export/?format=json",
            data=json.dumps(good_body),
            content_type="application/json",
        )
        self.assertEqual(export_json.status_code, 200)
        self.assertEqual(export_json["X-DOC-T"], "DOC-T-08")
        self.assertIn("application/json", export_json["Content-Type"])
        exported = json.loads(export_json.content.decode("utf-8"))
        self.assertEqual(exported["status"], "valid")
        self.assertEqual(exported["fields"]["document_number"], "42")

        export_csv = client.post(
            "/api/v1/ocr/export/?format=csv",
            data=json.dumps(good_body),
            content_type="application/json",
        )
        self.assertEqual(export_csv.status_code, 200)
        self.assertIn("text/csv", export_csv["Content-Type"])
        self.assertIn(b"document_number", export_csv.content)
        self.assertIn(b"42", export_csv.content)

        blocked = client.post(
            "/api/v1/ocr/export/?format=json",
            data=json.dumps(
                {
                    "document_type": "passport",
                    "fields": {"series": "MP"},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(blocked.status_code, 400)

    def test_doc_t_subset_ids_documented(self):
        self.assertEqual(DOC_T_SUBSET, ("DOC-T-03", "DOC-T-04", "DOC-T-08"))
