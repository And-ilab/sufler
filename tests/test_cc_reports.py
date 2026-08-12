import os
import sys
import zipfile
from io import BytesIO
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


class CcReportsApiTest(TestCase):
    def user_for_role(self, role_code):
        role = ROLES_BY_CODE[role_code]
        user = get_user_model().objects.create_user(
            username=f"cc-rpt-{role_code}",
            password="test-password",
        )
        group, _ = Group.objects.get_or_create(name=role.mock_ad_group)
        user.groups.add(group)
        return user

    def test_analyst_gets_analytics_with_asr_charts(self):
        client = Client()
        client.force_login(self.user_for_role("contact_center_analyst"))

        response = client.get(
            "/api/reports/cc/analytics/",
            {
                "date_from": "2026-07-01",
                "date_to": "2026-07-07",
                "channel": "telephony",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["stub"])
        self.assertIn("summary", payload)
        self.assertGreater(len(payload["rows"]), 0)
        self.assertEqual(payload["filters"]["channel"], "telephony")
        self.assertTrue(
            all(row["channel"] == "telephony" for row in payload["rows"])
        )

        chat = client.get(
            "/api/reports/cc/analytics/",
            {
                "date_from": "2026-07-01",
                "date_to": "2026-07-07",
                "channel": "online_chat",
            },
        )
        self.assertEqual(chat.status_code, 200)
        chat_body = chat.json()
        self.assertEqual(chat_body["filters"]["channel"], "online_chat")
        self.assertIn("Онлайн-чат", chat_body["source"])

    def test_csv_and_xlsx_export_downloadable(self):
        client = Client()
        client.force_login(self.user_for_role("contact_center_analyst"))
        params = {
            "date_from": "2026-07-01",
            "date_to": "2026-07-03",
        }

        csv_response = client.get(
            "/api/reports/cc/export/",
            {**params, "format": "csv"},
        )
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("text/csv", csv_response["Content-Type"])
        self.assertIn("attachment", csv_response["Content-Disposition"])
        self.assertIn(b"date,channel,operator", csv_response.content)
        self.assertGreater(len(csv_response.content), 40)

        xlsx_response = client.get(
            "/api/reports/cc/export/",
            {**params, "format": "xlsx"},
        )
        self.assertEqual(xlsx_response.status_code, 200)
        self.assertIn(
            "spreadsheetml.sheet",
            xlsx_response["Content-Type"],
        )
        self.assertIn(".xlsx", xlsx_response["Content-Disposition"])
        with zipfile.ZipFile(BytesIO(xlsx_response.content)) as archive:
            names = archive.namelist()
            self.assertIn("xl/worksheets/sheet1.xml", names)
            sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
            self.assertIn("recognized_pct", sheet)

    @override_settings(DEBUG=False)
    def test_forbidden_without_reports_permission(self):
        client = Client()
        client.force_login(self.user_for_role("contact_center_telephony_operator"))
        response = client.get("/api/reports/cc/analytics/")
        self.assertIn(response.status_code, (401, 403))

    def test_live_and_catalog_endpoints(self):
        client = Client()
        client.force_login(self.user_for_role("contact_center_analyst"))

        live = client.get("/api/reports/cc/live/")
        self.assertEqual(live.status_code, 200)
        live_body = live.json()
        self.assertIn("kpis", live_body)
        self.assertIn("operators", live_body)

        catalog = client.get(
            "/api/reports/cc/catalog/",
            {"report": "chat-period", "date_from": "2026-07-01", "date_to": "2026-07-07"},
        )
        self.assertEqual(catalog.status_code, 200)
        catalog_body = catalog.json()
        self.assertEqual(catalog_body["report"]["id"], "chat-period")
        self.assertIn("catalog", catalog_body)
        self.assertTrue(any(item["id"] == "chat-sla" for item in catalog_body["catalog"]))

        builder = client.get("/api/reports/cc/builder/")
        self.assertEqual(builder.status_code, 200)
        self.assertIn("templates", builder.json())
        self.assertFalse(builder.json().get("stub", True))

        preview = client.post(
            "/api/reports/cc/builder/preview/",
            data='{"metrics":["dialogs_total","csat"],"name":"t"}',
            content_type="application/json",
        )
        self.assertEqual(preview.status_code, 200)
        self.assertIn("rows", preview.json())
