from abc import ABC, abstractmethod


class LLMPort(ABC):
    @abstractmethod
    def extract_form(self, raw_text: str) -> dict:
        """Parse pasted accelerator-form text into a dict shaped like
        contracts.AcceleratorForm: accelerator_name, url, deadline, and a
        list of question dicts, each with 'type' plus its type-specific
        fields."""

    @abstractmethod
    def generate_text(self, prompt: str, context: str) -> str:
        """Generate text for `prompt` grounded only in `context`."""
