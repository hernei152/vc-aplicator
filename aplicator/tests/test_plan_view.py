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
        self.assertContains(response, "Problem")
        self.assertContains(response, "founders.inc")
        self.assertContains(response, "Endeavor")


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
