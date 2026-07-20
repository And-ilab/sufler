from __future__ import annotations

from django.db import models


class QuReferenceExample(models.Model):
    """An active source question used to explain a QU preview match."""

    question = models.CharField(max_length=1000)
    article_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    intent_id = models.CharField(max_length=128, blank=True)
    locale = models.CharField(max_length=8, default="ru")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)

    def __str__(self) -> str:
        return self.question
