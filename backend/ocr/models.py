"""OCR job tracking for IV.5 upload → Celery → MinIO pipeline."""

from __future__ import annotations

from django.db import models


class OcrJob(models.Model):
    STATUS_QUEUED = "queued"
    STATUS_OCR_PROCESSING = "ocr_processing"
    STATUS_COMPLETED = "completed"
    STATUS_ERROR = "processing_error"
    STATUS_CHOICES = (
        (STATUS_QUEUED, "Queued"),
        (STATUS_OCR_PROCESSING, "OCR processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_ERROR, "Processing error"),
    )

    job_id = models.CharField(max_length=64, primary_key=True)
    document_id = models.CharField(max_length=64, db_index=True)
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
        db_index=True,
    )
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=128, blank=True)
    sha256 = models.CharField(max_length=64)
    original_object_key = models.CharField(max_length=512)
    result_object_key = models.CharField(max_length=512, blank=True)
    ocr_model = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    created_by = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.job_id} ({self.status})"
