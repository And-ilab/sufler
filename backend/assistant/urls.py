from django.urls import path

from assistant.views import (
    assistant_attachment_extract,
    assistant_attachment_ocr,
    assistant_chat,
    assistant_knowledge_bases,
    assistant_models,
    assistant_openapi,
    assistant_report_detail,
    assistant_reports_analytics,
    assistant_reports_catalog,
    assistant_reports_export,
    assistant_source_download,
)

urlpatterns = [
    path("chat", assistant_chat, name="assistant_chat"),
    path(
        "attachments/extract",
        assistant_attachment_extract,
        name="assistant_attachment_extract",
    ),
    path(
        "attachments/ocr",
        assistant_attachment_ocr,
        name="assistant_attachment_ocr",
    ),
    path(
        "sources/download",
        assistant_source_download,
        name="assistant_source_download",
    ),
    path("models/", assistant_models, name="assistant_models"),
    path("kbs/", assistant_knowledge_bases, name="assistant_knowledge_bases"),
    path("openapi.json", assistant_openapi, name="assistant_openapi"),
    path("reports/", assistant_reports_catalog, name="assistant_reports_catalog"),
    path(
        "reports/analytics/",
        assistant_reports_analytics,
        name="assistant_reports_analytics",
    ),
    path(
        "reports/export/",
        assistant_reports_export,
        name="assistant_reports_export",
    ),
    path(
        "reports/<str:report_id>/",
        assistant_report_detail,
        name="assistant_report_detail",
    ),
]
