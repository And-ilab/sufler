"""Validated loader for the YAML model-slot registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "model_registry.yaml"
)
REQUIRED_SLOTS = frozenset(
    {
        "asr",
        "embedding",
        "qu",
        "llm_sufler_cc",
        "llm_assistant_bank",
        "llm_docs_ocr",
        "ocr",
        "reranker",
    }
)
REQUIRED_FIELDS = frozenset(
    {"dev_model", "prod_candidate", "kpi", "status"}
)


class ModelRegistryError(ValueError):
    """Raised when the model registry is missing or invalid."""


@dataclass(frozen=True)
class ModelSlot:
    """Configuration for one logical AI model slot."""

    name: str
    dev_model: str | None
    prod_candidate: str | None
    kpi: Mapping[str, Any]
    status: str

    @classmethod
    def from_mapping(
        cls,
        name: str,
        payload: Mapping[str, Any],
    ) -> ModelSlot:
        missing_fields = REQUIRED_FIELDS - payload.keys()
        if missing_fields:
            fields = ", ".join(sorted(missing_fields))
            raise ModelRegistryError(
                f"Slot {name!r} is missing required fields: {fields}"
            )

        dev_model = payload["dev_model"]
        prod_candidate = payload["prod_candidate"]
        kpi = payload["kpi"]
        status = payload["status"]

        for field_name, value in (
            ("dev_model", dev_model),
            ("prod_candidate", prod_candidate),
        ):
            if value is not None and not isinstance(value, str):
                raise ModelRegistryError(
                    f"Slot {name!r} field {field_name!r} must be a string or null"
                )
        if not isinstance(kpi, Mapping):
            raise ModelRegistryError(
                f"Slot {name!r} field 'kpi' must be a mapping"
            )
        if not isinstance(status, str) or not status.strip():
            raise ModelRegistryError(
                f"Slot {name!r} field 'status' must be a non-empty string"
            )

        return cls(
            name=name,
            dev_model=dev_model,
            prod_candidate=prod_candidate,
            kpi=dict(kpi),
            status=status,
        )


class ModelRegistry:
    """Collection of validated logical AI model slots."""

    def __init__(self, slots: Mapping[str, ModelSlot]) -> None:
        self._slots = dict(slots)

    @classmethod
    def load(cls, path: str | Path = DEFAULT_REGISTRY_PATH) -> ModelRegistry:
        registry_path = Path(path)
        try:
            payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ModelRegistryError(
                f"Model registry not found: {registry_path}"
            ) from exc
        except yaml.YAMLError as exc:
            raise ModelRegistryError(
                f"Invalid YAML in model registry: {registry_path}"
            ) from exc

        if not isinstance(payload, Mapping):
            raise ModelRegistryError("Model registry root must be a mapping")
        raw_slots = payload.get("slots")
        if not isinstance(raw_slots, Mapping):
            raise ModelRegistryError(
                "Model registry must contain a 'slots' mapping"
            )

        missing_slots = REQUIRED_SLOTS - raw_slots.keys()
        if missing_slots:
            slots = ", ".join(sorted(missing_slots))
            raise ModelRegistryError(
                f"Model registry is missing required slots: {slots}"
            )

        parsed_slots: dict[str, ModelSlot] = {}
        for name, raw_slot in raw_slots.items():
            if not isinstance(name, str) or not isinstance(raw_slot, Mapping):
                raise ModelRegistryError(
                    "Each model slot must have a string name and mapping value"
                )
            parsed_slots[name] = ModelSlot.from_mapping(name, raw_slot)

        return cls(parsed_slots)

    @property
    def slots(self) -> Mapping[str, ModelSlot]:
        return self._slots.copy()

    def get_slot(self, name: str) -> ModelSlot:
        try:
            return self._slots[name]
        except KeyError as exc:
            raise KeyError(f"Unknown model slot: {name}") from exc
