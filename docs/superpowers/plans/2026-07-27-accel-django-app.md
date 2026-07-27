# Accel Django App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the accel v0 as a local Django webapp: paste accelerator forms, extract them via LLM into structured questions, review/edit, see a pure-code plan (answer-bank grouping + video recording grouping + marginal cost ranking), maintain an answer bank, and generate per-application answers under exact character limits.

**Architecture:** Single Django project (`accel`) + single app (`aplicator`), SQLite, no auth, full-page-reload templates. An `LLMPort` abstract interface decouples model calls from an OpenAI adapter (DeepSeek reuses it via base_url/model config, same SDK shape). The planner is pure Python functions with zero DB writes and zero LLM calls, called live from the plan view.

**Tech Stack:** Python 3, Django, SQLite, `openai` SDK (covers both OpenAI and DeepSeek), pytest-style asserts via Django's `TestCase`.

## Global Constraints

- `contracts.py` at the repo root is the reference contract — do not modify it; Django models must mirror its shape (discriminated union by `type`, `QuestionArchetype` enum, `NON_SHAREABLE` set, `VideoFocus` enum, `any` as default for orientation/language/who).
- Character limits are validated in code, never trusted from LLM output.
- The plan (text grouping, video grouping, marginal cost ranking) is never persisted — no `Plan` model, always computed live in the view.
- No JS/HTMX — Django templates, full page reload.
- No auth, no deploy config — local only (`manage.py runserver`).
- Missing company-context data must never be invented by the LLM — generation prompts must instruct a visible "[FALTA: ...]" marker instead.

---

### Task 1: Django project scaffold + company context models

**Files:**
- Create: `requirements.txt`
- Create: `accel/` (Django project, via `startproject`) — `accel/settings.py`, `accel/urls.py`, `accel/wsgi.py`, `accel/asgi.py`
- Create: `aplicator/` (Django app, via `startapp`) — `aplicator/models.py`, `aplicator/admin.py`, `aplicator/apps.py`
- Test: `aplicator/tests/__init__.py`, `aplicator/tests/test_context_models.py`

**Interfaces:**
- Produces: `TeamMember` model (fields: `name`, `role`, `bio`, `track_record`, `notable_projects` — all `TextField`, `name`/`role` required, rest optional) and `CompanyContextBlock` model (fields: `label` CharField, `text` TextField) — both used by later context-UI and generation tasks.

- [ ] **Step 1: Install Django and scaffold the project**

```bash
cd /home/bautista/zent/vc-aplicator
python3 -m venv venv
source venv/bin/activate
pip install django openai
pip freeze > requirements.txt
django-admin startproject accel .
python manage.py startapp aplicator
```

- [ ] **Step 2: Register the app and point settings at SQLite (already the Django default)**

Edit `accel/settings.py`, add `"aplicator"` to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "aplicator",
]
```

- [ ] **Step 3: Write the failing test for the context models**

Create `aplicator/tests/__init__.py` (empty file) and delete the auto-generated `aplicator/tests.py` if `startapp` created one instead of a package.

Create `aplicator/tests/test_context_models.py`:

```python
from django.test import TestCase
from aplicator.models import TeamMember, CompanyContextBlock


class TeamMemberModelTest(TestCase):
    def test_create_team_member(self):
        member = TeamMember.objects.create(
            name="Ada Lovelace",
            role="CTO",
            bio="Built the first algorithm.",
            track_record="Shipped the Analytical Engine software.",
            notable_projects="Notes on the Analytical Engine.",
        )
        self.assertEqual(TeamMember.objects.count(), 1)
        self.assertEqual(member.name, "Ada Lovelace")

    def test_track_record_and_projects_optional(self):
        member = TeamMember.objects.create(name="Grace Hopper", role="CEO")
        self.assertEqual(member.track_record, "")
        self.assertEqual(member.notable_projects, "")


