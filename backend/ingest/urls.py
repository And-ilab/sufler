from django.urls import path

from ingest.views import knowledge_events


urlpatterns = [
    path("events", knowledge_events, name="suz_knowledge_events"),
]
