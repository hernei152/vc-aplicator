from dataclasses import dataclass, field

from aplicator.models import NON_SHAREABLE


@dataclass
class TextGroup:
    category: str
    questions: list
    min_max_chars: int | None
    max_max_chars: int | None
    accelerator_names: list


def group_text_questions(questions):
    groups = {}
    for q in questions:
        if q.type not in ("text", "multiple_choice"):
            continue
        if q.category in NON_SHAREABLE:
            continue
        groups.setdefault(q.category, []).append(q)

    result = []
    for category, qs in groups.items():
        max_chars_values = [q.max_chars for q in qs if q.max_chars is not None]
        accelerator_names = sorted({q.accelerator.accelerator_name for q in qs})
        result.append(
            TextGroup(
                category=category,
                questions=qs,
                min_max_chars=min(max_chars_values) if max_chars_values else None,
                max_max_chars=max(max_chars_values) if max_chars_values else None,
                accelerator_names=accelerator_names,
            )
        )
    result.sort(key=lambda g: g.category)
    return result
