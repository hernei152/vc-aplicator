from django import template

from aplicator.models import QuestionArchetype, VideoFocus

register = template.Library()

_CATEGORY_LABELS = dict(QuestionArchetype.choices)
_FOCUS_LABELS = dict(VideoFocus.choices)


@register.filter
def category_label(value):
    return _CATEGORY_LABELS.get(value, value)


@register.filter
def focus_label(value):
    return _FOCUS_LABELS.get(value, value)
