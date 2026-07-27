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
