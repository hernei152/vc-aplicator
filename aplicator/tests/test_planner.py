import datetime
from django.test import TestCase
from aplicator.models import Accelerator, Question, QuestionArchetype
from aplicator.planner import group_text_questions, group_video_questions, rank_accelerators


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

    def test_unbounded_master_covers_bounded_minimums(self):
        """Regression test: unbounded master must record long enough for all group members' minimums.

        When a video with unbounded max_seconds is chosen as master, the recording duration
        must be at least as long as the highest min_seconds of any other video in the group,
        to preserve the "trim down, never extend" invariant.
        """
        bounded = self._video(min_seconds=90, max_seconds=180)
        unbounded = self._video(min_seconds=5, max_seconds=None)
        recordings = group_video_questions(Question.objects.all())
        self.assertEqual(len(recordings), 1)
        rec = recordings[0]
        # The recording must be long enough to cover the bounded video's minimum.
        # Without the fix, this would fail because record_seconds would be 5 (unbounded.min_seconds).
        self.assertGreaterEqual(rec.record_seconds, 90)


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
