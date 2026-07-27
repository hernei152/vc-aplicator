from django.conf import settings

from aplicator.llm.openai_adapter import OpenAIAdapter


def get_llm_port():
    if settings.LLM_PROVIDER == "deepseek":
        return OpenAIAdapter(
            api_key=settings.DEEPSEEK_API_KEY,
            model=settings.DEEPSEEK_MODEL,
            base_url="https://api.deepseek.com",
        )
    return OpenAIAdapter(api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_MODEL)
