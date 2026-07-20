from __future__ import annotations

import math

from django.core.exceptions import ValidationError
from django.db import models


class ModelRegistrySettings(models.Model):
    """Database-backed editable parameters for one LLM profile."""

    PROFILE_ASSISTANT = "assistant_bank"
    PROFILE_SUFLER_CC = "sufler_cc"
    PROFILE_CHOICES = (
        (PROFILE_ASSISTANT, "Assistant Bank"),
        (PROFILE_SUFLER_CC, "Sufler Contact Center"),
    )

    profile = models.CharField(
        max_length=32,
        choices=PROFILE_CHOICES,
        unique=True,
    )
    temperature = models.FloatField()
    top_p = models.FloatField()
    max_tokens = models.PositiveIntegerField()
    response_chars_max = models.PositiveIntegerField()
    chunk_size_tokens = models.PositiveIntegerField()
    chunk_overlap_tokens = models.PositiveIntegerField()
    context_inclusion_threshold = models.FloatField()
    deterministic_answer_threshold = models.FloatField()
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ("profile",)
        verbose_name = "Model Registry settings"
        verbose_name_plural = "Model Registry settings"

    def clean(self) -> None:
        errors: dict[str, str] = {}
        if (
            not math.isfinite(self.temperature)
            or not 0 <= self.temperature <= 1
        ):
            errors["temperature"] = "Temperature must be between 0 and 1."
        if self.profile == self.PROFILE_SUFLER_CC and not 0.1 <= self.temperature <= 0.25:
            errors["temperature"] = (
                "Sufler CC temperature must be between 0.1 and 0.25."
            )
        if not math.isfinite(self.top_p) or not 0 < self.top_p <= 1:
            errors["top_p"] = "Top P must be greater than 0 and at most 1."
        if not 1 <= self.max_tokens <= 32768:
            errors["max_tokens"] = "Max tokens must be between 1 and 32768."
        if not 1 <= self.response_chars_max <= 500:
            errors["response_chars_max"] = (
                "Response length must be between 1 and 500 characters."
            )
        if self.chunk_size_tokens <= 0:
            errors["chunk_size_tokens"] = "Chunk size must be positive."
        if not 0 <= self.chunk_overlap_tokens < self.chunk_size_tokens:
            errors["chunk_overlap_tokens"] = (
                "Chunk overlap must be non-negative and smaller than chunk size."
            )
        for field_name, value in (
            (
                "context_inclusion_threshold",
                self.context_inclusion_threshold,
            ),
            (
                "deterministic_answer_threshold",
                self.deterministic_answer_threshold,
            ),
        ):
            if not math.isfinite(value) or not 0 <= value <= 1:
                errors[field_name] = "Threshold must be between 0 and 1."
        if (
            self.context_inclusion_threshold
            > self.deterministic_answer_threshold
        ):
            errors["deterministic_answer_threshold"] = (
                "Deterministic threshold cannot be lower than context inclusion."
            )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.profile
