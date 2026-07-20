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
REQUIRED_PROFILES = frozenset({"kb_cc_production"})
REQUIRED_PROFILE_FIELDS = frozenset(
    {
        "target_index",
        "embedding_slot",
        "embedding_model",
        "similarity_metric",
        "chunk_size_tokens",
        "chunk_overlap_tokens",
        "thresholds",
        "source_trace_required",
        "status",
        "selection_basis",
        "bench_evidence",
        "change_control",
    }
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


@dataclass(frozen=True)
class KnowledgeBaseProfile:
    """Frozen retrieval defaults for one logical knowledge base."""

    name: str
    target_index: str
    embedding_slot: str
    embedding_model: str
    similarity_metric: str
    chunk_size_tokens: int
    chunk_overlap_tokens: int
    context_inclusion_threshold: float
    deterministic_answer_threshold: float
    source_trace_required: bool
    status: str
    selection_basis: str
    bench_evidence: Mapping[str, Any]
    change_control: Mapping[str, Any]

    @classmethod
    def from_mapping(
        cls,
        name: str,
        payload: Mapping[str, Any],
        slots: Mapping[str, ModelSlot],
    ) -> KnowledgeBaseProfile:
        missing_fields = REQUIRED_PROFILE_FIELDS - payload.keys()
        if missing_fields:
            fields = ", ".join(sorted(missing_fields))
            raise ModelRegistryError(
                f"Profile {name!r} is missing required fields: {fields}"
            )

        string_fields = (
            "target_index",
            "embedding_slot",
            "embedding_model",
            "similarity_metric",
            "status",
            "selection_basis",
        )
        for field_name in string_fields:
            value = payload[field_name]
            if not isinstance(value, str) or not value.strip():
                raise ModelRegistryError(
                    f"Profile {name!r} field {field_name!r} "
                    "must be a non-empty string"
                )
        if name == "kb_cc_production" and payload["status"] != "dev_frozen":
            raise ModelRegistryError(
                "Profile 'kb_cc_production' must have status 'dev_frozen'"
            )

        chunk_size = payload["chunk_size_tokens"]
        overlap = payload["chunk_overlap_tokens"]
        if (
            not isinstance(chunk_size, int)
            or isinstance(chunk_size, bool)
            or chunk_size <= 0
        ):
            raise ModelRegistryError(
                f"Profile {name!r} has invalid chunk_size_tokens"
            )
        if (
            not isinstance(overlap, int)
            or isinstance(overlap, bool)
            or overlap < 0
            or overlap >= chunk_size
        ):
            raise ModelRegistryError(
                f"Profile {name!r} requires 0 <= overlap < chunk size"
            )

        thresholds = payload["thresholds"]
        if not isinstance(thresholds, Mapping):
            raise ModelRegistryError(
                f"Profile {name!r} field 'thresholds' must be a mapping"
            )
        try:
            context = thresholds["context_inclusion"]
            deterministic = thresholds["deterministic_answer"]
        except KeyError as exc:
            raise ModelRegistryError(
                f"Profile {name!r} is missing threshold: {exc.args[0]}"
            ) from exc
        for threshold_name, value in (
            ("context_inclusion", context),
            ("deterministic_answer", deterministic),
        ):
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not 0 <= value <= 1
            ):
                raise ModelRegistryError(
                    f"Profile {name!r} threshold {threshold_name!r} "
                    "must be between 0 and 1"
                )
        if context > deterministic:
            raise ModelRegistryError(
                f"Profile {name!r} context threshold cannot exceed "
                "deterministic threshold"
            )

        source_trace_required = payload["source_trace_required"]
        if not isinstance(source_trace_required, bool):
            raise ModelRegistryError(
                f"Profile {name!r} source_trace_required must be boolean"
            )
        bench_evidence = payload["bench_evidence"]
        change_control = payload["change_control"]
        if not isinstance(bench_evidence, Mapping):
            raise ModelRegistryError(
                f"Profile {name!r} bench_evidence must be a mapping"
            )
        if not isinstance(change_control, Mapping):
            raise ModelRegistryError(
                f"Profile {name!r} change_control must be a mapping"
            )
        if change_control.get("benchmark_required") is not True:
            raise ModelRegistryError(
                f"Profile {name!r} must require benchmark change control"
            )
        if change_control.get("sign_off_required") is not True:
            raise ModelRegistryError(
                f"Profile {name!r} must require sign-off"
            )

        embedding_slot = payload["embedding_slot"]
        try:
            slot = slots[embedding_slot]
        except KeyError as exc:
            raise ModelRegistryError(
                f"Profile {name!r} references unknown slot: {embedding_slot}"
            ) from exc
        model = payload["embedding_model"]
        if model not in {slot.dev_model, slot.prod_candidate}:
            raise ModelRegistryError(
                f"Profile {name!r} model is inconsistent with "
                f"slot {embedding_slot!r}"
            )
        expected_values = {
            "similarity_metric": slot.kpi.get("similarity_metric"),
            "chunk_size_tokens": slot.kpi.get(
                "optimal_chunk_size_tokens"
            ),
            "chunk_overlap_tokens": slot.kpi.get(
                "optimal_chunk_overlap_tokens"
            ),
            "context_inclusion": slot.kpi.get(
                "context_inclusion_threshold"
            ),
            "deterministic_answer": slot.kpi.get(
                "deterministic_answer_threshold"
            ),
        }
        profile_values = {
            "similarity_metric": payload["similarity_metric"],
            "chunk_size_tokens": chunk_size,
            "chunk_overlap_tokens": overlap,
            "context_inclusion": context,
            "deterministic_answer": deterministic,
        }
        for field_name, expected in expected_values.items():
            if profile_values[field_name] != expected:
                raise ModelRegistryError(
                    f"Profile {name!r} field {field_name!r} is "
                    f"inconsistent with slot {embedding_slot!r}"
                )
        for status_field in (
            "chunk_selection_status",
            "retrieval_threshold_status",
        ):
            if slot.kpi.get(status_field) != payload["status"]:
                raise ModelRegistryError(
                    f"Profile {name!r} status is inconsistent with "
                    f"slot field {status_field!r}"
                )

        return cls(
            name=name,
            target_index=payload["target_index"],
            embedding_slot=embedding_slot,
            embedding_model=model,
            similarity_metric=payload["similarity_metric"],
            chunk_size_tokens=chunk_size,
            chunk_overlap_tokens=overlap,
            context_inclusion_threshold=float(context),
            deterministic_answer_threshold=float(deterministic),
            source_trace_required=source_trace_required,
            status=payload["status"],
            selection_basis=payload["selection_basis"],
            bench_evidence=dict(bench_evidence),
            change_control=dict(change_control),
        )


