"""Vendor pickup POST + dual-leg 02*/03* instances (Подслушивание.pdf)."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sufler.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Group  # noqa: E402
from django.test import Client, SimpleTestCase, TestCase, override_settings  # noqa: E402

from auth.roles import ROLES_BY_CODE  # noqa: E402
from integrations.oktell.call_hub import hub  # noqa: E402
from integrations.oktell.g711 import alaw_to_pcm16, rtp_payload_to_pcm16  # noqa: E402
from integrations.oktell.sip_dialog import (  # noqa: E402
    SipAuth,
    digest_response,
    parse_authenticate,
    parse_sdp_audio,
)
from integrations.oktell.sip_ua import plan_dual_leg  # noqa: E402
from integrations.oktell.sip_pool import SipAccount, parse_password_map  # noqa: E402
from integrations.oktell.webhook import listen_codes, parse_pickup_payload  # noqa: E402


INCOMING = {
    "CallerID": "375336664177",
    "CalledID": "1001",
    "Idchain": "affcc4a7-5bbc-4206-97e2-74d18ba4cb30",
    "op_name": "Администратор",
    "call_type": "in",
}


class SipEnvExportTest(SimpleTestCase):
    def test_env_text_contains_json_users(self):
        sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))
        from export_oktell_sip_env import env_text

        text = env_text([("2001", "p1"), ("2002", "p2")], count=2)
        self.assertIn("OKTELL_LISTEN_MODE=sip", text)
        self.assertIn("2001", text)
        self.assertIn("p1", text)


class PickupParseTest(SimpleTestCase):
    def test_vendor_json(self):
        event = parse_pickup_payload(INCOMING)
        self.assertEqual(event.called_id, "1001")
        self.assertEqual(listen_codes(event.called_id)["client"], "02*1001")
        self.assertEqual(listen_codes(event.called_id)["operator"], "03*1001")

    def test_password_map(self):
        mapping = parse_password_map("2001:one,2002:two")
        self.assertEqual(mapping["2001"], "one")


class DualLegPlanTest(SimpleTestCase):
    def test_two_instances(self):
        client = SipAccount("2001", "", "dev-qms.onedemoserver.online", "10.1.1.181")
        operator = SipAccount("2002", "", "dev-qms.onedemoserver.online", "10.1.1.181")
        dials = plan_dual_leg("1001", client, operator)
        self.assertEqual([item.speaker for item in dials], ["client", "operator"])
        self.assertTrue(dials[0].target.startswith("sip:02*1001@"))
        self.assertTrue(dials[1].target.startswith("sip:03*1001@"))
        self.assertEqual(dials[0].account.user, "2001")
        self.assertEqual(dials[1].account.user, "2002")


class SipCodecTest(SimpleTestCase):
    def test_alaw_pcm_length(self):
        pcm = alaw_to_pcm16(bytes([0xD5, 0x55]))
        self.assertEqual(len(pcm), 4)
        self.assertEqual(rtp_payload_to_pcm16(b"\xd5", 8), alaw_to_pcm16(b"\xd5"))

    def test_digest_and_sdp(self):
        auth = parse_authenticate(
            'Digest realm="oktell", nonce="abc", algorithm=MD5'
        )
        self.assertEqual(auth.realm, "oktell")
        self.assertEqual(
            digest_response(
                username="2001",
                password="secret",
                method="REGISTER",
                uri="sip:oktell",
                auth=SipAuth(realm="oktell", nonce="abc"),
            ),
            digest_response(
                username="2001",
                password="secret",
                method="REGISTER",
                uri="sip:oktell",
                auth=SipAuth(realm="oktell", nonce="abc"),
            ),
        )
        host, port, payload = parse_sdp_audio(
            "v=0\r\nc=IN IP4 10.1.1.31\r\nm=audio 18000 RTP/AVP 8 0\r\n"
        )
        self.assertEqual((host, port, payload), ("10.1.1.31", 18000, 8))


class OktellWebhookTest(TestCase):
    def setUp(self):
        hub.reset()

    def tearDown(self):
        hub.reset()

    @override_settings(OKTELL_LISTEN_MODE="mock", OKTELL_WEBHOOK_SECRET="")
    def test_pickup_starts_two_legs(self):
        client = Client()
        with patch("integrations.oktell.call_hub.publish_transcript"), patch(
            "integrations.oktell.call_hub.publish_to_call"
        ):
            response = client.post(
                "/api/v1/telephony/oktell/call-started",
                data=json.dumps(INCOMING),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 201)
        body = response.json()["call"]
        self.assertEqual(body["Idchain"], INCOMING["Idchain"])
        self.assertEqual([leg["dial"] for leg in body["legs"]], ["02*1001", "03*1001"])
        self.assertEqual({leg["sip_user"] for leg in body["legs"]}, {"2001", "2002"})
        detail = client.get(
            f"/api/v1/telephony/oktell/calls/{INCOMING['Idchain']}"
        )
        self.assertEqual(detail.status_code, 200)

        with patch("integrations.oktell.call_hub.publish_transcript"), patch(
            "integrations.oktell.call_hub.publish_to_call"
        ):
            again = client.post(
                "/api/v1/telephony/oktell/call-started",
                data=json.dumps(INCOMING),
                content_type="application/json",
            )
        self.assertEqual(again.status_code, 200)
        self.assertFalse(again.json()["created"])

    @override_settings(OKTELL_LISTEN_MODE="mock", OKTELL_WEBHOOK_SECRET="")
    def test_two_calls_use_four_sip_users(self):
        client = Client()
        second = {**INCOMING, "Idchain": "second-chain", "CalledID": "1002"}
        with patch("integrations.oktell.call_hub.publish_transcript"), patch(
            "integrations.oktell.call_hub.publish_to_call"
        ):
            first = client.post(
                "/api/v1/telephony/oktell/call-started",
                data=json.dumps(INCOMING),
                content_type="application/json",
            )
            other = client.post(
                "/api/v1/telephony/oktell/call-started",
                data=json.dumps(second),
                content_type="application/json",
            )
        users = {
            leg["sip_user"]
            for payload in (first.json()["call"], other.json()["call"])
            for leg in payload["legs"]
        }
        self.assertEqual(users, {"2001", "2002", "2003", "2004"})
        self.assertEqual(len(hub.list_calls()), 2)

    @override_settings(OKTELL_WEBHOOK_SECRET="s3cret", OKTELL_LISTEN_MODE="mock")
    def test_secret_required(self):
        client = Client()
        denied = client.post(
            "/api/v1/telephony/oktell/call-started",
            data=json.dumps(INCOMING),
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 401)
        with patch("integrations.oktell.call_hub.publish_transcript"), patch(
            "integrations.oktell.call_hub.publish_to_call"
        ):
            allowed = client.post(
                "/api/v1/telephony/oktell/call-started",
                data=json.dumps(INCOMING),
                content_type="application/json",
                HTTP_X_OKTELL_TOKEN="s3cret",
            )
        self.assertEqual(allowed.status_code, 201)

    @override_settings(
        OKTELL_LISTEN_MODE="sip",
        OKTELL_WEBHOOK_SECRET="",
        OKTELL_SIP_PASSWORDS_JSON='{"2001":"x","2002":"y"}',
        OKTELL_SIP_USER_COUNT=8,
    )
    def test_sip_mode_does_not_emit_mock_phrase(self):
        client = Client()
        with patch(
            "integrations.oktell.call_hub.place_barge_leg", return_value="listening"
        ) as barge, patch(
            "integrations.oktell.call_hub.publish_transcript"
        ) as published:
            response = client.post(
                "/api/v1/telephony/oktell/call-started",
                data=json.dumps({**INCOMING, "Idchain": "sip-live-1"}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()["call"]["listen_mode"], "sip")
            deadline = time.time() + 2
            while barge.call_count < 2 and time.time() < deadline:
                time.sleep(0.05)
            hub.stop("sip-live-1")
        self.assertEqual(barge.call_count, 2)
        texts = [call.kwargs.get("text") for call in published.call_args_list]
        self.assertNotIn(
            "Подскажите, как оформить перевод в Россию через мобильный банк?",
            texts,
        )

    def test_list_requires_operator(self):
        role = ROLES_BY_CODE["contact_center_telephony_operator"]
        user = get_user_model().objects.create_user("op-oktell", password="x")
        group, _ = Group.objects.get_or_create(name=role.mock_ad_group)
        user.groups.add(group)
        client = Client()
        self.assertEqual(client.get("/api/v1/telephony/oktell/calls").status_code, 401)
        client.force_login(user)
        listed = client.get("/api/v1/telephony/oktell/calls")
        self.assertEqual(listed.status_code, 200)
        self.assertIn("calls", listed.json())
