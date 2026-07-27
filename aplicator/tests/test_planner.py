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
