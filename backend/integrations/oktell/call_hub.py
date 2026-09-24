"""In-memory multi-call hub: one pickup → two listen instances (02* / 03*)."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from integrations.oktell.bridge import publish_to_call, publish_transcript
from integrations.oktell.sip_pool import (
    SipAccount,
    account_pool,
    listen_mode,
    mock_client_text,
    mock_operator_text,
)
from integrations.oktell.sip_ua import invite_summary, place_barge_leg, plan_dual_leg
from integrations.oktell.sip_dialog import SipDialogError
from integrations.oktell.webhook import PickupEvent, listen_codes

logger = logging.getLogger(__name__)


@dataclass
class ListenLeg:
    speaker: str
    dial: str
    sip_user: str
    status: str = "idle"

    def as_dict(self) -> dict[str, str]:
        return {
            "speaker": self.speaker,
            "dial": self.dial,
            "sip_user": self.sip_user,
            "status": self.status,
        }


@dataclass
class LiveCall:
    pickup: PickupEvent
    legs: list[ListenLeg]
    state: str = "started"
    listen_mode: str = "mock"
    created_at: float = field(default_factory=time.time)
    stop_event: threading.Event = field(default_factory=threading.Event)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def idchain(self) -> str:
        return self.pickup.idchain

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.pickup.as_dict(),
            "state": self.state,
            "listen_mode": self.listen_mode,
            "created_at": self.created_at,
            "legs": [leg.as_dict() for leg in self.legs],
            "sufler_ws": f"/ws/sufler/{self.idchain}/",
            "events": list(self.events),
        }


class CallHub:
    """Several instances: one LiveCall per Idchain, two SIP legs each."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: dict[str, LiveCall] = {}
        self._next_account = 0

    def reset(self) -> None:
        with self._lock:
            for call in self._calls.values():
                call.stop_event.set()
            self._calls.clear()
            self._next_account = 0

    def list_calls(self) -> list[LiveCall]:
        with self._lock:
            return list(self._calls.values())

    def get(self, idchain: str) -> LiveCall | None:
        with self._lock:
            return self._calls.get(idchain)

    def record_event(self, idchain: str, payload: dict[str, Any]) -> None:
        with self._lock:
            call = self._calls.get(idchain)
            if call is None:
                return
            call.events.append(dict(payload))

    def allocate_accounts(self, count: int = 2) -> list[SipAccount]:
        pool = account_pool()
        if len(pool) < count:
            raise RuntimeError("OKTELL_SIP_USER_COUNT is too small for dual-leg")
        with self._lock:
            chosen: list[SipAccount] = []
            for _ in range(count):
                chosen.append(pool[self._next_account % len(pool)])
                self._next_account += 1
            return chosen

    def start(self, pickup: PickupEvent) -> tuple[LiveCall, bool]:
        with self._lock:
            existing = self._calls.get(pickup.idchain)
            others = [
                call.idchain
                for call in self._calls.values()
                if call.state != "stopped" and call.idchain != pickup.idchain
            ]
        if existing is not None and existing.state != "stopped":
            return existing, False
        for idchain in others:
            self.stop(idchain)

        client_account, operator_account = self.allocate_accounts(2)
        codes = listen_codes(pickup.called_id)
        call = LiveCall(
            pickup=pickup,
            listen_mode=listen_mode(),
            legs=[
                ListenLeg("client", codes["client"], client_account.user),
                ListenLeg("operator", codes["operator"], operator_account.user),
            ],
        )
        dials = plan_dual_leg(pickup.called_id, client_account, operator_account)
        invite_summary(dials)

        with self._lock:
            self._calls[pickup.idchain] = call

        self._spawn_call(call, client_account, operator_account)
        return call, True

    def _spawn_call(
        self,
        call: LiveCall,
        client_account: SipAccount | None,
        operator_account: SipAccount | None,
    ) -> None:
        worker = threading.Thread(
            target=self._run_call,
            args=(call, client_account, operator_account),
            name=f"oktell-call-{call.idchain[:8]}",
            daemon=True,
        )
        worker.start()

    def stop(self, idchain: str) -> LiveCall | None:
        with self._lock:
            call = self._calls.get(idchain)
        if call is None:
            return None
        call.stop_event.set()
        call.state = "stopped"
        for leg in call.legs:
            if leg.status != "error":
                leg.status = "stopped"
        publish_to_call(
            idchain,
            {"type": "status", "status": "stopped", "call_id": idchain},
        )
        return call

    def _run_call(
        self,
        call: LiveCall,
        client_account: SipAccount | None,
        operator_account: SipAccount | None,
    ) -> None:
        call.state = "listening"
        for leg in call.legs:
            leg.status = "dialing" if call.listen_mode == "sip" else "mock"
        publish_to_call(
            call.idchain,
            {
                "type": "status",
                "status": "listening",
                "call_id": call.idchain,
                "caller_id": call.pickup.caller_id,
                "called_id": call.pickup.called_id,
            },
        )
        if call.listen_mode == "mock":
            self._run_mock_utterances(call)
            return
        if client_account is None or operator_account is None:
            logger.warning("SIP barge missing accounts for %s", call.idchain)
            call.stop_event.wait(timeout=3600)
            return
        self._run_sip_legs(call, client_account, operator_account)

    def _run_sip_legs(
        self,
        call: LiveCall,
        client_account: SipAccount,
        operator_account: SipAccount,
    ) -> None:
        if not client_account.password or not operator_account.password:
            logger.warning(
                "OKTELL_LISTEN_MODE=sip but SIP password empty user=%s/%s",
                client_account.user,
                operator_account.user,
            )
        dials = plan_dual_leg(call.pickup.called_id, client_account, operator_account)
        invite_summary(dials)
        workers: list[threading.Thread] = []
        for dial, leg in zip(dials, call.legs, strict=False):
            worker = threading.Thread(
                target=self._run_one_sip_leg,
                args=(call, dial, leg),
                name=f"oktell-sip-{dial.account.user}",
                daemon=True,
            )
            workers.append(worker)
            worker.start()
        call.stop_event.wait(timeout=3600)
        call.stop_event.set()
        for worker in workers:
            worker.join(timeout=5)
        if call.state != "stopped":
            call.state = "stopped"

    def _run_one_sip_leg(self, call: LiveCall, dial, leg: ListenLeg) -> None:
        turn = 0

        def on_final(text: str) -> None:
            nonlocal turn
            turn += 1
            publish_transcript(
                call.idchain,
                speaker=leg.speaker,
                text=text,
                turn_id=f"{call.idchain}-{leg.speaker}-{turn}",
            )
            leg.status = "heard"

        try:
            status = place_barge_leg(dial, stop_event=call.stop_event, on_final=on_final)
            if leg.status != "heard":
                leg.status = status
        except SipDialogError as exc:
            logger.warning("SIP barge failed %s %s: %s", dial.account.user, dial.target, exc)
            leg.status = "error"
            publish_to_call(
                call.idchain,
                {
                    "type": "error",
                    "message": str(exc),
                    "speaker": leg.speaker,
                    "sip_user": dial.account.user,
                },
            )

    def _run_mock_utterances(self, call: LiveCall) -> None:
        if call.stop_event.is_set():
            return
        operator_text = mock_operator_text()
        if operator_text:
            publish_transcript(
                call.idchain,
                speaker="operator",
                text=operator_text,
                turn_id=f"{call.idchain}-op",
            )
        client_text = mock_client_text()
        if client_text:
            publish_transcript(
                call.idchain,
                speaker="client",
                text=client_text,
                turn_id=f"{call.idchain}-cl",
            )
        for leg in call.legs:
            if leg.speaker == "client":
                leg.status = "heard"
            elif operator_text:
                leg.status = "heard"
            else:
                leg.status = "idle"


hub = CallHub()
