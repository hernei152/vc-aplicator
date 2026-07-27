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

    def test_accelerator_name_unique_constraint(self):
        Accelerator.objects.create(accelerator_name="Techstars")
        self.assertEqual(Accelerator.objects.count(), 1)
        with self.assertRaises(Exception):
            Accelerator.objects.create(accelerator_name="Techstars")


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
