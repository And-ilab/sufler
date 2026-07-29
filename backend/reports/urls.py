from django.urls import path

from assistant.views import (
    assistant_reports_analytics,
    assistant_reports_catalog,
    assistant_reports_export,
)
from reports.views import (
    asr_seed_demo,
    asr_session_audio,
    asr_session_detail,
    asr_sessions,
    asr_utterance_annotation,
    cc_analytics,
    cc_export,
)

urlpatterns = [
    path("asr/sessions/", asr_sessions, name="asr_sessions"),
    path(
        "asr/sessions/<int:session_id>/",
        asr_session_detail,
        name="asr_session_detail",
    ),
    path(
        "asr/sessions/<int:session_id>/audio/",
        asr_session_audio,
        name="asr_session_audio",
    ),
    path(
        "asr/sessions/<int:session_id>/utterances/<int:utterance_id>/",
        asr_utterance_annotation,
        name="asr_utterance_annotation",
    ),
    path("asr/seed-demo/", asr_seed_demo, name="asr_seed_demo"),
    path("cc/analytics/", cc_analytics, name="cc_analytics"),
    path("cc/export/", cc_export, name="cc_export"),
    # FR-RPT-ASS / III.10.2 — same handlers as /api/v1/assistant/reports/
    path("ass/", assistant_reports_catalog, name="ass_reports_catalog"),
    path(
        "ass/analytics/",
        assistant_reports_analytics,
        name="ass_reports_analytics",
    ),
    path("ass/export/", assistant_reports_export, name="ass_reports_export"),
]


