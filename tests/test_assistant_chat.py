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

from assistant.openapi import (  # noqa: E402
    SCHEMA_PATH,
    build_openapi_document,
    generate_openapi_yaml,
)
from auth.roles import ROLES_BY_CODE  # noqa: E402
from core.model_gateway import STUB_RESPONSES  # noqa: E402


def parse_sse_content(raw: bytes | str) -> tuple[str, bool]:
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    content = ""
    done = False
    for block in text.split("\n\n"):
        block = block.strip("\n")
        if not block or block.startswith(":"):
            continue
        if not block.startswith("data:"):
            continue
        payload = block[len("data:") :].strip()
        if payload == "[DONE]":
            done = True
            continue
        chunk = json.loads(payload)
        delta = chunk["choices"][0]["delta"]
        content += delta.get("content") or ""
    return content, done


class AssistantChatApiTest(TestCase):
    url = "/api/v1/assistant/chat"

    def user_for_role(self, role_code):
        role = ROLES_BY_CODE[role_code]
        user = get_user_model().objects.create_user(
            username=f"assistant-chat-{role_code}",
            password="test-password",
        )
        group, _ = Group.objects.get_or_create(name=role.mock_ad_group)
        user.groups.add(group)
        return user

    def test_chat_roundtrip_streams_assistant_bank_tokens(self):
        client = Client()
        client.force_login(self.user_for_role("ai_assistant_user"))

        response = client.post(
            self.url,
            data=json.dumps(
                {
                    "message": "Нужна справка о вкладе",
                    "session_id": "sess-roundtrip-1",
                    "stream": True,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response["Content-Type"])
        self.assertEqual(response["X-Assistant-Profile"], "assistant_bank")
        self.assertEqual(response["X-Session-ID"], "sess-roundtrip-1")

        raw = b"".join(response.streaming_content)
        content, done = parse_sse_content(raw)
        self.assertTrue(done)
        self.assertEqual(content, STUB_RESPONSES["assistant_bank"])
        self.assertIn("ассистент", content.casefold())

    def test_messages_history_roundtrip(self):
        client = Client()
        client.force_login(self.user_for_role("ai_assistant_user"))
        response = client.post(
            self.url,
            data=json.dumps(
                {
                    "messages": [
                        {"role": "user", "content": "Привет"},
                        {"role": "assistant", "content": "Здравствуйте"},
                        {"role": "user", "content": "Лимит перевода?"},
                    ]
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        content, done = parse_sse_content(b"".join(response.streaming_content))
        self.assertTrue(done)
        self.assertEqual(content, STUB_RESPONSES["assistant_bank"])

    def test_validation_and_rbac(self):
        client = Client()
        client.force_login(self.user_for_role("ai_assistant_user"))
        bad = client.post(
            self.url,
            data=json.dumps({"messages": []}),
            content_type="application/json",
        )
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.json()["error"], "validation_error")

        denied = Client()
        denied.force_login(
            self.user_for_role("contact_center_internal_user")
        )
        response = denied.post(
            self.url,
            data=json.dumps({"message": "hello"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_openapi_schema_generated_and_served(self):
        document = build_openapi_document()
        self.assertEqual(document["openapi"], "3.0.3")
        self.assertIn("/chat", document["paths"])
        self.assertEqual(
            document["paths"]["/chat"]["post"]["operationId"],
            "assistantChatStream",
        )

        written = generate_openapi_yaml()
        self.assertEqual(written, SCHEMA_PATH)
        self.assertTrue(SCHEMA_PATH.exists())
        self.assertIn("/chat", SCHEMA_PATH.read_text(encoding="utf-8"))

        client = Client()
        response = client.get("/api/v1/assistant/openapi.json")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["info"]["title"], "AI Assistant API")
        self.assertIn("/chat", body["paths"])
