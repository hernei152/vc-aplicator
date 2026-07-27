# UI/UX Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix usability problems across all 7 pages of the already-shipped accel Django app — most importantly, make the accelerator-review formset show only the fields relevant to each question's type — and add a vendored classless CSS framework for visual polish, without introducing any JS or build step.

**Architecture:** Template-level and view-level changes only. No changes to `contracts.py`, `aplicator/models.py`, or `aplicator/planner.py`. One new small module (`aplicator/templatetags/aplicator_extras.py`) for human-readable enum labels, one vendored static asset (`pico.min.css`), and a handful of new small views/templates for delete confirmation.

**Tech Stack:** Django templates, `django.contrib.staticfiles`, `django.contrib.messages` (both already configured in `accel/settings.py`), Pico.css v2 (vendored, classless, no JS).

## Global Constraints

- No JavaScript of any kind (no live character counters, no `confirm()` dialogs, no client-side validation) — every interaction is a full-page reload, consistent with the rest of the app.
- `contracts.py` at the repo root — never modify it.
- Do not change `aplicator/models.py`, `aplicator/planner.py`, or the LLM adapter — this is a template/view-only pass.
- All new behavior needs a test using Django's `TestCase` and real DB, matching the existing test style in `aplicator/tests/`.
- Every task must leave `python manage.py test` green before its commit.

---

### Task 1: Vendor Pico.css and wire it into base.html

**Files:**
- Create: `aplicator/static/aplicator/pico.min.css`
- Modify: `aplicator/templates/aplicator/base.html`
- Test: `aplicator/tests/test_static_assets.py`

**Interfaces:**
- Produces: every page extending `aplicator/base.html` gets Pico.css's classless styling automatically. `{% block content %}` and `<nav>` are unchanged in position — only styling changes. A `{% if messages %}` block (rendered as `<article>` tags, styled by Pico) is added right after `<nav>`, for Task 3's flash message to render into.

- [ ] **Step 1: Download the pinned Pico.css release**

```bash
mkdir -p aplicator/static/aplicator
curl -sL -o aplicator/static/aplicator/pico.min.css \
  https://cdn.jsdelivr.net/npm/@picocss/pico@2.0.6/css/pico.min.css
```

Verify it's non-trivial (a real stylesheet, not an error page or empty response):

```bash
wc -c aplicator/static/aplicator/pico.min.css
head -c 200 aplicator/static/aplicator/pico.min.css
```

Expected: file size well over 50000 bytes, content starts with a CSS comment block (`/*!`), not HTML.

- [ ] **Step 2: Write the failing test**

Create `aplicator/tests/test_static_assets.py`:

```python
import os
from django.conf import settings
from django.test import TestCase


class PicoCssVendoredTest(TestCase):
    def test_pico_css_file_exists_and_is_nontrivial(self):
        path = os.path.join(settings.BASE_DIR, "aplicator", "static", "aplicator", "pico.min.css")
        self.assertTrue(os.path.exists(path), f"expected {path} to exist")
        self.assertGreater(os.path.getsize(path), 50_000)

    def test_base_template_links_pico_css(self):
        response = self.client.get("/")
        self.assertContains(response, "pico.min.css")
```

- [ ] **Step 2b: Run test to verify the template-link assertion fails**

