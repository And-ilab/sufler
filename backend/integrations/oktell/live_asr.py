"""Turn 8 kHz PCM from SIP RTP into finals for the sufler window."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from django.conf import settings

from integrations.oktell.g711 import upsample_8k_to_16k

logger = logging.getLogger(__name__)

_CHUNK_BYTES_8K = 8000 * 2  # ~1 s of PCM16


def _model_path() -> Path | None:
    configured = str(getattr(settings, "VOSK_MODEL_PATH", "") or "").strip()
    candidates = []
    if configured:
        candidates.append(Path(configured))
    service_dir = Path(__file__).resolve().parents[2] / "services" / "asr"
    candidates.extend(
        [
            service_dir / "model" / "vosk-model-ru-0.22",
            service_dir.parents[2] / "recognizer" / "model" / "vosk-model-ru-0.22",
        ]
    )
    for path in candidates:
        if path.exists():
            return path
    return None


class LegTranscriber:
    """Buffer RTP PCM and emit Vosk finals. No-op if the model is missing."""

    def __init__(self, on_final: Callable[[str], None]) -> None:
        self.on_final = on_final
        self._buffer = bytearray()
        self._recognizer = None
        path = _model_path()
        if path is None:
            logger.warning("Vosk model missing; SIP audio will not become text")
            return
        try:
            from vosk import KaldiRecognizer, Model

            self._recognizer = KaldiRecognizer(Model(str(path)), 16000)
            self._recognizer.SetWords(True)
        except Exception:  # noqa: BLE001 — live path must not kill the call
            logger.exception("could not start Vosk for SIP leg")
            self._recognizer = None

    @property
    def ready(self) -> bool:
        return self._recognizer is not None

    def feed(self, pcm8k: bytes) -> None:
        if not pcm8k or self._recognizer is None:
            return
        self._buffer.extend(pcm8k)
        while len(self._buffer) >= _CHUNK_BYTES_8K:
            chunk = bytes(self._buffer[:_CHUNK_BYTES_8K])
            del self._buffer[:_CHUNK_BYTES_8K]
            self._accept(upsample_8k_to_16k(chunk))

    def _accept(self, pcm16k: bytes) -> None:
        assert self._recognizer is not None
        import json

        if self._recognizer.AcceptWaveform(pcm16k):
            payload = json.loads(self._recognizer.Result())
            text = str(payload.get("text") or "").strip()
            if text:
                self.on_final(text)

    def close(self) -> None:
        if self._recognizer is None:
            return
        import json

        leftover = bytes(self._buffer)
        self._buffer.clear()
        if leftover:
            self._accept(upsample_8k_to_16k(leftover))
        payload = json.loads(self._recognizer.FinalResult())
        text = str(payload.get("text") or "").strip()
        if text:
            self.on_final(text)