class CompanyContextBlockModelTest(TestCase):
    def test_create_block(self):
        block = CompanyContextBlock.objects.create(
            label="traction", text="10 pilot customers, $5k MRR."
        )
        self.assertEqual(str(block), "traction")
        self.assertEqual(CompanyContextBlock.objects.count(), 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test aplicator.tests.test_context_models`
Expected: FAIL with `ImportError: cannot import name 'TeamMember'`

- [ ] **Step 3: Write the models**

`aplicator/models.py`:

```python
from django.db import models


class TeamMember(models.Model):
    name = models.CharField(max_length=200)
    role = models.CharField(max_length=200)
    bio = models.TextField(blank=True, default="")
    track_record = models.TextField(blank=True, default="")
    notable_projects = models.TextField(blank=True, default="")

    def __str__(self):
        return self.name


class CompanyContextBlock(models.Model):
    label = models.CharField(max_length=100)
    text = models.TextField()

    def __str__(self):
        return self.label
```

- [ ] **Step 4: Register in admin, migrate, run test**

`aplicator/admin.py`:

```python
from django.contrib import admin
from aplicator.models import TeamMember, CompanyContextBlock

admin.site.register(TeamMember)
admin.site.register(CompanyContextBlock)
```

```bash
python manage.py makemigrations aplicator
python manage.py migrate
python manage.py test aplicator.tests.test_context_models
```

Expected: `OK` (3 tests pass).

- [ ] **Step 5: Commit**

```bash
git add requirements.txt accel aplicator manage.py
git commit -m "Scaffold Django project and add company context models"
```

---

### Task 2: Accelerator & Question models (mirrors contracts.py)

**Files:**
- Modify: `aplicator/models.py`
- Modify: `aplicator/admin.py`
- Test: `aplicator/tests/test_question_models.py`

**Interfaces:**
- Consumes: nothing new from Task 1.
- Produces: `Accelerator` model (`accelerator_name`, `url`, `deadline` [DateField, nullable], `raw_text`); `Question` model with `type` in `{"text","multiple_choice","video"}`, FK `accelerator`, and per-type fields as below; `QuestionArchetype` TextChoices; `NON_SHAREABLE` frozenset of `QuestionArchetype` values; `VideoFocus` TextChoices. Later tasks (planner, answer bank) import `QuestionArchetype`, `NON_SHAREABLE`, `VideoFocus`, `Question`, `Accelerator` from `aplicator.models`.

- [ ] **Step 1: Write the failing test**

Create `aplicator/tests/test_question_models.py`:

```python
import datetime
from django.test import TestCase
from aplicator.models import (
    Accelerator,
    Question,
    QuestionArchetype,
    NON_SHAREABLE,
    VideoFocus,
)


class AcceleratorModelTest(TestCase):
    def test_create_accelerator(self):
        acc = Accelerator.objects.create(
            accelerator_name="founders.inc",
            url="https://founders.inc/apply",
            deadline=datetime.date(2026, 9, 1),
            raw_text="pasted form text...",
        )
        self.assertEqual(str(acc), "founders.inc")


class QuestionModelTest(TestCase):
    def setUp(self):
        self.acc = Accelerator.objects.create(accelerator_name="Endeavor")

    def test_text_question(self):
        q = Question.objects.create(
            accelerator=self.acc,
            type="text",
            original_text="What problem do you solve?",
            category=QuestionArchetype.PROBLEM,
            max_chars=500,
        )
        self.assertEqual(q.category, "problem")
        self.assertIsNone(q.focus)

    def test_video_question_defaults_to_any(self):
        q = Question.objects.create(
            accelerator=self.acc,
            type="video",
            original_text="Record a 2 min pitch.",
            focus=VideoFocus.PITCH,
            min_seconds=60,
            max_seconds=120,
        )
        self.assertEqual(q.orientation, "any")
        self.assertEqual(q.language, "any")
        self.assertEqual(q.who, "any")

    def test_non_shareable_set(self):
        self.assertIn(QuestionArchetype.WHY_THIS_PROGRAM, NON_SHAREABLE)
        self.assertIn(QuestionArchetype.LEGAL_ADMIN, NON_SHAREABLE)
        self.assertIn(QuestionArchetype.OTHER, NON_SHAREABLE)
        self.assertNotIn(QuestionArchetype.PROBLEM, NON_SHAREABLE)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test aplicator.tests.test_question_models`
Expected: FAIL with `ImportError: cannot import name 'Accelerator'`

- [ ] **Step 3: Write the models**

Append to `aplicator/models.py`:

```python
class QuestionArchetype(models.TextChoices):
    PROBLEM = "problem", "Problem"
    SOLUTION = "solution", "Solution"
    WHY_NOW = "why_now", "Why now"
    WHY_YOU = "why_you", "Why you"
    TEAM = "team", "Team"
    TRACTION = "traction", "Traction"
    BUSINESS_MODEL = "business_model", "Business model"
    MARKET_SIZE = "market_size", "Market size"
    COMPETITION = "competition", "Competition"
    MOAT = "moat", "Moat"
    GTM = "gtm", "GTM"
    PRODUCT_DEMO = "product_demo", "Product demo"
    TECH = "tech", "Tech"
    MILESTONES = "milestones", "Milestones"
    ASK = "ask", "Ask"
    USE_OF_FUNDS = "use_of_funds", "Use of funds"
    RISKS = "risks", "Risks"
    FAILURE_STORY = "failure_story", "Failure story"
    WHY_THIS_PROGRAM = "why_this_program", "Why this program"
    LEGAL_ADMIN = "legal_admin", "Legal admin"
    OTHER = "other", "Other"


NON_SHAREABLE = frozenset(
    {
        QuestionArchetype.WHY_THIS_PROGRAM,
        QuestionArchetype.LEGAL_ADMIN,
        QuestionArchetype.OTHER,
    }
)


class VideoFocus(models.TextChoices):
    FOUNDER_INTRO = "founder_intro", "Founder intro"
    PITCH = "pitch", "Pitch"
    DEMO = "demo", "Demo"


class Accelerator(models.Model):
    accelerator_name = models.CharField(max_length=200)
    url = models.URLField(blank=True, default="")
    deadline = models.DateField(null=True, blank=True)
    raw_text = models.TextField(blank=True, default="")

    def __str__(self):
        return self.accelerator_name


class Question(models.Model):
    TYPE_CHOICES = [
        ("text", "Text"),
        ("multiple_choice", "Multiple choice"),
        ("video", "Video"),
    ]
    ORIENTATION_CHOICES = [("h", "Horizontal"), ("v", "Vertical"), ("any", "Any")]
    LANGUAGE_CHOICES = [("es", "Spanish"), ("en", "English"), ("any", "Any")]
    WHO_CHOICES = [("solo", "Solo"), ("all_founders", "All founders"), ("any", "Any")]

    accelerator = models.ForeignKey(
        Accelerator, on_delete=models.CASCADE, related_name="questions"
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    original_text = models.TextField()
    is_required = models.BooleanField(default=True)

    # text / multiple_choice fields
    category = models.CharField(
        max_length=30, choices=QuestionArchetype.choices, null=True, blank=True
    )
    max_chars = models.IntegerField(null=True, blank=True)
    options = models.JSONField(default=list, blank=True)
    allow_multiple = models.BooleanField(default=False)

    # video fields
    focus = models.CharField(
        max_length=20, choices=VideoFocus.choices, null=True, blank=True
    )
    min_seconds = models.IntegerField(null=True, blank=True)
    max_seconds = models.IntegerField(null=True, blank=True)
    orientation = models.CharField(
        max_length=5, choices=ORIENTATION_CHOICES, default="any"
    )
    language = models.CharField(
        max_length=5, choices=LANGUAGE_CHOICES, default="any"
    )
    who = models.CharField(max_length=15, choices=WHO_CHOICES, default="any")

    def __str__(self):
        return f"[{self.type}] {self.original_text[:50]}"
```

- [ ] **Step 4: Register in admin, migrate, run test**

Append to `aplicator/admin.py`:

```python
from aplicator.models import Accelerator, Question

admin.site.register(Accelerator)
admin.site.register(Question)
```

```bash
python manage.py makemigrations aplicator
python manage.py migrate
python manage.py test aplicator.tests.test_question_models
```

Expected: `OK` (4 tests pass).

- [ ] **Step 5: Commit**

```bash
git add aplicator
git commit -m "Add Accelerator and Question models mirroring contracts.py"
```

---

### Task 3: CanonicalAnswer & GeneratedAnswer models

**Files:**
- Modify: `aplicator/models.py`
- Modify: `aplicator/admin.py`
- Test: `aplicator/tests/test_answer_models.py`

**Interfaces:**
- Consumes: `QuestionArchetype` and `Question` from Task 2.
- Produces: `CanonicalAnswer` (`category` unique CharField, `text` TextField) and `GeneratedAnswer` (`question` OneToOneField to `Question`, `text` TextField) — both used by the answer-bank and per-application-answers UI tasks (9-12... see Task 11/12).

- [ ] **Step 1: Write the failing test**

Create `aplicator/tests/test_answer_models.py`:

```python
from django.test import TestCase
from aplicator.models import (
    Accelerator,
    Question,
    QuestionArchetype,
    CanonicalAnswer,
    GeneratedAnswer,
)


class CanonicalAnswerModelTest(TestCase):
    def test_create_and_unique_category(self):
        CanonicalAnswer.objects.create(
            category=QuestionArchetype.PROBLEM, text="Long canonical answer."
        )
        self.assertEqual(CanonicalAnswer.objects.count(), 1)
        with self.assertRaises(Exception):
            CanonicalAnswer.objects.create(
                category=QuestionArchetype.PROBLEM, text="Duplicate."
            )


class GeneratedAnswerModelTest(TestCase):
    def test_create(self):
        acc = Accelerator.objects.create(accelerator_name="Techstars")
        q = Question.objects.create(
            accelerator=acc,
            type="text",
            original_text="What problem?",
            category=QuestionArchetype.PROBLEM,
            max_chars=250,
        )
        answer = GeneratedAnswer.objects.create(question=q, text="Adapted answer.")
        self.assertEqual(q.generatedanswer, answer)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test aplicator.tests.test_answer_models`
Expected: FAIL with `ImportError: cannot import name 'CanonicalAnswer'`

- [ ] **Step 3: Write the models**

Append to `aplicator/models.py`:

```python
class CanonicalAnswer(models.Model):
    category = models.CharField(
        max_length=30, choices=QuestionArchetype.choices, unique=True
    )
    text = models.TextField()

    def __str__(self):
        return self.category


class GeneratedAnswer(models.Model):
    question = models.OneToOneField(Question, on_delete=models.CASCADE)
    text = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Answer for {self.question_id}"
```

- [ ] **Step 4: Register in admin, migrate, run test**

Append to `aplicator/admin.py`:

```python
from aplicator.models import CanonicalAnswer, GeneratedAnswer

admin.site.register(CanonicalAnswer)
admin.site.register(GeneratedAnswer)
```

```bash
python manage.py makemigrations aplicator
python manage.py migrate
python manage.py test aplicator.tests.test_answer_models
```

Expected: `OK` (2 tests pass).

- [ ] **Step 5: Commit**

```bash
git add aplicator
git commit -m "Add CanonicalAnswer and GeneratedAnswer models"
```

---

### Task 4: Planner — text axis (group by category)

**Files:**
- Create: `aplicator/planner.py`
- Test: `aplicator/tests/test_planner.py`

**Interfaces:**
- Consumes: `Question`, `QuestionArchetype`, `NON_SHAREABLE` from `aplicator.models` (Task 2).
- Produces: `TextGroup` dataclass (`category: str`, `questions: list[Question]`, `min_max_chars: int | None`, `max_max_chars: int | None`, `accelerator_names: list[str]`) and `group_text_questions(questions: Iterable[Question]) -> list[TextGroup]`, sorted by `category`. Used by Task 10 (plan view) and Task 12 (answer bank view, to know which categories are in use).

- [ ] **Step 1: Write the failing test**

Create `aplicator/tests/test_planner.py`:

```python
from django.test import TestCase
from aplicator.models import Accelerator, Question, QuestionArchetype
from aplicator.planner import group_text_questions


class GroupTextQuestionsTest(TestCase):
    def setUp(self):
        self.a1 = Accelerator.objects.create(accelerator_name="founders.inc")
        self.a2 = Accelerator.objects.create(accelerator_name="Endeavor")

    def test_groups_same_category_across_accelerators(self):
        Question.objects.create(
            accelerator=self.a1,
            type="text",
            original_text="What problem?",
            category=QuestionArchetype.PROBLEM,
            max_chars=500,
        )
        Question.objects.create(
            accelerator=self.a2,
            type="text",
            original_text="Describe the problem",
            category=QuestionArchetype.PROBLEM,
            max_chars=250,
        )
        groups = group_text_questions(Question.objects.all())
        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertEqual(group.category, "problem")
        self.assertEqual(len(group.questions), 2)
        self.assertEqual(group.min_max_chars, 250)
        self.assertEqual(group.max_max_chars, 500)
        self.assertEqual(group.accelerator_names, ["Endeavor", "founders.inc"])

    def test_excludes_non_shareable_categories(self):
        Question.objects.create(
            accelerator=self.a1,
            type="text",
            original_text="Why this program?",
            category=QuestionArchetype.WHY_THIS_PROGRAM,
            max_chars=200,
        )
        groups = group_text_questions(Question.objects.all())
        self.assertEqual(groups, [])

    def test_excludes_video_questions(self):
        Question.objects.create(
            accelerator=self.a1,
            type="video",
            original_text="Record a pitch",
            focus="pitch",
            min_seconds=60,
            max_seconds=120,
        )
        groups = group_text_questions(Question.objects.all())
        self.assertEqual(groups, [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test aplicator.tests.test_planner`
Expected: FAIL with `ModuleNotFoundError: No module named 'aplicator.planner'`

- [ ] **Step 3: Write the implementation**

Create `aplicator/planner.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test aplicator.tests.test_planner`
Expected: `OK` (3 tests pass).

- [ ] **Step 5: Commit**

```bash
git add aplicator
git commit -m "Add planner text axis: group_text_questions by category"
```

---

### Task 5: Planner — video axis (focus, dimensions, duration)

**Files:**
- Modify: `aplicator/planner.py`
- Modify: `aplicator/tests/test_planner.py`

**Interfaces:**
- Consumes: `Question` (Task 2).
- Produces: `Recording` dataclass (`focus: str`, `orientation: str`, `language: str`, `who: str`, `record_seconds: int`, `master_question: Question`, `derived_cut_questions: list[Question]`) and `group_video_questions(questions: Iterable[Question]) -> list[Recording]`. Used by Task 10 (plan view) and Task 6 (marginal cost ranking, to know which video questions are already covered).

**Design note (recorded here, not just in code comments):** because a recording can always be *trimmed down* to satisfy a shorter window but never extended, one recording per resolved dimension-group always suffices — record the video with the largest `max_seconds` (the group's master) at its own max, and every other video in the group becomes a derived cut of it. This is a strict generalization of the brief's two illustrative cases (overlapping windows, and the ≤60s/≥90s non-overlapping example) into one code path — no recursion or leftover-grouping is needed.

- [ ] **Step 1: Write the failing tests**

Append to `aplicator/tests/test_planner.py`:

```python
from aplicator.planner import group_video_questions


class GroupVideoQuestionsTest(TestCase):
    def setUp(self):
        self.acc = Accelerator.objects.create(accelerator_name="YC")

    def _video(self, **kwargs):
        defaults = dict(
            accelerator=self.acc,
            type="video",
            original_text="video question",
            focus="pitch",
        )
        defaults.update(kwargs)
        return Question.objects.create(**defaults)

    def test_any_orientation_absorbed_into_concrete_group(self):
        self._video(orientation="v", min_seconds=60, max_seconds=90)
        self._video(orientation="any", min_seconds=60, max_seconds=90)
        recordings = group_video_questions(Question.objects.all())
        self.assertEqual(len(recordings), 1)
        self.assertEqual(recordings[0].orientation, "v")

    def test_two_concrete_orientations_split(self):
        self._video(orientation="h", min_seconds=60, max_seconds=90)
        self._video(orientation="v", min_seconds=60, max_seconds=90)
        recordings = group_video_questions(Question.objects.all())
        self.assertEqual(len(recordings), 2)
        orientations = sorted(r.orientation for r in recordings)
        self.assertEqual(orientations, ["h", "v"])

    def test_different_focus_never_merges(self):
        self._video(focus="pitch", min_seconds=60, max_seconds=90)
        self._video(focus="demo", min_seconds=60, max_seconds=90)
        recordings = group_video_questions(Question.objects.all())
        self.assertEqual(len(recordings), 2)

    def test_non_overlapping_windows_produce_master_and_derived_cut(self):
        short = self._video(min_seconds=10, max_seconds=20)
        long = self._video(min_seconds=90, max_seconds=180)
        recordings = group_video_questions(Question.objects.all())
        self.assertEqual(len(recordings), 1)
        rec = recordings[0]
        self.assertEqual(rec.master_question, long)
        self.assertEqual(rec.record_seconds, 180)
        self.assertEqual(rec.derived_cut_questions, [short])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test aplicator.tests.test_planner.GroupVideoQuestionsTest`
Expected: FAIL with `ImportError: cannot import name 'group_video_questions'`

- [ ] **Step 3: Write the implementation**

Append to `aplicator/planner.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test aplicator.tests.test_planner`
Expected: `OK` (all tests in the file pass, 7 total).

- [ ] **Step 5: Commit**

```bash
git add aplicator
git commit -m "Add planner video axis: group_video_questions by focus/dimensions/duration"
```

---

### Task 6: Planner — marginal cost ranking

**Files:**
- Modify: `aplicator/planner.py`
- Modify: `aplicator/tests/test_planner.py`

**Interfaces:**
- Consumes: `group_text_questions`, `group_video_questions` (Task 4, 5), `NON_SHAREABLE` (Task 2).
- Produces: `rank_accelerators(accelerators: Iterable[Accelerator], questions: Iterable[Question]) -> list[Accelerator]`, sorted ascending by exclusive effort then by `deadline` (nulls last). Used by Task 10 (plan view).

An accelerator's "exclusive count" is: its own `NON_SHAREABLE`-category questions (never shared, one unit each) + text categories where it is the *only* accelerator in that `TextGroup` + video recordings where it is the *only* accelerator among the recording's covered questions (master + derived cuts).

- [ ] **Step 1: Write the failing tests**

Append to `aplicator/tests/test_planner.py`:

```python
import datetime
from aplicator.planner import rank_accelerators


class RankAcceleratorsTest(TestCase):
    def test_ranks_by_exclusive_count_then_deadline(self):
        cheap = Accelerator.objects.create(
            accelerator_name="cheap", deadline=datetime.date(2026, 12, 1)
        )
        expensive = Accelerator.objects.create(
            accelerator_name="expensive", deadline=datetime.date(2026, 8, 1)
        )
        # shared category: costs nothing extra for either
        Question.objects.create(
            accelerator=cheap,
            type="text",
            original_text="problem?",
            category=QuestionArchetype.PROBLEM,
            max_chars=300,
        )
        Question.objects.create(
            accelerator=expensive,
            type="text",
            original_text="problem?",
            category=QuestionArchetype.PROBLEM,
            max_chars=300,
        )
        # exclusive, non-shareable question, only on "expensive"
        Question.objects.create(
            accelerator=expensive,
            type="text",
            original_text="Why this program?",
            category=QuestionArchetype.WHY_THIS_PROGRAM,
            max_chars=200,
        )
        questions = Question.objects.select_related("accelerator").all()
        ranked = rank_accelerators([cheap, expensive], questions)
        self.assertEqual([a.accelerator_name for a in ranked], ["cheap", "expensive"])

    def test_deadline_tiebreak_when_exclusive_count_equal(self):
        earlier = Accelerator.objects.create(
            accelerator_name="earlier", deadline=datetime.date(2026, 8, 1)
        )
        later = Accelerator.objects.create(
            accelerator_name="later", deadline=datetime.date(2026, 12, 1)
        )
        ranked = rank_accelerators([later, earlier], [])
        self.assertEqual([a.accelerator_name for a in ranked], ["earlier", "later"])

    def test_exclusive_video_recording_counts_against_owner(self):
        solo = Accelerator.objects.create(accelerator_name="solo")
        shared_a = Accelerator.objects.create(accelerator_name="shared_a")
        shared_b = Accelerator.objects.create(accelerator_name="shared_b")
        Question.objects.create(
            accelerator=solo,
            type="video",
            original_text="pitch",
            focus="pitch",
            min_seconds=60,
            max_seconds=90,
        )
        Question.objects.create(
            accelerator=shared_a,
            type="video",
            original_text="pitch",
            focus="demo",
            min_seconds=60,
            max_seconds=90,
        )
        Question.objects.create(
            accelerator=shared_b,
            type="video",
            original_text="pitch",
            focus="demo",
            min_seconds=60,
            max_seconds=90,
        )
        questions = Question.objects.select_related("accelerator").all()
        ranked = rank_accelerators([solo, shared_a, shared_b], questions)
        self.assertEqual(ranked[0].accelerator_name, "shared_a")
        self.assertEqual(ranked[1].accelerator_name, "shared_b")
        self.assertEqual(ranked[2].accelerator_name, "solo")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test aplicator.tests.test_planner.RankAcceleratorsTest`
Expected: FAIL with `ImportError: cannot import name 'rank_accelerators'`

- [ ] **Step 3: Write the implementation**

Append to `aplicator/planner.py`:

```python
import datetime


def rank_accelerators(accelerators, questions):
    accelerators = list(accelerators)
    questions = list(questions)
    text_groups = group_text_questions(questions)
    recordings = group_video_questions(questions)

    def exclusive_count(acc):
        count = sum(
            1
            for q in questions
            if q.accelerator_id == acc.id
            and q.type in ("text", "multiple_choice")
            and q.category in NON_SHAREABLE
        )
        for group in text_groups:
            if group.accelerator_names == [acc.accelerator_name]:
                count += 1
        for rec in recordings:
            covered = [rec.master_question, *rec.derived_cut_questions]
            names = {q.accelerator.accelerator_name for q in covered}
            if names == {acc.accelerator_name}:
                count += 1
        return count

    return sorted(
        accelerators,
        key=lambda acc: (
            exclusive_count(acc),
            acc.deadline or datetime.date.max,
        ),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test aplicator.tests.test_planner`
Expected: `OK` (all tests in the file pass, 10 total).

- [ ] **Step 5: Commit**

```bash
git add aplicator
git commit -m "Add planner marginal-cost ranking: rank_accelerators"
```

---

### Task 7: LLMPort interface + OpenAI/DeepSeek adapter

**Files:**
- Create: `aplicator/llm/__init__.py`
- Create: `aplicator/llm/port.py`
- Create: `aplicator/llm/openai_adapter.py`
- Test: `aplicator/tests/test_llm_adapter.py`

**Interfaces:**
- Produces: `LLMPort` ABC with `extract_form(raw_text: str) -> dict` and `generate_text(prompt: str, context: str) -> str`; `OpenAIAdapter(LLMPort)` implementing both, constructed as `OpenAIAdapter(api_key, model="gpt-4o-mini", base_url=None, client=None)`. DeepSeek is the *same* class with `base_url="https://api.deepseek.com"` and `model="deepseek-chat"` — same SDK shape, no separate adapter needed. Used by Task 9 (extract view) and Task 12/13 (generate view).

- [ ] **Step 1: Write the failing tests**

Create `aplicator/tests/test_llm_adapter.py`:

```python
import json
from unittest import TestCase
from unittest.mock import MagicMock
from aplicator.llm.openai_adapter import OpenAIAdapter


def _fake_chat_client(content):
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    client.chat.completions.create.return_value = response
    return client


class OpenAIAdapterTest(TestCase):
    def test_extract_form_parses_json_response(self):
        payload = {
            "accelerator_name": "founders.inc",
            "url": None,
            "deadline": None,
            "questions": [{"type": "text", "original_text": "What problem?"}],
        }
        client = _fake_chat_client(json.dumps(payload))
        adapter = OpenAIAdapter(api_key="fake", client=client)

        result = adapter.extract_form("pasted form text")

        self.assertEqual(result["accelerator_name"], "founders.inc")
        self.assertEqual(len(result["questions"]), 1)
        client.chat.completions.create.assert_called_once()

    def test_generate_text_returns_message_content(self):
        client = _fake_chat_client("Generated answer text.")
        adapter = OpenAIAdapter(api_key="fake", client=client)

        result = adapter.generate_text(prompt="Write the problem answer", context="We solve X.")

        self.assertEqual(result, "Generated answer text.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test aplicator.tests.test_llm_adapter`
Expected: FAIL with `ModuleNotFoundError: No module named 'aplicator.llm'`

- [ ] **Step 3: Write the implementation**

Create `aplicator/llm/__init__.py` (empty file).

Create `aplicator/llm/port.py`:

```python
from abc import ABC, abstractmethod


class LLMPort(ABC):
    @abstractmethod
    def extract_form(self, raw_text: str) -> dict:
        """Parse pasted accelerator-form text into a dict shaped like
        contracts.AcceleratorForm: accelerator_name, url, deadline, and a
        list of question dicts, each with 'type' plus its type-specific
        fields."""

    @abstractmethod
    def generate_text(self, prompt: str, context: str) -> str:
        """Generate text for `prompt` grounded only in `context`."""
```

Create `aplicator/llm/openai_adapter.py`:

```python
import json

from openai import OpenAI

from aplicator.llm.port import LLMPort

EXTRACTION_SYSTEM_PROMPT = """Sos un extractor de formularios de aceleradoras.
Te paso el texto crudo pegado de un formulario (puede incluir menús, footers,
botones — ignoralos). Devolvé UN JSON con esta forma exacta:

{
  "accelerator_name": str,
  "url": str | null,
  "deadline": "YYYY-MM-DD" | null,
  "questions": [
    {
      "type": "text" | "multiple_choice" | "video",
      "original_text": str,
      "is_required": bool,
      // si type == "text" o "multiple_choice":
      "category": uno de [problem, solution, why_now, why_you, team, traction,
        business_model, market_size, competition, moat, gtm, product_demo,
        tech, milestones, ask, use_of_funds, risks, failure_story,
        why_this_program, legal_admin, other],
      "max_chars": int | null,   // si el form da un límite en palabras, convertilo a caracteres (palabras * 6)
      // si type == "multiple_choice" además:
      "options": [str],
      "allow_multiple": bool,
      // si type == "video":
      "focus": "founder_intro" | "pitch" | "demo",
      "min_seconds": int | null,
      "max_seconds": int | null,
      "orientation": "h" | "v" | "any",   // "any" si el form no lo aclara
      "language": "es" | "en" | "any",     // "any" si el form no lo aclara
      "who": "solo" | "all_founders" | "any"  // "any" si el form no lo aclara
    }
  ]
}

Regla dura: nunca inventes una restricción (orientación, idioma, quién
aparece) que el form no pida explícitamente — usá "any" por defecto."""

GENERATION_SYSTEM_PROMPT = """Sos un asistente que escribe respuestas para
formularios de aceleradoras, en la voz del founder, con tono específico y
sobrio: números, nombres, fechas, cero lenguaje de pitch inflado
("revolucionario", "disruptivo"). Usá EXCLUSIVAMENTE el contexto de empresa
provisto. Si un dato necesario no está en ese contexto, escribí el marcador
visible "[FALTA: <qué dato falta>]" en su lugar — nunca inventes métricas,
nombres de clientes ni fechas."""


class OpenAIAdapter(LLMPort):
    def __init__(self, api_key=None, model="gpt-4o-mini", base_url=None, client=None):
        self.client = client or OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def extract_form(self, raw_text: str) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)

    def generate_text(self, prompt: str, context: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
                {"role": "user", "content": f"Contexto de la empresa:\n{context}\n\nTarea:\n{prompt}"},
            ],
        )
        return response.choices[0].message.content
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test aplicator.tests.test_llm_adapter`
Expected: `OK` (2 tests pass).

- [ ] **Step 5: Commit**

```bash
git add aplicator
git commit -m "Add LLMPort interface and OpenAI/DeepSeek adapter"
```

---

### Task 8: Company context UI (base template + urls + context page)

**Files:**
- Modify: `accel/urls.py`
- Create: `aplicator/urls.py`
- Create: `aplicator/views.py`
- Create: `aplicator/forms.py`
- Create: `aplicator/templates/aplicator/base.html`
- Create: `aplicator/templates/aplicator/context.html`
- Test: `aplicator/tests/test_context_views.py`

**Interfaces:**
- Produces: URL name `aplicator:context` (GET renders the page, POST with `add_member` or `add_block` in the body creates a `TeamMember`/`CompanyContextBlock`); `TeamMemberForm`, `CompanyContextBlockForm` (`ModelForm`s); `aplicator/templates/aplicator/base.html` with a `{% block content %}` and a `<nav>` that later tasks append links to.

- [ ] **Step 1: Write the failing test**

Create `aplicator/tests/test_context_views.py`:

```python
from django.test import TestCase
from django.urls import reverse
from aplicator.models import TeamMember, CompanyContextBlock


class ContextViewTest(TestCase):
    def test_get_renders_page(self):
        response = self.client.get(reverse("aplicator:context"))
        self.assertEqual(response.status_code, 200)

    def test_post_adds_team_member(self):
        response = self.client.post(
            reverse("aplicator:context"),
            {
                "add_member": "1",
                "name": "Ada Lovelace",
                "role": "CTO",
                "bio": "",
                "track_record": "",
                "notable_projects": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TeamMember.objects.count(), 1)

    def test_post_adds_context_block(self):
        response = self.client.post(
            reverse("aplicator:context"),
            {"add_block": "1", "label": "traction", "text": "10 pilots."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CompanyContextBlock.objects.count(), 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test aplicator.tests.test_context_views`
Expected: FAIL with `NoReverseMatch` (no `aplicator` URL namespace yet).

- [ ] **Step 3: Write forms, views, urls, templates**

Create `aplicator/forms.py`:

```python
from django import forms

from aplicator.models import TeamMember, CompanyContextBlock


class TeamMemberForm(forms.ModelForm):
    class Meta:
        model = TeamMember
        fields = ["name", "role", "bio", "track_record", "notable_projects"]


class CompanyContextBlockForm(forms.ModelForm):
    class Meta:
        model = CompanyContextBlock
        fields = ["label", "text"]
```

Create `aplicator/views.py`:

```python
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
```

Create `aplicator/urls.py`:

```python
from django.urls import path

from aplicator import views

app_name = "aplicator"

urlpatterns = [
    path("", views.context_view, name="context"),
]
```

Modify `accel/urls.py`:

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("aplicator.urls")),
]
```

Create `aplicator/templates/aplicator/base.html`:

```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>accel</title>
</head>
<body>
  <nav>
    <a href="{% url 'aplicator:context' %}">Contexto</a>
  </nav>
  {% block content %}{% endblock %}
</body>
</html>
```

Create `aplicator/templates/aplicator/context.html`:

```html
{% extends "aplicator/base.html" %}
{% block content %}
<h1>Contexto de empresa</h1>

<h2>Equipo</h2>
<ul>
  {% for member in members %}
  <li>{{ member.name }} — {{ member.role }}</li>
  {% endfor %}
</ul>
<form method="post">
  {% csrf_token %}
  {{ member_form.as_p }}
  <button type="submit" name="add_member" value="1">Agregar miembro</button>
</form>

<h2>Bloques de contexto</h2>
<ul>
  {% for block in blocks %}
  <li><strong>{{ block.label }}</strong>: {{ block.text|truncatewords:20 }}</li>
  {% endfor %}
</ul>
<form method="post">
  {% csrf_token %}
  {{ block_form.as_p }}
  <button type="submit" name="add_block" value="1">Agregar bloque</button>
</form>
{% endblock %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test aplicator.tests.test_context_views`
Expected: `OK` (3 tests pass).

- [ ] **Step 5: Commit**

```bash
git add aplicator accel
git commit -m "Add company context UI (team members and context blocks)"
```

---

### Task 9: Add accelerator + extraction + review UI

**Files:**
- Modify: `accel/settings.py`
- Modify: `aplicator/urls.py`
- Modify: `aplicator/views.py`
- Modify: `aplicator/templates/aplicator/base.html`
- Create: `aplicator/llm/factory.py`
- Create: `aplicator/templates/aplicator/accelerator_add.html`
- Create: `aplicator/templates/aplicator/accelerator_review.html`
- Test: `aplicator/tests/test_accelerator_views.py`

**Interfaces:**
- Consumes: `OpenAIAdapter`, `LLMPort` (Task 7); `Accelerator`, `Question` (Task 2).
- Produces: `get_llm_port() -> LLMPort` (reads `LLM_PROVIDER`/`OPENAI_API_KEY`/`DEEPSEEK_API_KEY` from Django settings); URL names `aplicator:accelerator_add` (GET: paste form + list of existing accelerators; POST: extracts via LLM, creates `Accelerator`+`Question`s, redirects to review) and `aplicator:accelerator_review` (GET/POST: edits the extracted `Question`s for one accelerator via a `modelformset_factory`). Later tasks link to `aplicator:accelerator_review` from the accelerator list.

- [ ] **Step 1: Write the failing tests**

Create `aplicator/tests/test_accelerator_views.py`:

```python
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.urls import reverse
from aplicator.models import Accelerator, Question


FAKE_EXTRACTION = {
    "accelerator_name": "founders.inc",
    "url": "https://founders.inc/apply",
    "deadline": "2026-09-01",
    "questions": [
        {
            "type": "text",
            "original_text": "What problem do you solve?",
            "is_required": True,
            "category": "problem",
            "max_chars": 500,
        },
        {
            "type": "video",
            "original_text": "Record a pitch",
            "is_required": True,
            "focus": "pitch",
            "min_seconds": 60,
            "max_seconds": 120,
            "orientation": "any",
            "language": "any",
            "who": "any",
        },
    ],
}


class AcceleratorAddViewTest(TestCase):
    @patch("aplicator.views.get_llm_port")
    def test_post_extracts_and_creates_accelerator_and_questions(self, mock_get_llm_port):
        fake_llm = MagicMock()
        fake_llm.extract_form.return_value = FAKE_EXTRACTION
        mock_get_llm_port.return_value = fake_llm

        response = self.client.post(
            reverse("aplicator:accelerator_add"), {"raw_text": "pasted text..."}
        )

        accelerator = Accelerator.objects.get(accelerator_name="founders.inc")
        self.assertRedirects(
            response,
            reverse("aplicator:accelerator_review", args=[accelerator.id]),
        )
        self.assertEqual(Question.objects.filter(accelerator=accelerator).count(), 2)


class AcceleratorReviewViewTest(TestCase):
    def setUp(self):
        self.accelerator = Accelerator.objects.create(accelerator_name="Endeavor")
        self.question = Question.objects.create(
            accelerator=self.accelerator,
            type="text",
            original_text="What problem?",
            category="problem",
            max_chars=500,
        )

    def test_get_renders_formset(self):
        response = self.client.get(
            reverse("aplicator:accelerator_review", args=[self.accelerator.id])
        )
        self.assertEqual(response.status_code, 200)

    def test_post_saves_edits(self):
        management_data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-id": str(self.question.id),
            "form-0-type": "text",
            "form-0-original_text": "What problem?",
            "form-0-category": "solution",
            "form-0-max_chars": "500",
            "form-0-options": "[]",
        }
        response = self.client.post(
            reverse("aplicator:accelerator_review", args=[self.accelerator.id]),
            management_data,
        )
        self.assertEqual(response.status_code, 302)
        self.question.refresh_from_db()
        self.assertEqual(self.question.category, "solution")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test aplicator.tests.test_accelerator_views`
Expected: FAIL with `NoReverseMatch` (no `aplicator:accelerator_add` URL yet).

- [ ] **Step 3: Add settings, factory, views, urls, templates**

Append to `accel/settings.py`:

```python
import os

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
```

Create `aplicator/llm/factory.py`:

```python
from django.conf import settings

from aplicator.llm.openai_adapter import OpenAIAdapter


def get_llm_port():
    if settings.LLM_PROVIDER == "deepseek":
        return OpenAIAdapter(
            api_key=settings.DEEPSEEK_API_KEY,
            model=settings.DEEPSEEK_MODEL,
            base_url="https://api.deepseek.com",
        )
    return OpenAIAdapter(api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_MODEL)
```

Append to `aplicator/views.py`:

```python
from django.forms import modelformset_factory
from django.shortcuts import get_object_or_404

from aplicator.models import Accelerator, Question
from aplicator.llm.factory import get_llm_port

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
```

Append to `aplicator/urls.py` `urlpatterns`:

```python
    path("accelerators/add/", views.accelerator_add_view, name="accelerator_add"),
    path(
        "accelerators/<int:accelerator_id>/review/",
        views.accelerator_review_view,
        name="accelerator_review",
    ),
```

Modify `aplicator/templates/aplicator/base.html` nav to add:

```html
    <a href="{% url 'aplicator:accelerator_add' %}">Aceleradoras</a>
```

Create `aplicator/templates/aplicator/accelerator_add.html`:

```html
{% extends "aplicator/base.html" %}
{% block content %}
<h1>Agregar aceleradora</h1>
<form method="post">
  {% csrf_token %}
  <textarea name="raw_text" rows="20" cols="80" placeholder="Pegá el texto del formulario"></textarea>
  <button type="submit">Extraer</button>
</form>

<h2>Aceleradoras cargadas</h2>
<ul>
  {% for accelerator in accelerators %}
  <li>
    {{ accelerator.accelerator_name }}
    (<a href="{% url 'aplicator:accelerator_review' accelerator.id %}">revisar</a>)
  </li>
  {% endfor %}
</ul>
{% endblock %}
```

Create `aplicator/templates/aplicator/accelerator_review.html`:

```html
{% extends "aplicator/base.html" %}
{% block content %}
<h1>Revisar {{ accelerator.accelerator_name }}</h1>
<form method="post">
  {% csrf_token %}
  {{ formset.management_form }}
  {% for form in formset %}
    <fieldset>{{ form.as_p }}</fieldset>
  {% endfor %}
  <button type="submit">Guardar</button>
</form>
{% endblock %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test aplicator.tests.test_accelerator_views`
Expected: `OK` (3 tests pass).

- [ ] **Step 5: Commit**

```bash
git add aplicator accel
git commit -m "Add accelerator paste/extract/review UI"
```

---

### Task 10: Plan page (computed live, no persistence)

**Files:**
- Modify: `aplicator/views.py`
- Modify: `aplicator/urls.py`
- Modify: `aplicator/templates/aplicator/base.html`
- Create: `aplicator/templates/aplicator/plan.html`
- Test: `aplicator/tests/test_plan_view.py`

**Interfaces:**
- Consumes: `group_text_questions`, `group_video_questions`, `rank_accelerators` (Tasks 4-6).
- Produces: URL name `aplicator:plan` (GET only, computes and renders — no DB writes).

- [ ] **Step 1: Write the failing test**

Create `aplicator/tests/test_plan_view.py`:

```python
from django.test import TestCase
from django.urls import reverse
from aplicator.models import Accelerator, Question, QuestionArchetype


class PlanViewTest(TestCase):
    def test_shows_grouped_categories_and_ranked_accelerators(self):
        a1 = Accelerator.objects.create(accelerator_name="founders.inc")
        a2 = Accelerator.objects.create(accelerator_name="Endeavor")
        Question.objects.create(
            accelerator=a1,
            type="text",
            original_text="What problem?",
            category=QuestionArchetype.PROBLEM,
            max_chars=500,
        )
        Question.objects.create(
            accelerator=a2,
            type="text",
            original_text="Describe the problem",
            category=QuestionArchetype.PROBLEM,
            max_chars=250,
        )

        response = self.client.get(reverse("aplicator:plan"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "problem")
        self.assertContains(response, "founders.inc")
        self.assertContains(response, "Endeavor")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test aplicator.tests.test_plan_view`
Expected: FAIL with `NoReverseMatch` (no `aplicator:plan` URL yet).

- [ ] **Step 3: Write the view, url, template**

Append to `aplicator/views.py`:

```python
from aplicator.planner import group_text_questions, group_video_questions, rank_accelerators


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
```

Append to `aplicator/urls.py` `urlpatterns`:

```python
    path("plan/", views.plan_view, name="plan"),
```

Modify `aplicator/templates/aplicator/base.html` nav to add:

```html
    <a href="{% url 'aplicator:plan' %}">Plan</a>
```

Create `aplicator/templates/aplicator/plan.html`:

```html
{% extends "aplicator/base.html" %}
{% block content %}
<h1>Plan</h1>

<h2>Qué respondo una sola vez</h2>
<table>
  <tr><th>Categoría</th><th>Aplicaciones</th><th>Límite (min–max chars)</th></tr>
  {% for group in text_groups %}
  <tr>
    <td>{{ group.category }}</td>
    <td>{{ group.accelerator_names|join:", " }}</td>
    <td>{{ group.min_max_chars }}–{{ group.max_max_chars }}</td>
  </tr>
  {% endfor %}
</table>

<h2>Qué produzco una sola vez (video)</h2>
<table>
  <tr><th>Focus</th><th>Orientación</th><th>Idioma</th><th>Quién</th><th>Grabar (seg)</th><th>Master</th><th>Cortes derivados</th></tr>
  {% for rec in recordings %}
  <tr>
    <td>{{ rec.focus }}</td>
    <td>{{ rec.orientation }}</td>
    <td>{{ rec.language }}</td>
    <td>{{ rec.who }}</td>
    <td>{{ rec.record_seconds }}</td>
    <td>{{ rec.master_question.accelerator.accelerator_name }}</td>
    <td>
      {% for cut in rec.derived_cut_questions %}
        {{ cut.accelerator.accelerator_name }}{% if not forloop.last %}, {% endif %}
      {% endfor %}
    </td>
  </tr>
  {% endfor %}
</table>

<h2>Costo marginal (menor a mayor esfuerzo exclusivo)</h2>
<ol>
  {% for accelerator in ranked_accelerators %}
  <li>{{ accelerator.accelerator_name }} — deadline: {{ accelerator.deadline|default:"sin fecha" }}</li>
  {% endfor %}
</ol>
{% endblock %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test aplicator.tests.test_plan_view`
Expected: `OK` (1 test passes).

- [ ] **Step 5: Commit**

```bash
git add aplicator
git commit -m "Add plan page: live-computed text/video grouping and marginal cost ranking"
```

---

### Task 11: Answer bank page

**Files:**
- Create: `aplicator/company_context.py`
- Modify: `aplicator/views.py`
- Modify: `aplicator/urls.py`
- Modify: `aplicator/templates/aplicator/base.html`
- Create: `aplicator/templates/aplicator/answer_bank.html`
- Test: `aplicator/tests/test_answer_bank_view.py`

**Interfaces:**
- Consumes: `group_text_questions` (Task 4), `CanonicalAnswer` (Task 3), `get_llm_port` (Task 9).
- Produces: `build_company_context_text() -> str` (used again by Task 12); URL name `aplicator:answer_bank` (GET: one row per in-use category with its current canonical text if any; POST with `save` stores the submitted text as-is, POST with `generate` calls the LLM grounded in the company context first, then stores the result — both editable afterwards).

- [ ] **Step 1: Write the failing test**

Create `aplicator/tests/test_answer_bank_view.py`:

```python
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.urls import reverse
from aplicator.models import Accelerator, Question, QuestionArchetype, CanonicalAnswer


class AnswerBankViewTest(TestCase):
    def setUp(self):
        acc = Accelerator.objects.create(accelerator_name="founders.inc")
        Question.objects.create(
            accelerator=acc,
            type="text",
            original_text="What problem?",
            category=QuestionArchetype.PROBLEM,
            max_chars=500,
        )

    def test_get_shows_category_in_use(self):
        response = self.client.get(reverse("aplicator:answer_bank"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "problem")

    def test_save_stores_submitted_text_without_calling_llm(self):
        response = self.client.post(
            reverse("aplicator:answer_bank"),
            {"category": "problem", "text": "My canonical answer.", "save": "1"},
        )
        self.assertEqual(response.status_code, 302)
        answer = CanonicalAnswer.objects.get(category="problem")
        self.assertEqual(answer.text, "My canonical answer.")

    @patch("aplicator.views.get_llm_port")
    def test_generate_calls_llm_and_stores_result(self, mock_get_llm_port):
        fake_llm = MagicMock()
        fake_llm.generate_text.return_value = "Generated canonical answer."
        mock_get_llm_port.return_value = fake_llm

        response = self.client.post(
            reverse("aplicator:answer_bank"),
            {"category": "problem", "text": "", "generate": "1"},
        )

        self.assertEqual(response.status_code, 302)
        fake_llm.generate_text.assert_called_once()
        answer = CanonicalAnswer.objects.get(category="problem")
        self.assertEqual(answer.text, "Generated canonical answer.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test aplicator.tests.test_answer_bank_view`
Expected: FAIL with `NoReverseMatch` (no `aplicator:answer_bank` URL yet).

- [ ] **Step 3: Write the helper, view, url, template**

Create `aplicator/company_context.py`:

```python
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
```

Append to `aplicator/views.py`:

```python
from aplicator.models import CanonicalAnswer
from aplicator.company_context import build_company_context_text


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
        {"category": group.category, "canonical": canonical_by_category.get(group.category)}
        for group in group_text_questions(questions)
    ]
    return render(request, "aplicator/answer_bank.html", {"rows": rows})
```

Append to `aplicator/urls.py` `urlpatterns`:

```python
    path("answer-bank/", views.answer_bank_view, name="answer_bank"),
```

Modify `aplicator/templates/aplicator/base.html` nav to add:

```html
    <a href="{% url 'aplicator:answer_bank' %}">Answer bank</a>
```

Create `aplicator/templates/aplicator/answer_bank.html`:

```html
{% extends "aplicator/base.html" %}
{% block content %}
<h1>Answer bank</h1>
{% for row in rows %}
<fieldset>
  <legend>{{ row.category }}</legend>
  <form method="post">
    {% csrf_token %}
    <input type="hidden" name="category" value="{{ row.category }}">
    <textarea name="text" rows="6" cols="80">{{ row.canonical.text|default:"" }}</textarea>
    <br>
    <button type="submit" name="save" value="1">Guardar</button>
    <button type="submit" name="generate" value="1">Generar</button>
  </form>
</fieldset>
{% endfor %}
{% endblock %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test aplicator.tests.test_answer_bank_view`
Expected: `OK` (3 tests pass).

- [ ] **Step 5: Commit**

```bash
git add aplicator
git commit -m "Add answer bank page: view, edit, and LLM-generate canonical answers"
```

---

### Task 12: Per-application answers page (char limit enforced in code)

**Files:**
- Modify: `aplicator/views.py`
- Modify: `aplicator/urls.py`
- Modify: `aplicator/templates/aplicator/accelerator_add.html`
- Create: `aplicator/templates/aplicator/application_answers.html`
- Test: `aplicator/tests/test_application_answers_view.py`

**Interfaces:**
- Consumes: `GeneratedAnswer`, `CanonicalAnswer`, `NON_SHAREABLE` (Tasks 2-3), `get_llm_port` (Task 9), `build_company_context_text` (Task 11).
- Produces: URL name `aplicator:application_answers` (GET: one row per text/multiple_choice `Question` for the accelerator, with its current `GeneratedAnswer` if any; POST `save` stores submitted text as-is; POST `generate` calls the LLM — grounded in the category's `CanonicalAnswer` when one exists and the category is shareable, otherwise grounded directly in the company context for `NON_SHAREABLE` categories — then **truncates to `question.max_chars` in code** before storing, regardless of what the LLM returned).

- [ ] **Step 1: Write the failing tests**

Create `aplicator/tests/test_application_answers_view.py`:

```python
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.urls import reverse
from aplicator.models import (
    Accelerator,
    Question,
    QuestionArchetype,
    CanonicalAnswer,
    GeneratedAnswer,
)


class ApplicationAnswersViewTest(TestCase):
    def setUp(self):
        self.accelerator = Accelerator.objects.create(accelerator_name="founders.inc")
        self.question = Question.objects.create(
            accelerator=self.accelerator,
            type="text",
            original_text="What problem do you solve?",
            category=QuestionArchetype.PROBLEM,
            max_chars=20,
        )

    def test_get_renders_question(self):
        response = self.client.get(
            reverse("aplicator:application_answers", args=[self.accelerator.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "What problem do you solve?")

    def test_save_stores_submitted_text_without_calling_llm(self):
        response = self.client.post(
            reverse("aplicator:application_answers", args=[self.accelerator.id]),
            {"question_id": self.question.id, "text": "Manually written.", "save": "1"},
        )
        self.assertEqual(response.status_code, 302)
        answer = GeneratedAnswer.objects.get(question=self.question)
        self.assertEqual(answer.text, "Manually written.")

    @patch("aplicator.views.get_llm_port")
    def test_generate_uses_canonical_answer_as_context(self, mock_get_llm_port):
        CanonicalAnswer.objects.create(
            category=QuestionArchetype.PROBLEM, text="Long canonical problem answer."
        )
        fake_llm = MagicMock()
        fake_llm.generate_text.return_value = "Short adapted answer."
        mock_get_llm_port.return_value = fake_llm

        self.client.post(
            reverse("aplicator:application_answers", args=[self.accelerator.id]),
            {"question_id": self.question.id, "text": "", "generate": "1"},
        )

        _, kwargs = fake_llm.generate_text.call_args
        self.assertEqual(kwargs["context"], "Long canonical problem answer.")

    @patch("aplicator.views.get_llm_port")
    def test_generated_text_is_truncated_to_max_chars(self, mock_get_llm_port):
        CanonicalAnswer.objects.create(category=QuestionArchetype.PROBLEM, text="Canonical.")
        fake_llm = MagicMock()
        fake_llm.generate_text.return_value = "This generated answer is way longer than twenty chars."
        mock_get_llm_port.return_value = fake_llm

        self.client.post(
            reverse("aplicator:application_answers", args=[self.accelerator.id]),
            {"question_id": self.question.id, "text": "", "generate": "1"},
        )

        answer = GeneratedAnswer.objects.get(question=self.question)
        self.assertEqual(len(answer.text), 20)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test aplicator.tests.test_application_answers_view`
Expected: FAIL with `NoReverseMatch` (no `aplicator:application_answers` URL yet).

- [ ] **Step 3: Write the view, url, template**

Append to `aplicator/views.py`:

```python
from aplicator.models import GeneratedAnswer, NON_SHAREABLE


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
            text = llm.generate_text(
                prompt=(
                    f"Adaptá esta respuesta al wording exacto y al límite de esta "
                    f"pregunta puntual.\nPregunta original: {question.original_text}\n"
                    f"Límite de caracteres: {question.max_chars}"
                ),
                context=context_text,
            )
            if question.max_chars is not None:
                text = text[: question.max_chars]
        GeneratedAnswer.objects.update_or_create(question=question, defaults={"text": text})
        return redirect("aplicator:application_answers", accelerator_id=accelerator.id)

    questions = Question.objects.filter(
        accelerator=accelerator, type__in=["text", "multiple_choice"]
    )
    rows = [
        {"question": q, "answer": GeneratedAnswer.objects.filter(question=q).first()}
        for q in questions
    ]
    return render(
        request,
        "aplicator/application_answers.html",
        {"accelerator": accelerator, "rows": rows},
    )
```

Append to `aplicator/urls.py` `urlpatterns`:

```python
    path(
        "accelerators/<int:accelerator_id>/answers/",
        views.application_answers_view,
        name="application_answers",
    ),
```

Modify `aplicator/templates/aplicator/accelerator_add.html` — add a second link in the loaded-accelerators list:

```html
    (<a href="{% url 'aplicator:accelerator_review' accelerator.id %}">revisar</a> |
     <a href="{% url 'aplicator:application_answers' accelerator.id %}">respuestas</a>)
```

(This replaces the single `revisar` link line from Task 9.)

Create `aplicator/templates/aplicator/application_answers.html`:

```html
{% extends "aplicator/base.html" %}
{% block content %}
<h1>Respuestas — {{ accelerator.accelerator_name }}</h1>
{% for row in rows %}
<fieldset>
  <legend>{{ row.question.original_text }} (máx {{ row.question.max_chars }} caracteres)</legend>
  <form method="post">
    {% csrf_token %}
    <input type="hidden" name="question_id" value="{{ row.question.id }}">
    <textarea name="text" rows="6" cols="80">{{ row.answer.text|default:"" }}</textarea>
    <br>
    <button type="submit" name="save" value="1">Guardar</button>
    <button type="submit" name="generate" value="1">Generar</button>
  </form>
</fieldset>
{% endfor %}
{% endblock %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test aplicator.tests.test_application_answers_view`
Expected: `OK` (4 tests pass).

- [ ] **Step 5: Commit**

```bash
git add aplicator
git commit -m "Add per-application answers page with code-enforced char limit"
```

---

## Final Verification

- [ ] **Run the full test suite**

```bash
python manage.py test
```

Expected: `OK`, all tests across `aplicator/tests/` pass.

- [ ] **Manual smoke test**

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` and walk the flow: add a team member and a context block → paste a fake accelerator form and extract (needs a real `OPENAI_API_KEY` or `DEEPSEEK_API_KEY`+`LLM_PROVIDER=deepseek` in the environment) → review the extracted questions → check `/plan/` → generate a canonical answer in `/answer-bank/` → generate a per-application answer and confirm it's truncated to the question's `max_chars`.

