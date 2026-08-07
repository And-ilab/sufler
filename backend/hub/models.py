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


class ContactCenterKnowledgeBase(models.Model):
    """Admin-managed KB for contact-center sufler (FR-CC-08)."""

    STATUS_IDLE = "idle"
    STATUS_INDEXING = "indexing"
    STATUS_READY = "ready"
    STATUS_ERROR = "error"
    STATUS_CHOICES = (
        (STATUS_IDLE, "Idle"),
        (STATUS_INDEXING, "Indexing"),
        (STATUS_READY, "Ready"),
        (STATUS_ERROR, "Error"),
    )

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    scope = models.CharField(max_length=64, default="contact_center")
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_IDLE,
        db_index=True,
    )
    status_message = models.CharField(max_length=500, blank=True)
    document_count = models.PositiveIntegerField(default=0)
    chunk_count = models.PositiveIntegerField(default=0)
    last_reindexed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class KnowledgeBaseDocument(models.Model):
    """Uploaded source document for a contact-center KB (FR-CC-13)."""

    STATUS_UPLOADED = "uploaded"
    STATUS_INDEXED = "indexed"
    STATUS_ERROR = "error"
    STATUS_CHOICES = (
        (STATUS_UPLOADED, "Uploaded"),
        (STATUS_INDEXED, "Indexed"),
        (STATUS_ERROR, "Error"),
    )

    knowledge_base = models.ForeignKey(
        ContactCenterKnowledgeBase,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=128, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_UPLOADED,
        db_index=True,
    )
    status_message = models.CharField(max_length=500, blank=True)
    extracted_text = models.TextField(blank=True)
    chunk_count = models.PositiveIntegerField(default=0)
    article_id = models.BigIntegerField(unique=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    indexed_at = models.DateTimeField(null=True, blank=True)
    uploaded_by = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ("-uploaded_at",)

    def __str__(self) -> str:
        return self.filename


class AssistantKnowledgeBase(models.Model):
    """Assistant module KB namespace ``assistant_*`` (isolated from cc_production)."""

    STATUS_IDLE = "idle"
    STATUS_INDEXING = "indexing"
    STATUS_READY = "ready"
    STATUS_ERROR = "error"
    STATUS_CHOICES = (
        (STATUS_IDLE, "Idle"),
        (STATUS_INDEXING, "Indexing"),
        (STATUS_READY, "Ready"),
        (STATUS_ERROR, "Error"),
    )

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    scope = models.CharField(max_length=64, default="department")
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_IDLE,
        db_index=True,
    )
    status_message = models.CharField(max_length=500, blank=True)
    document_count = models.PositiveIntegerField(default=0)
    chunk_count = models.PositiveIntegerField(default=0)
    last_reindexed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.slug


class AssistantKnowledgeBaseDocument(models.Model):
    """Uploaded source document for an assistant_* KB (isolated from КЦ)."""

    STATUS_UPLOADED = "uploaded"
    STATUS_INDEXED = "indexed"
    STATUS_ERROR = "error"
    STATUS_CHOICES = (
        (STATUS_UPLOADED, "Uploaded"),
        (STATUS_INDEXED, "Indexed"),
        (STATUS_ERROR, "Error"),
    )

    knowledge_base = models.ForeignKey(
        AssistantKnowledgeBase,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=128, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_UPLOADED,
        db_index=True,
    )
    status_message = models.CharField(max_length=500, blank=True)
    extracted_text = models.TextField(blank=True)
    chunk_count = models.PositiveIntegerField(default=0)
    article_id = models.BigIntegerField(unique=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    indexed_at = models.DateTimeField(null=True, blank=True)
    uploaded_by = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ("-uploaded_at",)

    def __str__(self) -> str:
        return self.filename


class AssistantPromptTemplate(models.Model):
    """CRUD prompt templates for assistant_bank (III.10.1 / III.6)."""

    TYPE_SYSTEM = "system"
    TYPE_TASK = "task"
    TYPE_SCOPE = "scope"
    TYPE_CHOICES = (
        (TYPE_SYSTEM, "System"),
        (TYPE_TASK, "Task"),
        (TYPE_SCOPE, "Scope"),
    )
    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_PUBLISHED, "Published"),
    )

    name = models.CharField(max_length=200)
    prompt_type = models.CharField(
        max_length=16,
        choices=TYPE_CHOICES,
        default=TYPE_TASK,
        db_index=True,
    )
    scope = models.CharField(max_length=64, default="bank")
    body = models.TextField()
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )
    version = models.PositiveIntegerField(default=1)
    kb_slug = models.SlugField(max_length=200, blank=True, default="")
    updated_by = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("prompt_type", "name")

    def __str__(self) -> str:
        return f"{self.name} v{self.version}"


class AssistantCapability(models.Model):
    """Tools / skills registry stub for «Навыки» (III.6 / VII.5 D4)."""

    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)
    deep_link = models.CharField(max_length=128, blank=True)
    category = models.CharField(max_length=64, default="tool")
    sort_order = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "name")
        verbose_name_plural = "Assistant capabilities"

    def __str__(self) -> str:
        return self.code
