"""Local STT for sufler imitation: Vosk on uploaded PCM WAV."""

from __future__ import annotations

import json
import os
import struct
from pathlib import Path
from typing import Any

MAX_AUDIO_BYTES = 2_000_000


class TranscribeError(ValueError):
    """Raised when uploaded audio cannot be transcribed."""


def _read_wav_pcm16(data: bytes) -> tuple[bytes, int]:
    if len(data) < 44 or data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise TranscribeError("audio must be a PCM WAV file")
    offset = 12
    channels = 1
    sample_rate = 16000
    bits = 16
    pcm = b""
    while offset + 8 <= len(data):
        chunk_id = data[offset : offset + 4]
        chunk_size = struct.unpack_from("<I", data, offset + 4)[0]
        start = offset + 8
        end = start + chunk_size
        if chunk_id == b"fmt " and chunk_size >= 16:
            audio_format, channels, sample_rate, _, _, bits = struct.unpack_from(
                "<HHIIHH",
                data,
                start,
            )
            if audio_format != 1:
                raise TranscribeError("WAV must be uncompressed PCM")
            if channels != 1:
                raise TranscribeError("WAV must be mono")
            if bits != 16:
                raise TranscribeError("WAV must be 16-bit")
        elif chunk_id == b"data":
            pcm = data[start:end]
            break
        offset = end + (chunk_size % 2)
    if not pcm:
        raise TranscribeError("WAV has no PCM data")
    if sample_rate not in {8000, 16000, 22050, 44100, 48000}:
        raise TranscribeError(f"unsupported sample rate: {sample_rate}")
    return pcm, sample_rate


def _vosk_model_path() -> Path | None:
    configured = os.environ.get("VOSK_MODEL_PATH", "").strip()
    candidates = [
        Path(configured).expanduser() if configured else None,
        Path(__file__).resolve().parents[1]
        / "services"
        / "asr"
        / "model"
        / "vosk-model-small-ru-0.22",
        Path(__file__).resolve().parents[2]
        / "recognizer"
        / "model"
        / "vosk-model-ru-0.22",
    ]
    for candidate in candidates:
        if candidate is not None and candidate.exists():
            return candidate
    return None


def _transcribe_vosk(pcm: bytes, sample_rate: int) -> str:
    model_path = _vosk_model_path()
    if model_path is None:
        return ""
    try:
        from vosk import KaldiRecognizer, Model
    except ImportError:
        return ""
    rec = KaldiRecognizer(Model(str(model_path)), sample_rate)
    rec.SetWords(True)
    rec.AcceptWaveform(pcm)
    payload: dict[str, Any] = json.loads(rec.FinalResult())
    return str(payload.get("text") or "").strip()


def transcribe_wav(data: bytes) -> str:
    if not data:
        raise TranscribeError("audio is empty")
    if len(data) > MAX_AUDIO_BYTES:
        raise TranscribeError("audio is too large")
    pcm, sample_rate = _read_wav_pcm16(data)
    text = _transcribe_vosk(pcm, sample_rate)
    if text:
        return text
    raise TranscribeError("could not recognize speech")
