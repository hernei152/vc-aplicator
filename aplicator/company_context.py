from aplicator.models import TeamMember, CompanyContextBlock


def build_company_context_text():
    parts = []
    for member in TeamMember.objects.all():
        parts.append(
            f"Equipo — {member.name} ({member.role}): {member.bio}\n"
            f"Track record: {member.track_record}\n"
            f"Proyectos destacables: {member.notable_projects}"
        )
    for block in CompanyContextBlock.objects.all():
        parts.append(f"{block.label}: {block.text}")
    return "\n\n".join(parts)
