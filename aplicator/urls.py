from django.urls import path

from aplicator import views

app_name = "aplicator"

urlpatterns = [
    path("", views.context_view, name="context"),
]
