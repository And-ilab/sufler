from django.urls import path



from orchestrator.views import sufler_suggest, sufler_test_dialog





urlpatterns = [

    path("suggest", sufler_suggest, name="sufler_suggest"),

    path("test-dialog", sufler_test_dialog, name="sufler_test_dialog"),

]

