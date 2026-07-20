import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from core.model_gateway import (  # noqa: E402
    GatewayProfile,
    ModelGateway,
    ModelGatewayConfigurationError,
    STUB_RESPONSES,
)


class ModelGatewayTest(unittest.TestCase):
    def setUp(self):
        self.gateway = ModelGateway.from_registry()
        self.messages = [{"role": "user", "content": "Тестовый запрос"}]

    def test_registry_maps_all_profiles_to_expected_slots(self):
        expected = {
            "sufler_cc": "llm_sufler_cc",
            "assistant_bank": "llm_assistant_bank",
            "docs_ocr": "llm_docs_ocr",
        }

        for profile, slot_name in expected.items():
            with self.subTest(profile=profile):
                configured = self.gateway.get_profile(profile)
                self.assertEqual(configured.slot_name, slot_name)
                self.assertEqual(configured.gateway_mode, "stub")
                self.assertEqual(
                    configured.model,
                    f"stub:{profile}",
                )

    def test_dev_stub_returns_profile_specific_openai_response(self):
        responses = {
            profile: self.gateway.chat(profile, self.messages)
            for profile in STUB_RESPONSES
        }

        for profile, response in responses.items():
            with self.subTest(profile=profile):
                self.assertEqual(response["object"], "chat.completion")
                self.assertEqual(response["model"], f"stub:{profile}")
                self.assertEqual(
                    response["choices"][0]["message"]["content"],
                    STUB_RESPONSES[profile],
                )
                self.assertEqual(
                    response["choices"][0]["finish_reason"],
                    "stop",
                )
        self.assertEqual(
            len(
                {
                    response["choices"][0]["message"]["content"]
                    for response in responses.values()
                }
            ),
            3,
        )

    def test_stub_stream_is_valid_sse_and_reconstructs_content(self):
        events = list(self.gateway.stream("sufler_cc", self.messages))

        self.assertEqual(events[-1], "data: [DONE]\n\n")
        chunks = [
            json.loads(event.removeprefix("data: ").strip())
            for event in events[:-1]
        ]
        content = "".join(
            chunk["choices"][0]["delta"].get("content", "")
            for chunk in chunks
        )
        self.assertEqual(content, STUB_RESPONSES["sufler_cc"])
        self.assertEqual(
            chunks[0]["choices"][0]["delta"]["role"],
            "assistant",
        )
        self.assertEqual(
            chunks[-1]["choices"][0]["finish_reason"],
            "stop",
        )

    def test_assistant_stub_returns_openai_tool_call(self):
        response = self.gateway.chat(
            "assistant_bank",
            self.messages,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "get_exchange_rate",
                        "parameters": {"type": "object"},
                    },
                }
            ],
            tool_choice="auto",
        )

        choice = response["choices"][0]
        tool_call = choice["message"]["tool_calls"][0]
        self.assertEqual(choice["finish_reason"], "tool_calls")
        self.assertEqual(tool_call["type"], "function")
        self.assertEqual(
            tool_call["function"]["name"],
            "get_exchange_rate",
        )
        self.assertEqual(
            json.loads(tool_call["function"]["arguments"]),
            {"currency": "USD"},
        )

    def test_unknown_profile_and_reserved_parameter_are_rejected(self):
        with self.assertRaises(ModelGatewayConfigurationError):
            self.gateway.chat("unknown", self.messages)
        with self.assertRaises(ModelGatewayConfigurationError):
            self.gateway.chat(
                "sufler_cc",
                self.messages,
                model="override",
            )

    def test_openai_mode_posts_compatible_payload(self):
        configured = GatewayProfile(
            profile="sufler_cc",
            slot_name="llm_sufler_cc",
            model="vendor-model",
            gateway_mode="openai",
            api_compatibility="openai",
            kpi={},
        )
        gateway = ModelGateway(
            self.gateway._registry,
            mode="openai",
            base_url="http://llm.internal/v1",
            api_key="test-key",
        )
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "id": "chatcmpl-real",
            "object": "chat.completion",
            "choices": [],
        }

        with (
            patch.object(
                gateway,
                "get_profile",
                return_value=configured,
            ),
            patch(
                "core.model_gateway.requests.post",
                return_value=response,
            ) as post,
        ):
            result = gateway.chat(
                "sufler_cc",
                self.messages,
                temperature=0.2,
            )

        self.assertEqual(result["id"], "chatcmpl-real")
        post.assert_called_once()
        call = post.call_args
        self.assertEqual(
            call.args[0],
            "http://llm.internal/v1/chat/completions",
        )
        self.assertEqual(call.kwargs["json"]["model"], "vendor-model")
        self.assertEqual(call.kwargs["json"]["messages"], self.messages)
        self.assertFalse(call.kwargs["json"]["stream"])
        self.assertEqual(call.kwargs["json"]["temperature"], 0.2)
        self.assertEqual(
            call.kwargs["headers"]["Authorization"],
            "Bearer test-key",
        )


if __name__ == "__main__":
    unittest.main()
