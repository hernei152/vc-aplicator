from django.urls import path

from aplicator import views

app_name = "aplicator"

urlpatterns = [
    path("", views.context_view, name="context"),
    path(
        "context/member/<int:member_id>/edit/",
        views.team_member_edit_view,
        name="team_member_edit",
    ),
    path(
        "context/member/<int:member_id>/delete/",
        views.team_member_delete_view,
        name="team_member_delete",
    ),
    path(
        "context/block/<int:block_id>/edit/",
        views.context_block_edit_view,
        name="context_block_edit",
    ),
    path(
        "context/block/<int:block_id>/delete/",
        views.context_block_delete_view,
        name="context_block_delete",
    ),
    path(
        "context/member/<int:member_id>/delete/confirm/",
        views.team_member_delete_confirm_view,
        name="team_member_delete_confirm",
    ),
    path(
        "context/block/<int:block_id>/delete/confirm/",
        views.context_block_delete_confirm_view,
        name="context_block_delete_confirm",
    ),
    path("accelerators/add/", views.accelerator_add_view, name="accelerator_add"),
    path(
        "accelerators/<int:accelerator_id>/review/",
        views.accelerator_review_view,
        name="accelerator_review",
    ),
    path(
        "accelerators/<int:accelerator_id>/answers/",
        views.application_answers_view,
        name="application_answers",
    ),
    path("plan/", views.plan_view, name="plan"),
    path("answer-bank/", views.answer_bank_view, name="answer_bank"),
]
