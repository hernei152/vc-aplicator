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
        GeneratedAnswer.objects.create(question=question, text="short answers")
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
