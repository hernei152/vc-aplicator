from django.shortcuts import render, redirect

from aplicator.models import TeamMember, CompanyContextBlock
from aplicator.forms import TeamMemberForm, CompanyContextBlockForm


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
