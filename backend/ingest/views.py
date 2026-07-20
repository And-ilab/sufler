from __future__ import annotations

import json

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from kombu.exceptions import OperationalError

from ingest.pipeline import checksum_for_text, normalize_text
from ingest.schema import SuzPayload, SuzPayloadError
from ingest.signature import verify_hmac_signature
from ingest.tasks import enqueue_ingest_chain


@csrf_exempt
@require_POST
def knowledge_events(request: HttpRequest) -> JsonResponse:
    """Receive SUZ Model B events for INT-01..05 and INT-07."""
    secret = settings.SUZ_WEBHOOK_HMAC_SECRET
    if not verify_hmac_signature(
        request.body,
        request.headers.get("X-Sufler-Signature", ""),
        secret,
    ):
        return JsonResponse({"error": "auth"}, status=401)

    try:
        raw_payload = json.loads(request.body)
        if not isinstance(raw_payload, dict):
            raise ValueError
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return JsonResponse(
            {"error": "validation", "fields": ["body"]},
            status=400,
        )

    try:
        payload = SuzPayload.from_mapping(raw_payload)
        header_event_id = request.headers.get("X-Sufler-Event-Id")
        if header_event_id and header_event_id != str(payload.event_id):
            raise SuzPayloadError(["X-Sufler-Event-Id"])
        if (
            payload.event_type == "article.version_published"
            and checksum_for_text(
                normalize_text(payload.body_plain, payload.body_html)
            )
            != payload.checksum
        ):
            raise SuzPayloadError(["checksum"])
    except SuzPayloadError as exc:
        return JsonResponse(
            {"error": "validation", "fields": exc.fields},
            status=400,
        )

    try:
        result = enqueue_ingest_chain(raw_payload)
    except OperationalError:
        return JsonResponse({"error": "temporary"}, status=503)

    return JsonResponse(
        {
            "status": "accepted",
            "event_id": str(payload.event_id),
            "outcome": "queued",
            "task_id": result.id,
        },
        status=202,
    )
