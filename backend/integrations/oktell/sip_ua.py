"""Plan (and optionally place) SIP barge calls 02*/03*1xxx from 2xxx accounts."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from integrations.oktell.sip_pool import SipAccount
from integrations.oktell.webhook import listen_codes

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SipDial:
    speaker: str
    code: str
    target: str
    account: SipAccount

    def as_dict(self) -> dict[str, str]:
        return {
            "speaker": self.speaker,
            "code": self.code,
            "target": self.target,
            "sip_user": self.account.user,
            "sip_uri": self.account.uri,
        }


def plan_dual_leg(called_id: str, client_account: SipAccount, operator_account: SipAccount) -> list[SipDial]:
    codes = listen_codes(called_id)
    host = client_account.server or "oktell"
    return [
        SipDial(
            speaker="client",
            code="02",
            target=f"sip:{codes['client']}@{host}",
            account=client_account,
        ),
        SipDial(
            speaker="operator",
            code="03",
            target=f"sip:{codes['operator']}@{host}",
            account=operator_account,
        ),
    ]


def invite_summary(dials: list[SipDial]) -> list[dict[str, str]]:
    """What we would send to the PBX. Real REGISTER/INVITE needs network + vault passwords."""
    planned = [dial.as_dict() for dial in dials]
    for row in planned:
        logger.info(
            "Oktell SIP barge planned user=%s target=%s",
            row["sip_user"],
            row["target"],
        )
    return planned
