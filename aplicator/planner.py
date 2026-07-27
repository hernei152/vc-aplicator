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


@dataclass
class Recording:
    focus: str
    orientation: str
    language: str
    who: str
    record_seconds: int
    master_question: object
    derived_cut_questions: list


def _resolve_dimension(groups, attr):
    new_groups = []
    for group in groups:
        concrete_values = sorted(
            {getattr(q, attr) for q in group if getattr(q, attr) != "any"}
        )
        if len(concrete_values) <= 1:
            new_groups.append(group)
            continue
        buckets = {v: [q for q in group if getattr(q, attr) == v] for v in concrete_values}
        any_qs = [q for q in group if getattr(q, attr) == "any"]
        if any_qs:
            target = max(concrete_values, key=lambda v: len(buckets[v]))
            buckets[target].extend(any_qs)
        new_groups.extend(buckets.values())
    return new_groups


def _group_dimension_value(group, attr):
    concrete = {getattr(q, attr) for q in group if getattr(q, attr) != "any"}
    return concrete.pop() if len(concrete) == 1 else "any"


def _resolve_duration(group):
    def sort_key(q):
        return q.max_seconds if q.max_seconds is not None else float("inf")

    ordered = sorted(group, key=lambda q: q.id)
    ordered = sorted(ordered, key=sort_key, reverse=True)
    master = ordered[0]
    record_seconds = (
        master.max_seconds if master.max_seconds is not None else (master.min_seconds or 0)
    )
    return master, record_seconds, ordered[1:]


def group_video_questions(questions):
    videos = [q for q in questions if q.type == "video"]
    by_focus = {}
    for q in videos:
        by_focus.setdefault(q.focus, []).append(q)

    recordings = []
    for focus in sorted(by_focus):
        groups = [by_focus[focus]]
        for attr in ("orientation", "language", "who"):
            groups = _resolve_dimension(groups, attr)
        for group in groups:
            master, record_seconds, derived_cuts = _resolve_duration(group)
            recordings.append(
                Recording(
                    focus=focus,
                    orientation=_group_dimension_value(group, "orientation"),
                    language=_group_dimension_value(group, "language"),
                    who=_group_dimension_value(group, "who"),
                    record_seconds=record_seconds,
                    master_question=master,
                    derived_cut_questions=derived_cuts,
                )
            )
    return recordings
