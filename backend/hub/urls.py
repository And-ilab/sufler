from django.urls import path

from hub.views import (
    assistant_capabilities,
    assistant_capability_detail,
    assistant_knowledge_base_detail,
    assistant_knowledge_base_document_detail,
    assistant_knowledge_base_reindex,
    assistant_knowledge_base_upload,
    assistant_knowledge_bases,
    assistant_prompt_detail,
    assistant_prompts,
    knowledge_base_detail,
    knowledge_base_document_detail,
    knowledge_base_reindex,
    knowledge_base_upload,
    knowledge_bases,
    model_params,
    qu_preview,
)


urlpatterns = [
    path(
        "model-registry/model-params/",
        model_params,
        name="model_registry_model_params",
    ),
    path("qu/preview/", qu_preview, name="qu_preview"),
    path("kb/", knowledge_bases, name="knowledge_bases"),
    path("kb/<int:kb_id>/", knowledge_base_detail, name="knowledge_base_detail"),
    path(
        "kb/<int:kb_id>/upload/",
        knowledge_base_upload,
        name="knowledge_base_upload",
    ),
    path(
        "kb/<int:kb_id>/reindex/",
        knowledge_base_reindex,
        name="knowledge_base_reindex",
    ),
    path(
        "kb/<int:kb_id>/documents/<int:document_id>/",
        knowledge_base_document_detail,
        name="knowledge_base_document_detail",
    ),
    path(
        "assistant/kb/",
        assistant_knowledge_bases,
        name="assistant_knowledge_bases",
    ),
    path(
        "assistant/kb/<int:kb_id>/",
        assistant_knowledge_base_detail,
        name="assistant_knowledge_base_detail",
    ),
    path(
        "assistant/kb/<int:kb_id>/upload/",
        assistant_knowledge_base_upload,
        name="assistant_knowledge_base_upload",
    ),
    path(
        "assistant/kb/<int:kb_id>/reindex/",
        assistant_knowledge_base_reindex,
        name="assistant_knowledge_base_reindex",
    ),
    path(
        "assistant/kb/<int:kb_id>/documents/<int:document_id>/",
        assistant_knowledge_base_document_detail,
        name="assistant_knowledge_base_document_detail",
    ),
    path("assistant/prompts/", assistant_prompts, name="assistant_prompts"),
    path(
        "assistant/prompts/<int:prompt_id>/",
        assistant_prompt_detail,
        name="assistant_prompt_detail",
    ),
    path(
        "assistant/capabilities/",
        assistant_capabilities,
        name="assistant_capabilities",
    ),
    path(
        "assistant/capabilities/<slug:code>/",
        assistant_capability_detail,
        name="assistant_capability_detail",
    ),
]
