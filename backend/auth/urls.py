from django.urls import path

from auth.views import auth_context


urlpatterns = [
    path("me/", auth_context, name="auth_context"),
]
