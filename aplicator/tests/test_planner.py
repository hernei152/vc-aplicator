from django.test import TestCase
from aplicator.models import Accelerator, Question, QuestionArchetype
from aplicator.planner import group_text_questions, group_video_questions


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
