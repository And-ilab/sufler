from django.urls import path

from hub.views import model_params, qu_preview


urlpatterns = [
    path(
        "model-registry/model-params/",
        model_params,
        name="model_registry_model_params",
    ),
    path("qu/preview/", qu_preview, name="qu_preview"),
]