Run: `python manage.py test aplicator.tests.test_static_assets`
Expected: `test_pico_css_file_exists_and_is_nontrivial` passes (file already downloaded in Step 1), `test_base_template_links_pico_css` FAILS (base.html doesn't reference it yet).

- [ ] **Step 3: Rewrite base.html**

Replace the full contents of `aplicator/templates/aplicator/base.html`:

```html
{% load static %}
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>accel</title>
  <link rel="stylesheet" href="{% static 'aplicator/pico.min.css' %}">
</head>
<body>
  <nav>
    <a href="{% url 'aplicator:context' %}">Contexto</a>
    <a href="{% url 'aplicator:accelerator_add' %}">Aceleradoras</a>
    <a href="{% url 'aplicator:plan' %}">Plan</a>
    <a href="{% url 'aplicator:answer_bank' %}">Answer bank</a>
  </nav>
  {% if messages %}
    {% for message in messages %}
      <article>{{ message }}</article>
    {% endfor %}
  {% endif %}
  <main>
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

This drops the hand-written `<style>` block entirely — Pico.css styles `<nav>`, `<form>`, `<table>`, `<fieldset>`, `<button>`, `<article>` without any classes needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test aplicator.tests.test_static_assets`
Expected: `OK` (2 tests pass).

- [ ] **Step 5: Run the full suite and confirm nothing else broke**

Run: `python manage.py test`
Expected: `OK`, same test count as before plus 2.

- [ ] **Step 6: Commit**

```bash
git add aplicator/static aplicator/templates/aplicator/base.html aplicator/tests/test_static_assets.py
git commit -m "Vendor Pico.css and wire it into base.html"
```

---

### Task 2: Human-readable labels for category/focus enums

**Files:**
- Create: `aplicator/templatetags/__init__.py`
- Create: `aplicator/templatetags/aplicator_extras.py`
- Modify: `aplicator/templates/aplicator/plan.html`
- Modify: `aplicator/templates/aplicator/answer_bank.html`
- Test: `aplicator/tests/test_templatetags.py`

**Interfaces:**
- Consumes: `QuestionArchetype`, `VideoFocus` from `aplicator/models.py` (unchanged).
- Produces: two Django template filters, `category_label` and `focus_label`, registered under the `aplicator_extras` tag library — used by `plan.html` and `answer_bank.html` in this task, available for any future template.

- [ ] **Step 1: Write the failing test**

Create `aplicator/tests/test_templatetags.py`:

```python
from django.test import SimpleTestCase
from aplicator.templatetags.aplicator_extras import category_label, focus_label


class LabelFiltersTest(SimpleTestCase):
    def test_category_label_maps_known_value(self):
        self.assertEqual(category_label("why_now"), "Why now")

    def test_category_label_falls_back_to_raw_value(self):
        self.assertEqual(category_label("not_a_real_category"), "not_a_real_category")

    def test_focus_label_maps_known_value(self):
        self.assertEqual(focus_label("founder_intro"), "Founder intro")

    def test_focus_label_falls_back_to_raw_value(self):
        self.assertEqual(focus_label("not_a_real_focus"), "not_a_real_focus")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test aplicator.tests.test_templatetags`
Expected: FAIL with `ModuleNotFoundError: No module named 'aplicator.templatetags'`

- [ ] **Step 3: Write the filters**

Create `aplicator/templatetags/__init__.py` (empty file).

Create `aplicator/templatetags/aplicator_extras.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test aplicator.tests.test_templatetags`
Expected: `OK` (4 tests pass).

- [ ] **Step 5: Apply the filters in plan.html**

In `aplicator/templates/aplicator/plan.html`, add `{% load aplicator_extras %}` right after the `{% extends %}` line, then change:

```html
    <td>{{ group.category }}</td>
```
to:
```html
    <td>{{ group.category|category_label }}</td>
```

and change:
```html
    <td>{{ rec.focus }}</td>
```
to:
```html
    <td>{{ rec.focus|focus_label }}</td>
```

- [ ] **Step 6: Apply the filter in answer_bank.html**

In `aplicator/templates/aplicator/answer_bank.html`, add `{% load aplicator_extras %}` right after the `{% extends %}` line, then change:

```html
  <legend>{{ row.category }}</legend>
```
to:
```html
  <legend>{{ row.category|category_label }}</legend>
```

- [ ] **Step 7: Run the full suite**

Run: `python manage.py test`
Expected: `OK`, same count as before plus 4.

- [ ] **Step 8: Commit**

```bash
git add aplicator/templatetags aplicator/templates/aplicator/plan.html aplicator/templates/aplicator/answer_bank.html aplicator/tests/test_templatetags.py
git commit -m "Add human-readable labels for category/focus enums in plan and answer bank pages"
```

---

### Task 3: Type-aware review formset (the triggering complaint) + extraction flash message

**Files:**
- Modify: `aplicator/templates/aplicator/accelerator_review.html`
- Modify: `aplicator/views.py`
- Test: `aplicator/tests/test_accelerator_views.py`

**Interfaces:**
- Consumes: `QuestionFormSet` (unchanged, still `modelformset_factory(Question, fields=[...13 fields...], extra=0)` from Task 9 of the original plan), `Question.type` values (`"text"`, `"multiple_choice"`, `"video"`).
- Produces: no interface changes for other tasks — this is a template rewrite plus one `messages.info(...)` call.

**Important correctness note:** `Question.orientation`, `Question.language`, and `Question.who` do **not** have `blank=True` on the model (only `default="any"`), so their Django form fields are `required=True`. They must always be present in the POST data — as a visible field for `type == "video"` rows, and as a **hidden** field (`{{ form.orientation.as_hidden }}` etc.) for `text`/`multiple_choice` rows — never omitted entirely, or `formset.is_valid()` will fail for those rows. All other type-specific fields (`category`, `max_chars`, `options`, `allow_multiple`, `focus`, `min_seconds`, `max_seconds`) have `null=True, blank=True` and are safe to omit entirely when not applicable — Django treats their absence from POST as an empty value, which matches what's already stored for a non-applicable type.

- [ ] **Step 1: Write the failing tests**

Add to `aplicator/tests/test_accelerator_views.py` (new imports if not already present: `from aplicator.models import Question` should already be imported; no new imports needed beyond what's already at the top of the file):

```python
class AcceleratorReviewFieldRelevanceTest(TestCase):
    def setUp(self):
        self.accelerator = Accelerator.objects.create(accelerator_name="Field Relevance Co")
        self.text_q = Question.objects.create(
            accelerator=self.accelerator,
            type="text",
            original_text="What problem?",
            category="problem",
            max_chars=200,
        )
        self.video_q = Question.objects.create(
            accelerator=self.accelerator,
            type="video",
            original_text="Record a pitch",
            focus="pitch",
            min_seconds=60,
            max_seconds=90,
        )

    def test_text_question_does_not_render_video_only_fields(self):
        response = self.client.get(
            reverse("aplicator:accelerator_review", args=[self.accelerator.id])
        )
        content = response.content.decode()
        self.assertNotIn('name="form-0-focus"', content)
        self.assertNotIn('name="form-0-min_seconds"', content)
        self.assertNotIn('name="form-0-max_seconds"', content)

    def test_video_question_does_not_render_text_only_fields(self):
        response = self.client.get(
            reverse("aplicator:accelerator_review", args=[self.accelerator.id])
        )
        content = response.content.decode()
        self.assertNotIn('name="form-1-category"', content)
        self.assertNotIn('name="form-1-max_chars"', content)
        self.assertNotIn('name="form-1-options"', content)

    def test_mixed_types_save_successfully(self):
        management_data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-id": str(self.text_q.id),
            "form-0-type": "text",
            "form-0-original_text": "What problem?",
            "form-0-category": "solution",
            "form-0-max_chars": "200",
            "form-0-options": "[]",
            "form-0-orientation": "any",
            "form-0-language": "any",
            "form-0-who": "any",
            "form-1-id": str(self.video_q.id),
            "form-1-type": "video",
            "form-1-original_text": "Record a pitch",
            "form-1-focus": "pitch",
            "form-1-min_seconds": "60",
            "form-1-max_seconds": "90",
            "form-1-orientation": "h",
            "form-1-language": "en",
            "form-1-who": "solo",
            "form-1-options": "[]",
        }
        response = self.client.post(
            reverse("aplicator:accelerator_review", args=[self.accelerator.id]),
            management_data,
        )
        self.assertEqual(response.status_code, 302)
        self.text_q.refresh_from_db()
        self.assertEqual(self.text_q.category, "solution")


class AcceleratorAddFlashMessageTest(TestCase):
    @patch("aplicator.views.get_llm_port")
    def test_extraction_shows_flash_message_with_question_count(self, mock_get_llm_port):
        fake_llm = MagicMock()
        fake_llm.extract_form.return_value = {
            "accelerator_name": "Flash Co",
            "questions": [
                {"type": "text", "original_text": "Q1", "category": "problem"},
                {"type": "text", "original_text": "Q2", "category": "solution"},
            ],
        }
        mock_get_llm_port.return_value = fake_llm
        response = self.client.post(
            reverse("aplicator:accelerator_add"), {"raw_text": "..."}, follow=True
        )
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertIn("2", str(messages[0]))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test aplicator.tests.test_accelerator_views`
Expected: `test_text_question_does_not_render_video_only_fields` and `test_video_question_does_not_render_text_only_fields` FAIL (current template renders every field via `.as_p` for every row). `AcceleratorAddFlashMessageTest` FAILS with `len(messages) == 0` (no flash message yet).

- [ ] **Step 3: Rewrite the review template**

Replace `aplicator/templates/aplicator/accelerator_review.html`:

```html
{% extends "aplicator/base.html" %}
{% block content %}
<h1>Revisar {{ accelerator.accelerator_name }}</h1>
<form method="post">
  {% csrf_token %}
  {{ formset.management_form }}
  {% for form in formset %}
    <fieldset>
      <legend>{{ form.instance.get_type_display }}</legend>
      {{ form.id }}
      {{ form.type.as_hidden }}
      {{ form.original_text.as_field_group }}
      {{ form.is_required.as_field_group }}
      {% if form.instance.type == "text" %}
        {{ form.category.as_field_group }}
        {{ form.max_chars.as_field_group }}
        {{ form.orientation.as_hidden }}
        {{ form.language.as_hidden }}
        {{ form.who.as_hidden }}
      {% elif form.instance.type == "multiple_choice" %}
        {{ form.category.as_field_group }}
        {{ form.options.as_field_group }}
        {{ form.allow_multiple.as_field_group }}
        {{ form.orientation.as_hidden }}
        {{ form.language.as_hidden }}
        {{ form.who.as_hidden }}
      {% elif form.instance.type == "video" %}
        {{ form.focus.as_field_group }}
        {{ form.min_seconds.as_field_group }}
        {{ form.max_seconds.as_field_group }}
        {{ form.orientation.as_field_group }}
        {{ form.language.as_field_group }}
        {{ form.who.as_field_group }}
      {% endif %}
    </fieldset>
  {% endfor %}
  <button type="submit">Guardar</button>
</form>
{% endblock %}
```

- [ ] **Step 4: Add the flash message to accelerator_add_view**

In `aplicator/views.py`, add the import at the top (near the other Django imports):

```python
from django.contrib import messages
```

In `accelerator_add_view`, right before `return redirect("aplicator:accelerator_review", accelerator_id=accelerator.id)`, add:

```python
        question_count = len(extracted.get("questions", []))
        messages.info(
            request,
            f"Se extrajeron {question_count} preguntas — revisalas antes de continuar.",
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python manage.py test aplicator.tests.test_accelerator_views`
Expected: `OK`.

- [ ] **Step 6: Run the full suite**

Run: `python manage.py test`
Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add aplicator/templates/aplicator/accelerator_review.html aplicator/views.py aplicator/tests/test_accelerator_views.py
git commit -m "Make review formset type-aware (no irrelevant fields per question type), add extraction flash message"
```

---

### Task 4: Answer bank — show applicability and draft status

**Files:**
- Modify: `aplicator/views.py`
- Modify: `aplicator/templates/aplicator/answer_bank.html`
- Test: `aplicator/tests/test_answer_bank_view.py`

**Interfaces:**
- Consumes: `TextGroup.accelerator_names` (already computed by `group_text_questions`, previously discarded when building `rows` in `answer_bank_view`).
- Produces: each row dict passed to the template gains `accelerator_names: list[str]` — no change to any function signature.

- [ ] **Step 1: Write the failing test**

Add to `aplicator/tests/test_answer_bank_view.py`:

```python
class AnswerBankApplicabilityTest(TestCase):
    def test_shows_accelerator_names_and_no_draft_badge(self):
        a1 = Accelerator.objects.create(accelerator_name="founders.inc")
        a2 = Accelerator.objects.create(accelerator_name="Endeavor")
        Question.objects.create(
            accelerator=a1, type="text", original_text="What problem?",
            category=QuestionArchetype.PROBLEM, max_chars=300,
        )
        Question.objects.create(
            accelerator=a2, type="text", original_text="Describe the problem",
            category=QuestionArchetype.PROBLEM, max_chars=300,
        )
        response = self.client.get(reverse("aplicator:answer_bank"))
        self.assertContains(response, "founders.inc")
        self.assertContains(response, "Endeavor")
        self.assertContains(response, "sin borrador")

    def test_shows_draft_saved_badge_when_canonical_exists(self):
        acc = Accelerator.objects.create(accelerator_name="founders.inc")
        Question.objects.create(
            accelerator=acc, type="text", original_text="What problem?",
            category=QuestionArchetype.PROBLEM, max_chars=300,
        )
        CanonicalAnswer.objects.create(category=QuestionArchetype.PROBLEM, text="Draft answer.")
        response = self.client.get(reverse("aplicator:answer_bank"))
        self.assertContains(response, "borrador guardado")
```

(This file already imports `TestCase`, `reverse`, `Accelerator`, `Question`, `QuestionArchetype`, `CanonicalAnswer` from earlier tasks — if any are missing, add them to the existing import block at the top of the file rather than duplicating imports.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test aplicator.tests.test_answer_bank_view`
Expected: FAIL — neither "sin borrador" nor "borrador guardado" nor accelerator names appear in the current template.

- [ ] **Step 3: Update the view**

In `aplicator/views.py`, in `answer_bank_view`, change:

```python
    rows = [
        {"category": group.category, "canonical": canonical_by_category.get(group.category)}
        for group in group_text_questions(questions)
    ]
```

to:

```python
    rows = [
        {
            "category": group.category,
            "canonical": canonical_by_category.get(group.category),
            "accelerator_names": group.accelerator_names,
        }
        for group in group_text_questions(questions)
    ]
```

- [ ] **Step 4: Update the template**

In `aplicator/templates/aplicator/answer_bank.html`, add right after the `<legend>` line:

```html
  <p>
    Aplica a: {{ row.accelerator_names|join:", " }}
    — {% if row.canonical %}borrador guardado{% else %}sin borrador{% endif %}
  </p>
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python manage.py test aplicator.tests.test_answer_bank_view`
Expected: `OK`.

- [ ] **Step 6: Run the full suite**

Run: `python manage.py test`
Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add aplicator/views.py aplicator/templates/aplicator/answer_bank.html aplicator/tests/test_answer_bank_view.py
git commit -m "Show accelerator applicability and draft status on answer bank page"
```

---

### Task 5: Per-application answers — character count feedback and prompt fix

**Files:**
- Modify: `aplicator/views.py`
- Modify: `aplicator/templates/aplicator/application_answers.html`
- Test: `aplicator/tests/test_application_answers_view.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: each row dict in `application_answers_view` gains `answer_length: int` and `possibly_truncated: bool`. The LLM prompt built in the `generate` branch no longer contains the literal string `"Límite de caracteres: None"` when `question.max_chars` is `None`.

- [ ] **Step 1: Write the failing tests**

Add to `aplicator/tests/test_application_answers_view.py`:

```python
class ApplicationAnswersCharCountTest(TestCase):
    def setUp(self):
        self.accelerator = Accelerator.objects.create(accelerator_name="Char Count Co")

    def test_shows_char_count_and_truncation_warning_when_exact_limit(self):
        question = Question.objects.create(
            accelerator=self.accelerator, type="text",
            original_text="What problem?", category=QuestionArchetype.PROBLEM,
            max_chars=10,
        )
        GeneratedAnswer.objects.create(question=question, text="1234567890")
        response = self.client.get(
            reverse("aplicator:application_answers", args=[self.accelerator.id])
        )
        self.assertContains(response, "10/10")
        self.assertContains(response, "posible truncado")

    def test_no_truncation_warning_when_under_limit(self):
        question = Question.objects.create(
            accelerator=self.accelerator, type="text",
            original_text="What problem?", category=QuestionArchetype.PROBLEM,
            max_chars=500,
        )
        GeneratedAnswer.objects.create(question=question, text="short answer")
        response = self.client.get(
            reverse("aplicator:application_answers", args=[self.accelerator.id])
        )
        self.assertContains(response, "13/500")
        self.assertNotContains(response, "posible truncado")


class ApplicationAnswersPromptTest(TestCase):
    @patch("aplicator.views.get_llm_port")
    def test_generate_prompt_omits_none_when_max_chars_unset(self, mock_get_llm_port):
        accelerator = Accelerator.objects.create(accelerator_name="No Limit Co")
        question = Question.objects.create(
            accelerator=accelerator, type="text",
            original_text="What problem?", category=QuestionArchetype.PROBLEM,
            max_chars=None,
        )
        fake_llm = MagicMock()
        fake_llm.generate_text.return_value = "Generated answer."
        mock_get_llm_port.return_value = fake_llm

        self.client.post(
            reverse("aplicator:application_answers", args=[accelerator.id]),
            {"question_id": question.id, "text": "", "generate": "1"},
        )

        _, kwargs = fake_llm.generate_text.call_args
        self.assertNotIn("None", kwargs["prompt"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test aplicator.tests.test_application_answers_view`
Expected: FAIL — no char-count text in the response, and the prompt currently contains `"Límite de caracteres: None"`.

- [ ] **Step 3: Update the view**

In `aplicator/views.py`, in `application_answers_view`, replace the prompt-building block:

```python
            text = llm.generate_text(
                prompt=(
                    f"Adaptá esta respuesta al wording exacto y al límite de esta "
                    f"pregunta puntual.\nPregunta original: {question.original_text}\n"
                    f"Límite de caracteres: {question.max_chars}"
                ),
                context=context_text,
            )
```

with:

```python
            prompt_lines = [
                "Adaptá esta respuesta al wording exacto y al límite de esta pregunta puntual.",
                f"Pregunta original: {question.original_text}",
            ]
            if question.max_chars is not None:
                prompt_lines.append(f"Límite de caracteres: {question.max_chars}")
            text = llm.generate_text(prompt="\n".join(prompt_lines), context=context_text)
```

Then replace the row-building block:

```python
    rows = [
        {"question": q, "answer": GeneratedAnswer.objects.filter(question=q).first()}
        for q in questions
    ]
```

with:

```python
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
```

- [ ] **Step 4: Update the template**

In `aplicator/templates/aplicator/application_answers.html`, add right after the `<legend>` line:

```html
  <p>
    {{ row.answer_length }}/{{ row.question.max_chars|default:"sin límite" }} caracteres
    {% if row.possibly_truncated %}— posible truncado por límite{% endif %}
  </p>
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python manage.py test aplicator.tests.test_application_answers_view`
Expected: `OK`.

- [ ] **Step 6: Run the full suite**

Run: `python manage.py test`
Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add aplicator/views.py aplicator/templates/aplicator/application_answers.html aplicator/tests/test_application_answers_view.py
git commit -m "Show character count / truncation warning on application answers, fix None in LLM prompt"
```

---

### Task 6: Plan page — fix "None–None" character-limit display

**Files:**
- Modify: `aplicator/templates/aplicator/plan.html`
- Test: `aplicator/tests/test_plan_view.py`

**Interfaces:**
- Consumes: `TextGroup.min_max_chars`/`.max_max_chars` (unchanged, already `int | None`).
- Produces: no interface change — display-only fix.

- [ ] **Step 1: Write the failing test**

Add to `aplicator/tests/test_plan_view.py`:

```python
class PlanViewNoLimitDisplayTest(TestCase):
    def test_shows_sin_limite_when_no_question_has_max_chars(self):
        acc = Accelerator.objects.create(accelerator_name="No Limit Co")
        Question.objects.create(
            accelerator=acc, type="text", original_text="What problem?",
            category=QuestionArchetype.PROBLEM, max_chars=None,
        )
        response = self.client.get(reverse("aplicator:plan"))
        self.assertContains(response, "sin límite")
        self.assertNotContains(response, "None–None")
```

(Add `QuestionArchetype` to the file's existing import from `aplicator.models` if it isn't already imported.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test aplicator.tests.test_plan_view`
Expected: FAIL — current template renders `None–None`.

- [ ] **Step 3: Fix the template**

In `aplicator/templates/aplicator/plan.html`, change:

```html
    <td>{{ group.min_max_chars }}–{{ group.max_max_chars }}</td>
```

to:

```html
    <td>
      {% if group.min_max_chars %}{{ group.min_max_chars }}–{{ group.max_max_chars }}{% else %}sin límite{% endif %}
    </td>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test aplicator.tests.test_plan_view`
Expected: `OK`.

- [ ] **Step 5: Run the full suite**

Run: `python manage.py test`
Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add aplicator/templates/aplicator/plan.html aplicator/tests/test_plan_view.py
git commit -m "Fix None-None character-limit display on plan page"
```

---

### Task 7: Two-step delete confirmation and team member preview

**Files:**
- Modify: `aplicator/views.py`
- Modify: `aplicator/urls.py`
- Modify: `aplicator/templates/aplicator/context.html`
- Create: `aplicator/templates/aplicator/delete_confirm.html`
- Modify: `aplicator/tests/test_context_views.py`

**Interfaces:**
- Produces: URL names `aplicator:team_member_delete_confirm` and `aplicator:context_block_delete_confirm` (GET-only, renders a confirmation page, deletes nothing). The existing `aplicator:team_member_delete` / `aplicator:context_block_delete` POST endpoints (from the earlier context edit/delete feature) are unchanged — the confirm page's form POSTs to those same URLs.

- [ ] **Step 1: Write the failing tests**

Add to `aplicator/tests/test_context_views.py`:

```python
class TeamMemberDeleteConfirmViewTest(TestCase):
    def setUp(self):
        self.member = TeamMember.objects.create(
            name="Ada Lovelace", role="CTO", bio="Built the algorithm engine for early computers."
        )

    def test_get_confirm_page_does_not_delete(self):
        response = self.client.get(
            reverse("aplicator:team_member_delete_confirm", args=[self.member.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ada Lovelace")
        self.assertEqual(TeamMember.objects.count(), 1)

    def test_confirm_then_post_deletes(self):
        self.client.get(reverse("aplicator:team_member_delete_confirm", args=[self.member.id]))
        response = self.client.post(reverse("aplicator:team_member_delete", args=[self.member.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TeamMember.objects.count(), 0)


class ContextBlockDeleteConfirmViewTest(TestCase):
    def setUp(self):
        self.block = CompanyContextBlock.objects.create(label="traction", text="10 pilots.")

    def test_get_confirm_page_does_not_delete(self):
        response = self.client.get(
            reverse("aplicator:context_block_delete_confirm", args=[self.block.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "traction")
        self.assertEqual(CompanyContextBlock.objects.count(), 1)

    def test_confirm_then_post_deletes(self):
        self.client.get(reverse("aplicator:context_block_delete_confirm", args=[self.block.id]))
        response = self.client.post(
            reverse("aplicator:context_block_delete", args=[self.block.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CompanyContextBlock.objects.count(), 0)


class TeamMemberListPreviewTest(TestCase):
    def test_list_shows_bio_preview(self):
        TeamMember.objects.create(
            name="Ada Lovelace", role="CTO",
            bio="Built the algorithm engine for early computers.",
        )
        response = self.client.get(reverse("aplicator:context"))
        self.assertContains(response, "Built the algorithm")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test aplicator.tests.test_context_views`
Expected: FAIL with `NoReverseMatch` for the two new `_delete_confirm` URL names, and the preview test fails since bio isn't shown in the list yet.

- [ ] **Step 3: Add the confirm views**

In `aplicator/views.py`, add near the existing `team_member_delete_view`/`context_block_delete_view`:

```python
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
```

Add `reverse` to the existing `from django.urls import ...` import if not already present, or add a new line `from django.urls import reverse` near the top of `aplicator/views.py`.

- [ ] **Step 4: Add the URLs**

In `aplicator/urls.py`, add next to the existing `team_member_delete`/`context_block_delete` patterns:

```python
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
```

- [ ] **Step 5: Create the confirm template**

Create `aplicator/templates/aplicator/delete_confirm.html`:

```html
{% extends "aplicator/base.html" %}
{% block content %}
<h1>Confirmar borrado</h1>
<p>¿Confirmás borrar <strong>{{ label }}</strong>?</p>
<form method="post" action="{{ delete_url }}">
  {% csrf_token %}
  <button type="submit">Sí, borrar</button>
</form>
<p><a href="{% url 'aplicator:context' %}">Cancelar</a></p>
{% endblock %}
```

- [ ] **Step 6: Update context.html**

In `aplicator/templates/aplicator/context.html`, replace the team member list item:

```html
  <li>
    {{ member.name }} — {{ member.role }}
    (<a href="{% url 'aplicator:team_member_edit' member.id %}">editar</a> |
    <form method="post" action="{% url 'aplicator:team_member_delete' member.id %}" style="display:inline">
      {% csrf_token %}
      <button type="submit">borrar</button>
    </form>)
  </li>
```

with:

```html
  <li>
    {{ member.name }} — {{ member.role }}
    {% if member.bio or member.track_record %}
    <br><small>{{ member.bio|default:member.track_record|truncatewords:15 }}</small>
    {% endif %}
    (<a href="{% url 'aplicator:team_member_edit' member.id %}">editar</a> |
    <a href="{% url 'aplicator:team_member_delete_confirm' member.id %}">borrar</a>)
  </li>
```

Replace the context block list item:

```html
  <li>
    <strong>{{ block.label }}</strong>: {{ block.text|truncatewords:20 }}
    (<a href="{% url 'aplicator:context_block_edit' block.id %}">editar</a> |
    <form method="post" action="{% url 'aplicator:context_block_delete' block.id %}" style="display:inline">
      {% csrf_token %}
      <button type="submit">borrar</button>
    </form>)
  </li>
```

with:

```html
  <li>
    <strong>{{ block.label }}</strong>: {{ block.text|truncatewords:20 }}
    (<a href="{% url 'aplicator:context_block_edit' block.id %}">editar</a> |
    <a href="{% url 'aplicator:context_block_delete_confirm' block.id %}">borrar</a>)
  </li>
```

- [ ] **Step 7: Run test to verify it passes**

Run: `python manage.py test aplicator.tests.test_context_views`
Expected: `OK`. All prior tests in this file (including the earlier direct-POST-delete tests from the original edit/delete feature) must still pass unchanged — the underlying delete endpoints are untouched, only the UI path to reach them changed.

- [ ] **Step 8: Run the full suite**

Run: `python manage.py test`
Expected: `OK`.

- [ ] **Step 9: Commit**

```bash
git add aplicator/views.py aplicator/urls.py aplicator/templates/aplicator/context.html aplicator/templates/aplicator/delete_confirm.html aplicator/tests/test_context_views.py
git commit -m "Add two-step delete confirmation and team member bio/track-record preview"
```

---

## Final Verification

- [ ] **Run the full test suite**

```bash
python manage.py test
```

Expected: `OK`, all tests across `aplicator/tests/` pass (45 pre-existing + roughly 20 new from this plan).

- [ ] **Manual smoke test**

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` and walk the flow: confirm Pico.css is visibly styling the page → add/edit/delete a team member (confirm the two-step delete) → paste and extract a fake accelerator form, confirm the flash message shows the question count → open the review page, confirm a text question shows no video fields and a video question shows no text fields → check `/plan/` shows human-readable category/focus labels and "sin límite" instead of "None–None" → check `/answer-bank/` shows which accelerators use each category and the draft/no-draft badge → check a per-application answer shows its character count and, if at the limit, the truncation note.
