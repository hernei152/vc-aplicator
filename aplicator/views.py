from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.forms import modelformset_factory
from django.utils.dateparse import parse_date
from django.contrib import messages

from aplicator.models import (
    TeamMember,
    CompanyContextBlock,
    Accelerator,
    Question,
    CanonicalAnswer,
    GeneratedAnswer,
    NON_SHAREABLE,
)
from aplicator.forms import TeamMemberForm, CompanyContextBlockForm
from aplicator.llm.factory import get_llm_port
from aplicator.planner import group_text_questions, group_video_questions, rank_accelerators
from aplicator.company_context import build_company_context_text


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


def team_member_edit_view(request, member_id):
    member = get_object_or_404(TeamMember, pk=member_id)
    if request.method == "POST":
        form = TeamMemberForm(request.POST, instance=member)
        if form.is_valid():
            form.save()
            return redirect("aplicator:context")
    else:
        form = TeamMemberForm(instance=member)
    return render(
        request,
        "aplicator/edit_form.html",
        {"form": form, "title": f"Editar miembro: {member.name}"},
    )


def team_member_delete_view(request, member_id):
    if request.method == "POST":
        TeamMember.objects.filter(pk=member_id).delete()
    return redirect("aplicator:context")


def context_block_edit_view(request, block_id):
    block = get_object_or_404(CompanyContextBlock, pk=block_id)
    if request.method == "POST":
        form = CompanyContextBlockForm(request.POST, instance=block)
        if form.is_valid():
            form.save()
            return redirect("aplicator:context")
    else:
        form = CompanyContextBlockForm(instance=block)
    return render(
        request,
        "aplicator/edit_form.html",
        {"form": form, "title": f"Editar bloque: {block.label}"},
    )


def context_block_delete_view(request, block_id):
    if request.method == "POST":
        CompanyContextBlock.objects.filter(pk=block_id).delete()
    return redirect("aplicator:context")


def team_member_delete_confirm_view(request, member_id):
    member = get_object_or_404(TeamMember, pk=member_id)
    return render(
        request,
        "aplicator/delete_confirm.html",
        {
            "label": member.name,
            "delete_url": reverse("aplicator:team_member_delete", args=[member.id]),
        },
    )


def context_block_delete_confirm_view(request, block_id):
    block = get_object_or_404(CompanyContextBlock, pk=block_id)
    return render(
        request,
        "aplicator/delete_confirm.html",
        {
            "label": block.label,
            "delete_url": reverse("aplicator:context_block_delete", args=[block.id]),
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
        # get_or_create guards against the accelerator_name unique constraint:
        # if extraction yields a name that already exists (including a repeated
        # "Sin nombre" fallback), we reuse that accelerator instead of crashing
        # with an IntegrityError, and just append the newly extracted questions
        # to it for review.
        accelerator, _created = Accelerator.objects.get_or_create(
            accelerator_name=extracted.get("accelerator_name") or "Sin nombre",
            defaults={
                "url": extracted.get("url") or "",
                "deadline": parse_date(extracted.get("deadline") or ""),
                "raw_text": raw_text,
            },
        )
        for q in extracted.get("questions", []):
            Question.objects.create(
                accelerator=accelerator,
                type=q.get("type"),
                original_text=q.get("original_text", ""),
                is_required=q.get("is_required", True),
                category=q.get("category") or q.get("archetype"),
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
        question_count = len(extracted.get("questions", []))
        messages.info(
            request,
            f"Se extrajeron {question_count} preguntas — revisalas antes de continuar.",
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


def plan_view(request):
    questions = list(Question.objects.select_related("accelerator").all())
    accelerators = Accelerator.objects.all()
    return render(
        request,
        "aplicator/plan.html",
        {
            "text_groups": group_text_questions(questions),
            "recordings": group_video_questions(questions),
            "ranked_accelerators": rank_accelerators(accelerators, questions),
        },
    )


def answer_bank_view(request):
    if request.method == "POST":
        category = request.POST.get("category")
        text = request.POST.get("text", "")
        if "generate" in request.POST:
            llm = get_llm_port()
            text = llm.generate_text(
                prompt=f"Escribí la respuesta canónica larga para la categoría '{category}'.",
                context=build_company_context_text(),
            )
        CanonicalAnswer.objects.update_or_create(
            category=category, defaults={"text": text}
        )
        return redirect("aplicator:answer_bank")

    questions = list(Question.objects.select_related("accelerator").all())
    canonical_by_category = {c.category: c for c in CanonicalAnswer.objects.all()}
    rows = [
        {
            "category": group.category,
            "canonical": canonical_by_category.get(group.category),
            "accelerator_names": group.accelerator_names,
        }
        for group in group_text_questions(questions)
    ]
    return render(request, "aplicator/answer_bank.html", {"rows": rows})


def application_answers_view(request, accelerator_id):
    accelerator = get_object_or_404(Accelerator, pk=accelerator_id)

    if request.method == "POST":
        question = get_object_or_404(
            Question, pk=request.POST.get("question_id"), accelerator=accelerator
        )
        text = request.POST.get("text", "")
        if "generate" in request.POST:
            llm = get_llm_port()
            if question.category and question.category not in NON_SHAREABLE:
                canonical = CanonicalAnswer.objects.filter(
                    category=question.category
                ).first()
                context_text = canonical.text if canonical else build_company_context_text()
            else:
                context_text = build_company_context_text()
            prompt_lines = [
                "Adaptá esta respuesta al wording exacto y al límite de esta pregunta puntual.",
                f"Pregunta original: {question.original_text}",
            ]
            if question.max_chars is not None:
                prompt_lines.append(f"Límite de caracteres: {question.max_chars}")
            text = llm.generate_text(prompt="\n".join(prompt_lines), context=context_text)
            if question.max_chars is not None:
                text = text[: question.max_chars]
        GeneratedAnswer.objects.update_or_create(question=question, defaults={"text": text})
        return redirect("aplicator:application_answers", accelerator_id=accelerator.id)

    questions = Question.objects.filter(
        accelerator=accelerator, type__in=["text", "multiple_choice"]
    )
    rows = []
    for q in questions:
        answer = GeneratedAnswer.objects.filter(question=q).first()
        answer_length = len(answer.text) if answer else 0
        rows.append(
            {
                "question": q,
                "answer": answer,
                "answer_length": answer_length,
                "possibly_truncated": (
                    answer is not None
                    and q.max_chars is not None
                    and answer_length == q.max_chars
                ),
            }
        )
    return render(
        request,
        "aplicator/application_answers.html",
        {"accelerator": accelerator, "rows": rows},
    )
