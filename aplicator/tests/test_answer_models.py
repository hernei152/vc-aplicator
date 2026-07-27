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
