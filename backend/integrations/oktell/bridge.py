"""Push ASR text into the sufler window WebSocket (call_id = Idchain)."""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from orchestrator.sufler import SuflerOrchestratorError, suggest

logger = logging.getLogger(__name__)


def sufler_group(call_id: str) -> str:
    safe = "".join(char if char.isalnum() or char in "-_" else "-" for char in call_id)
    return f"sufler_call_{safe}"


def publish_to_call(call_id: str, payload: dict[str, Any]) -> None:
    try:
        from integrations.oktell.call_hub import hub

        hub.record_event(call_id, payload)
    except Exception:  # noqa: BLE001 — replay must not break live publish
        logger.debug("could not record oktell event for %s", call_id, exc_info=True)
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning("no channel layer; drop sufler event call_id=%s", call_id)
        return
    async_to_sync(channel_layer.group_send)(
        sufler_group(call_id),
        {"type": "sufler.event", "payload": payload},
    )


def publish_transcript(
    call_id: str,
    *,
    speaker: str,
    text: str,
    turn_id: str,
    is_final: bool = True,
) -> None:
    cleaned = text.strip()
    if not cleaned:
        return
    publish_to_call(
        call_id,
        {
            "type": "transcript",
            "speaker": speaker,
            "text": cleaned,
            "is_final": is_final,
            "turn_id": turn_id,
        },
    )
    if not (is_final and speaker == "client"):
        return
    try:
        result = suggest(
            cleaned,
            limit=5,
            session_id=call_id,
            channel="telephony",
        )
    except (SuflerOrchestratorError, RuntimeError, ValueError, KeyError, TypeError) as exc:
        logger.warning("suggest failed for call %s: %s", call_id, exc)
        publish_to_call(
            call_id,
            {
                "type": "error",
                "message": str(exc),
                "turn_id": turn_id,
            },
        )
        return
    publish_to_call(
        call_id,
        {
            "type": "hints",
            "turn_id": turn_id,
            "query": result["query"],
            "hints": result["hints"][:5],
            "latency_ms": result["latency_ms"],
            "request_id": result["request_id"],
            "blocked_reason": result.get("blocked_reason"),
            "scenario": result.get("scenario"),
            "suggested_scenario": result.get("suggested_scenario"),
        },
    )
