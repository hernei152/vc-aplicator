import json
from unittest import TestCase
from unittest.mock import MagicMock
from aplicator.llm.openai_adapter import OpenAIAdapter, EXTRACTION_SYSTEM_PROMPT, GENERATION_SYSTEM_PROMPT


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

        # Verify parsed response
        self.assertEqual(result["accelerator_name"], "founders.inc")
        self.assertEqual(len(result["questions"]), 1)

        # Verify request construction
        client.chat.completions.create.assert_called_once()
        call_kwargs = client.chat.completions.create.call_args.kwargs

        # Verify model
        self.assertEqual(call_kwargs["model"], "gpt-4o-mini")

        # Verify messages structure
        messages = call_kwargs["messages"]
        self.assertIsInstance(messages, list)
        self.assertEqual(len(messages), 2)

        # System message should contain extraction prompt
        system_msg = messages[0]
        self.assertEqual(system_msg["role"], "system")
        self.assertEqual(system_msg["content"], EXTRACTION_SYSTEM_PROMPT)

        # User message should be the raw text
        user_msg = messages[1]
        self.assertEqual(user_msg["role"], "user")
        self.assertEqual(user_msg["content"], "pasted form text")

        # Verify response_format
        self.assertEqual(call_kwargs["response_format"], {"type": "json_object"})

    def test_generate_text_returns_message_content(self):
        client = _fake_chat_client("Generated answer text.")
        adapter = OpenAIAdapter(api_key="fake", client=client)

        result = adapter.generate_text(prompt="Write the problem answer", context="We solve X.")

        # Verify returned content
        self.assertEqual(result, "Generated answer text.")

        # Verify request construction
        client.chat.completions.create.assert_called_once()
        call_kwargs = client.chat.completions.create.call_args.kwargs

        # Verify model
        self.assertEqual(call_kwargs["model"], "gpt-4o-mini")

        # Verify messages structure
        messages = call_kwargs["messages"]
        self.assertIsInstance(messages, list)
        self.assertEqual(len(messages), 2)

        # System message should contain generation prompt
        system_msg = messages[0]
        self.assertEqual(system_msg["role"], "system")
        self.assertEqual(system_msg["content"], GENERATION_SYSTEM_PROMPT)

        # User message should combine context and prompt
        user_msg = messages[1]
        self.assertEqual(user_msg["role"], "user")
        expected_content = "Contexto de la empresa:\nWe solve X.\n\nTarea:\nWrite the problem answer"
        self.assertEqual(user_msg["content"], expected_content)
