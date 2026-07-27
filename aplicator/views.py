from django.shortcuts import render, redirect, get_object_or_404
from django.forms import modelformset_factory

from aplicator.models import TeamMember, CompanyContextBlock, Accelerator, Question
from aplicator.forms import TeamMemberForm, CompanyContextBlockForm
from aplicator.llm.factory import get_llm_port


def context_view(request):
    member_form = TeamMemberForm()
    block_form = CompanyContextBlockForm()
    if request.method == "POST":
        if "add_member" in request.POST:
            member_form = TeamMemberForm(request.POST)
            if member_form.is_valid():
                member_form.save()
                return redirect("aplicator:context")
        elif "add_block" in request.POST:
            block_form = CompanyContextBlockForm(request.POST)
            if block_form.is_valid():
                block_form.save()
                return redirect("aplicator:context")
    return render(
        request,
        "aplicator/context.html",
        {
            "members": TeamMember.objects.all(),
            "blocks": CompanyContextBlock.objects.all(),
            "member_form": member_form,
            "block_form": block_form,
        },
    )


QuestionFormSet = modelformset_factory(
    Question,
    fields=[
        "type",
        "original_text",
        "is_required",
        "category",
        "max_chars",
        "options",
        "allow_multiple",
        "focus",
        "min_seconds",
        "max_seconds",
        "orientation",
        "language",
        "who",
    ],
    extra=0,
)


def accelerator_add_view(request):
    if request.method == "POST":
        raw_text = request.POST.get("raw_text", "")
        llm = get_llm_port()
        extracted = llm.extract_form(raw_text)
        accelerator = Accelerator.objects.create(
            accelerator_name=extracted.get("accelerator_name") or "Sin nombre",
            url=extracted.get("url") or "",
            deadline=extracted.get("deadline") or None,
            raw_text=raw_text,
        )
        for q in extracted.get("questions", []):
            Question.objects.create(
                accelerator=accelerator,
                type=q.get("type"),
                original_text=q.get("original_text", ""),
                is_required=q.get("is_required", True),
                category=q.get("category"),
                max_chars=q.get("max_chars"),
                options=q.get("options") or [],
                allow_multiple=q.get("allow_multiple", False),
                focus=q.get("focus"),
                min_seconds=q.get("min_seconds"),
                max_seconds=q.get("max_seconds"),
                orientation=q.get("orientation") or "any",
                language=q.get("language") or "any",
                who=q.get("who") or "any",
            )
        return redirect("aplicator:accelerator_review", accelerator_id=accelerator.id)
    return render(
        request,
        "aplicator/accelerator_add.html",
        {"accelerators": Accelerator.objects.all()},
    )


def accelerator_review_view(request, accelerator_id):
    accelerator = get_object_or_404(Accelerator, pk=accelerator_id)
    queryset = Question.objects.filter(accelerator=accelerator)
    if request.method == "POST":
        formset = QuestionFormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            formset.save()
            return redirect("aplicator:accelerator_add")
    else:
        formset = QuestionFormSet(queryset=queryset)
    return render(
        request,
        "aplicator/accelerator_review.html",
        {"accelerator": accelerator, "formset": formset},
    )
