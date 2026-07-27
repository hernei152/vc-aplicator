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
            "type": "multiple_choice",
            "original_text": "What stage is your company at?",
            "is_required": True,
            "archetype": "traction",
            "options": ["Idea", "MVP", "Revenue"],
            "allow_multiple": False,
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
        self.assertEqual(Question.objects.filter(accelerator=accelerator).count(), 3)
        # Verify that multiple_choice question has archetype correctly mapped to category
        mc_question = Question.objects.get(type="multiple_choice", accelerator=accelerator)
        self.assertEqual(mc_question.category, "traction")

    @patch("aplicator.views.get_llm_port")
    def test_post_with_duplicate_accelerator_name_does_not_crash(self, mock_get_llm_port):
        existing = Accelerator.objects.create(accelerator_name="founders.inc")

        duplicate_name_extraction = {
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
            ],
        }
        fake_llm = MagicMock()
        fake_llm.extract_form.return_value = duplicate_name_extraction
        mock_get_llm_port.return_value = fake_llm

        response = self.client.post(
            reverse("aplicator:accelerator_add"), {"raw_text": "pasted text..."}
        )

        self.assertEqual(response.status_code, 302)
        # No new Accelerator was created for the colliding name; the existing
        # one is reused instead of raising IntegrityError.
        self.assertEqual(
            Accelerator.objects.filter(accelerator_name="founders.inc").count(), 1
        )
        self.assertRedirects(
            response,
            reverse("aplicator:accelerator_review", args=[existing.id]),
        )

    @patch("aplicator.views.get_llm_port")
    def test_post_with_malformed_deadline_does_not_crash(self, mock_get_llm_port):
        malformed_deadline_extraction = {
            "accelerator_name": "Malformed Deadline Accelerator",
            "url": "https://example.com/apply",
            "deadline": "sometime next month",
            "questions": [],
        }
        fake_llm = MagicMock()
        fake_llm.extract_form.return_value = malformed_deadline_extraction
        mock_get_llm_port.return_value = fake_llm

        response = self.client.post(
            reverse("aplicator:accelerator_add"), {"raw_text": "pasted text..."}
        )

        self.assertEqual(response.status_code, 302)
        accelerator = Accelerator.objects.get(
            accelerator_name="Malformed Deadline Accelerator"
        )
        self.assertIsNone(accelerator.deadline)


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
        self.mc_question = Question.objects.create(
            accelerator=self.accelerator,
            type="multiple_choice",
            original_text="What stage?",
            category="traction",
            options=["Idea", "MVP", "Revenue"],
        )

    def test_get_renders_formset(self):
        response = self.client.get(
            reverse("aplicator:accelerator_review", args=[self.accelerator.id])
        )
        self.assertEqual(response.status_code, 200)

    def test_post_saves_edits(self):
        management_data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-id": str(self.question.id),
            "form-0-type": "text",
            "form-0-original_text": "What problem?",
            "form-0-is_required": "on",
            "form-0-category": "solution",
            "form-0-max_chars": "500",
            "form-0-options": "[]",
            "form-0-allow_multiple": "",
            "form-0-focus": "",
            "form-0-min_seconds": "",
            "form-0-max_seconds": "",
            "form-0-orientation": "any",
            "form-0-language": "any",
            "form-0-who": "any",
            "form-1-id": str(self.mc_question.id),
            "form-1-type": "multiple_choice",
            "form-1-original_text": "What stage?",
            "form-1-is_required": "on",
            "form-1-category": "traction",
            "form-1-max_chars": "",
            "form-1-options": '["Idea", "MVP", "Revenue"]',
            "form-1-allow_multiple": "",
            "form-1-focus": "",
            "form-1-min_seconds": "",
            "form-1-max_seconds": "",
            "form-1-orientation": "any",
            "form-1-language": "any",
            "form-1-who": "any",
        }
        response = self.client.post(
            reverse("aplicator:accelerator_review", args=[self.accelerator.id]),
            management_data,
        )
        self.assertEqual(response.status_code, 302)
        self.question.refresh_from_db()
        self.assertEqual(self.question.category, "solution")
        self.mc_question.refresh_from_db()
        self.assertEqual(self.mc_question.category, "traction")


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