class ModelRegistry:
    """Collection of validated logical AI model slots."""

    def __init__(
        self,
        slots: Mapping[str, ModelSlot],
        profiles: Mapping[str, KnowledgeBaseProfile],
    ) -> None:
        self._slots = dict(slots)
        self._profiles = dict(profiles)

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

        raw_profiles = payload.get("profiles")
        if not isinstance(raw_profiles, Mapping):
            raise ModelRegistryError(
                "Model registry must contain a 'profiles' mapping"
            )
        missing_profiles = REQUIRED_PROFILES - raw_profiles.keys()
        if missing_profiles:
            profiles = ", ".join(sorted(missing_profiles))
            raise ModelRegistryError(
                f"Model registry is missing required profiles: {profiles}"
            )
        parsed_profiles: dict[str, KnowledgeBaseProfile] = {}
        for name, raw_profile in raw_profiles.items():
            if not isinstance(name, str) or not isinstance(
                raw_profile,
                Mapping,
            ):
                raise ModelRegistryError(
                    "Each profile must have a string name and mapping value"
                )
            parsed_profiles[name] = KnowledgeBaseProfile.from_mapping(
                name,
                raw_profile,
                parsed_slots,
            )

        return cls(parsed_slots, parsed_profiles)

    @property
    def slots(self) -> Mapping[str, ModelSlot]:
        return self._slots.copy()

    @property
    def profiles(self) -> Mapping[str, KnowledgeBaseProfile]:
        return self._profiles.copy()

    def get_slot(self, name: str) -> ModelSlot:
        try:
            return self._slots[name]
        except KeyError as exc:
            raise KeyError(f"Unknown model slot: {name}") from exc

    def get_profile(self, name: str) -> KnowledgeBaseProfile:
        try:
            return self._profiles[name]
        except KeyError as exc:
            raise KeyError(f"Unknown model profile: {name}") from exc
