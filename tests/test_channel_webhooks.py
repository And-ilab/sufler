import json
import os
import sys
from pathlib import Path
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sufler.settings")

import django  # noqa: E402

django.setup()

from django.test import Client, TestCase  # noqa: E402

from integrations.channels.webhooks import reset_inbox  # noqa: E402
from online_chat.models import Dialog, TelegramOnboardingSession  # noqa: E402


class ChannelWebhooksTest(TestCase):
    def setUp(self):
        reset_inbox()
        self.client = Client()

    def _tg(self, text: str, chat_id: int = 4242, update_id: int = 1):
        return self.client.post(
            "/api/v1/channels/telegram/webhook/",
            data=json.dumps(
                {
                    "update_id": update_id,
                    "message": {
                        "message_id": update_id * 10,
                        "text": text,
                        "chat": {"id": chat_id, "type": "private"},
                        "from": {"id": chat_id, "first_name": "Анна"},
                    },
                }
            ),
            content_type="application/json",
        )

    @patch("online_chat.telegram_onboarding.send_telegram_text")
    def test_telegram_onboarding_then_queue(self, _send):
        start = self._tg("/start", update_id=1)
        self.assertEqual(start.status_code, 200)
        self.assertEqual(start.json()["routed_to"], "onboarding")
        self.assertEqual(Dialog.objects.count(), 0)

        question = self._tg("Лимит снятия наличных?", update_id=2)
        self.assertEqual(question.status_code, 200)
        self.assertEqual(question.json()["routed_to"], "onboarding")
        self.assertEqual(Dialog.objects.count(), 0)

        fio = self._tg("Козлова Анна", update_id=3)
        self.assertEqual(fio.status_code, 200)
        self.assertEqual(fio.json()["routed_to"], "onboarding")

        phone = self._tg("80291234567", update_id=4)
        self.assertEqual(phone.status_code, 200)
        body = phone.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["routed_to"], "arm_queue")
        self.assertEqual(Dialog.objects.count(), 1)
        dialog = Dialog.objects.get()
        self.assertEqual(dialog.channel, "telegram")
        self.assertEqual(dialog.client_phone, "+375291234567")
        self.assertEqual(dialog.client_first_name, "Анна")
        self.assertEqual(dialog.client_last_name, "Козлова")
        self.assertIn("Лимит снятия", dialog.preview)
        session = TelegramOnboardingSession.objects.get(chat_id="4242")
        self.assertEqual(session.step, TelegramOnboardingSession.Step.DONE)

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

    def test_vk_webhook_routes_message_to_dialog(self):
        response = self.client.post(
            "/api/v1/channels/vk/webhook/",
            data=json.dumps(
                {
                    "type": "message_new",
                    "event_id": "vk-event-1",
                    "object": {
                        "message": {
                            "peer_id": 777,
                            "text": "Вопрос из VK",
                        }
                    },
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Dialog.objects.filter(channel="vk", client_external_id="777").exists()
        )

    def test_ok_webhook_routes_message_to_dialog(self):
        response = self.client.post(
            "/api/v1/channels/ok/webhook/",
            data=json.dumps(
                {
                    "message": {
                        "sender_id": "ok-42",
                        "text": "Вопрос из OK",
                    }
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Dialog.objects.filter(channel="ok", client_external_id="ok-42").exists()
        )

    def test_signed_api_webhook_routes_message_to_dialog(self):
        response = self.client.post(
            "/api/v1/channels/api/webhook/",
            data=json.dumps(
                {
                    "client_external_id": "partner-client-1",
                    "text": "Вопрос из API",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Dialog.objects.filter(
                channel="api",
                client_external_id="partner-client-1",
            ).exists()
        )
