from __future__ import annotations

from django.db import models
from pgvector.django import VectorField


class KnowledgeIngestEvent(models.Model):
    event_id = models.UUIDField(primary_key=True, editable=False)
    article_id = models.BigIntegerField(db_index=True)
    version_id = models.BigIntegerField(null=True, blank=True)
    event_type = models.CharField(max_length=64)
    checksum = models.CharField(max_length=80, blank=True)
    outcome = models.CharField(max_length=32)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-received_at",)


class CCProductionChunk(models.Model):
    """One searchable article fragment in the cc_production pgvector index."""

    article_id = models.BigIntegerField(db_index=True)
    version_id = models.BigIntegerField()
    chunk_index = models.PositiveIntegerField()
    title = models.CharField(max_length=500)
    content = models.TextField()
    permalink = models.URLField(max_length=1000)
    locale = models.CharField(max_length=8)
    visibility_scope = models.JSONField(default=list)
    checksum = models.CharField(max_length=80)
    embedding_model = models.CharField(max_length=255)
    embedding = VectorField(dimensions=1024)
    is_active = models.BooleanField(default=True, db_index=True)
    indexed_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cc_production"
        ordering = ("article_id", "chunk_index")
        constraints = [
            models.UniqueConstraint(
                fields=("article_id", "version_id", "chunk_index"),
                name="cc_prod_article_version_chunk_uniq",
            )
        ]
        indexes = [
            models.Index(
                fields=("article_id", "is_active"),
                name="cc_prod_article_active_idx",
            )
        ]
