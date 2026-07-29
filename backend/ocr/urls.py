from django.urls import path

from ocr.views import (
    ocr_doc_types,
    ocr_export,
    ocr_job_detail,
    ocr_job_export,
    ocr_job_result,
    ocr_upload,
    ocr_validate,
)

urlpatterns = [
    path("documents/", ocr_upload, name="ocr_upload"),
    path("doc-types/", ocr_doc_types, name="ocr_doc_types"),
    path("validate/", ocr_validate, name="ocr_validate"),
    path("export/", ocr_export, name="ocr_export"),
    path("jobs/<str:job_id>/", ocr_job_detail, name="ocr_job_detail"),
    path(
        "jobs/<str:job_id>/result/",
        ocr_job_result,
        name="ocr_job_result",
    ),
    path(
        "jobs/<str:job_id>/export/",
        ocr_job_export,
        name="ocr_job_export",
    ),
]
