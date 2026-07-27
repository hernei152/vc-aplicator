from django.urls import path

from aplicator import views

app_name = "aplicator"

urlpatterns = [
    path("", views.context_view, name="context"),
    path("accelerators/add/", views.accelerator_add_view, name="accelerator_add"),
    path(
        "accelerators/<int:accelerator_id>/review/",
        views.accelerator_review_view,
        name="accelerator_review",
    ),
]
