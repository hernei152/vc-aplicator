import json

from openai import OpenAI

from aplicator.llm.port import LLMPort

EXTRACTION_SYSTEM_PROMPT = """Sos un extractor de formularios de aceleradoras.
Te paso el texto crudo pegado de un formulario (puede incluir menús, footers,
botones — ignoralos). Devolvé UN JSON con esta forma exacta:

{
  "accelerator_name": str,
  "url": str | null,
  "deadline": "YYYY-MM-DD" | null,
  "questions": [
    {
      "type": "text" | "multiple_choice" | "video",
      "original_text": str,
      "is_required": bool,
      // si type == "text":
      "category": uno de [problem, solution, why_now, why_you, team, traction,
        business_model, market_size, competition, moat, gtm, product_demo,
        tech, milestones, ask, use_of_funds, risks, failure_story,
        why_this_program, legal_admin, other],
      "max_chars": int | null,   // si el form da un límite en palabras, convertilo a caracteres (palabras * 6)
      // si type == "multiple_choice":
      "archetype": uno de [problem, solution, why_now, why_you, team, traction,
        business_model, market_size, competition, moat, gtm, product_demo,
        tech, milestones, ask, use_of_funds, risks, failure_story,
        why_this_program, legal_admin, other],
      "options": [str],
      "allow_multiple": bool,
      // si type == "video":
      "focus": "founder_intro" | "pitch" | "demo",
      "min_seconds": int | null,
      "max_seconds": int | null,
      "orientation": "h" | "v" | "any",   // "any" si el form no lo aclara
      "language": "es" | "en" | "any",     // "any" si el form no lo aclara
      "who": "solo" | "all_founders" | "any"  // "any" si el form no lo aclara
    }
  ]
}

Regla dura: nunca inventes una restricción (orientación, idioma, quién
aparece) que el form no pida explícitamente — usá "any" por defecto."""

GENERATION_SYSTEM_PROMPT = """Sos un asistente que escribe respuestas para
formularios de aceleradoras, en la voz del founder, con tono específico y
sobrio: números, nombres, fechas, cero lenguaje de pitch inflado
("revolucionario", "disruptivo"). Usá EXCLUSIVAMENTE el contexto de empresa
provisto. Si un dato necesario no está en ese contexto, escribí el marcador
visible "[FALTA: <qué dato falta>]" en su lugar — nunca inventes métricas,
nombres de clientes ni fechas."""


class OpenAIAdapter(LLMPort):
    def __init__(self, api_key=None, model="gpt-4o-mini", base_url=None, client=None):
        self.client = client or OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def extract_form(self, raw_text: str) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)

    def generate_text(self, prompt: str, context: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
                {"role": "user", "content": f"Contexto de la empresa:\n{context}\n\nTarea:\n{prompt}"},
            ],
        )
        return response.choices[0].message.content
