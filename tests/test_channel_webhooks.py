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

from django.test import Client, TestCase  # noqa: E402

from integrations.channels.webhooks import reset_inbox  # noqa: E402


class ChannelWebhooksTest(TestCase):
    def setUp(self):
        reset_inbox()
        self.client = Client()

    def test_telegram_webhook_routes_to_arm_queue(self):
        response = self.client.post(
            "/api/v1/channels/telegram/webhook/",
            data=json.dumps(
                {
                    "update_id": 1,
                    "message": {
                        "message_id": 10,
                        "text": "Лимит снятия наличных?",
                        "chat": {"id": 4242, "type": "private"},
                        "from": {"id": 4242, "first_name": "Анна"},
                    },
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["channel"], "telegram")
        self.assertEqual(body["routed_to"], "arm_queue")
        self.assertIn("sendMessage", body["reply"]["method"])

    def test_viber_webhook_message_and_handshake(self):
        handshake = self.client.post(
            "/api/v1/channels/viber/webhook/",
            data=json.dumps({"event": "webhook", "timestamp": 1}),
            content_type="application/json",
        )
        self.assertEqual(handshake.status_code, 200)
        self.assertEqual(handshake.json()["status"], 0)

        response = self.client.post(
            "/api/v1/channels/viber/webhook/",
            data=json.dumps(
                {
                    "event": "message",
                    "sender": {"id": "viber-user-1", "name": "Пётр"},
                    "message": {"type": "text", "text": "Не приходит SMS"},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["channel"], "viber")
        self.assertEqual(body["routed_to"], "arm_queue")

    def test_widget_message_accepts_widget_id(self):
        response = self.client.post(
            "/api/v1/channels/widget/site-belarusbank/messages/",
            data=json.dumps(
                {
                    "text": "Здравствуйте",
                    "placement": "website",
                    "locale": "ru",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["widget_id"], "site-belarusbank")
        self.assertTrue(body["reply"])

        inbox = self.client.get("/api/v1/channels/inbox/")
        self.assertEqual(inbox.status_code, 200)
        self.assertGreaterEqual(inbox.json()["count"], 1)
