"""Acceptance: widget dialogs with first/last name reach ARM online-chat API."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sufler.settings")

import django

django.setup()

from django.test import Client, TestCase

from tests.acceptance.fixtures import post_json


class OnlineChatApiAcceptanceTest(TestCase):
    def test_widget_dialog_stores_first_and_last_name(self):
        client = Client()
        response = post_json(
            client,
            "/api/v1/online-chat/dialogs/",
            {
                "text": "Подскажите лимит снятия?",
                "widget_id": "site-belarusbank",
                "placement": "website",
                "first_name": "Анна",
                "last_name": "Козлова",
                "phone": "+375 29 123-45-67",
            },
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["ok"])
        dialog = body["dialog"]
        self.assertEqual(dialog["client_first_name"], "Анна")
        self.assertEqual(dialog["client_last_name"], "Козлова")
        self.assertEqual(dialog["client_name"], "Анна Козлова")
        self.assertEqual(dialog["client_phone"], "+375 29 123-45-67")
        self.assertEqual(dialog["status"], "waiting")
        self.assertGreaterEqual(len(dialog.get("messages") or []), 1)

        inbox = client.get("/api/v1/online-chat/dialogs/?status=waiting")
        self.assertEqual(inbox.status_code, 200)
        payload = inbox.json()
        self.assertGreaterEqual(payload["count"], 1)
        card = next(item for item in payload["items"] if item["id"] == dialog["id"])
        self.assertEqual(card["client_last_name"], "Козлова")
        self.assertIn("лимит", card["preview"].lower())

        accept = post_json(
            client,
            f"/api/v1/online-chat/dialogs/{dialog['id']}/accept/",
            {"operator_name": "Иванов И.И."},
        )
        self.assertEqual(accept.status_code, 200)
        self.assertEqual(accept.json()["dialog"]["status"], "active")


if __name__ == "__main__":
    unittest.main()
