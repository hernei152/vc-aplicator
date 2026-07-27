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
