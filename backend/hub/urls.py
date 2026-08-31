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
    qu_example_detail,
    qu_example_review,
    qu_examples,
    qu_kb_documents,
    qu_policy,
    qu_preview,
    sufler_policies,
    dialog_scenarios,
    dialog_scenario_detail,
    dialog_scenario_test_run,
)


urlpatterns = [
    path(
        "model-registry/model-params/",
        model_params,
        name="model_registry_model_params",
    ),
    path("sufler/policies/", sufler_policies, name="sufler_policies"),
    path("scenarios/", dialog_scenarios, name="dialog_scenarios"),
    path("scenarios/<str:code>/", dialog_scenario_detail, name="dialog_scenario_detail"),
    path(
        "scenarios/<str:code>/test-run/",
        dialog_scenario_test_run,
        name="dialog_scenario_test_run",
    ),
    path("qu/preview/", qu_preview, name="qu_preview"),
    path("qu/examples/", qu_examples, name="qu_examples"),
    path("qu/examples/<int:example_id>/", qu_example_detail, name="qu_example_detail"),
    path(
        "qu/examples/<int:example_id>/review/",
        qu_example_review,
        name="qu_example_review",
    ),
    path("qu/policy/", qu_policy, name="qu_policy"),
    path("qu/documents/", qu_kb_documents, name="qu_kb_documents"),
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
