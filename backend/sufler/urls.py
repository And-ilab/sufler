from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/admin/", include("hub.urls")),
    path("api/auth/", include("auth.urls")),
    path("api/v1/knowledge/", include("ingest.urls")),
    path("", include("chat.urls")),
]
