# accel — diseño de la app Django (v0)

Fecha: 2026-07-27
Fuente de contexto: brief del proyecto (ver conversación), `contracts.py` (contrato de datos de referencia).

## 1. Qué es

Reemplaza el v0-CLI propuesto originalmente en el brief por una webapp Django local
(sin deploy, SQLite). El objetivo funcional no cambia: dado un conjunto de
formularios de aceleradoras pegados como texto, producir (a) qué producir una sola
vez (videos/decks) y qué responder una sola vez (answer bank por categoría), y (b)
un primer borrador de respuesta por cada aplicación, respetando el límite exacto de
cada una.

## 2. Arquitectura

- Un solo proyecto Django, una app (`aplicator`), SQLite, corre en local
  (`manage.py runserver`), sin autenticación (single-user).
- UI: templates de Django clásicos, full page reload. Sin JS/HTMX.
- LLM: un puerto propio (`LLMPort`) con dos operaciones — `extract_form(raw_text) ->
  AcceleratorForm` y `generate_text(prompt, context) -> str` — con adapters
  intercambiables para OpenAI y DeepSeek (comparten forma de SDK: mismo cliente,
  cambia `base_url` y modelo). Nuevos proveedores se agregan como adapters nuevos,
  sin tocar el resto del sistema.
- `contracts.py` se mantiene como está, como referencia del contrato de datos; los
  modelos Django implementan la misma forma (unión discriminada por `type` para las
  preguntas) pero como tablas relacionales.

## 3. Modelos de datos

**Contexto de empresa** (se carga una vez, se edita cuando cambia):
- `TeamMember`: nombre, rol, bio, track_record, proyectos_destacables
- `CompanyContextBlock`: etiqueta libre, texto (métricas, tracción, modelo de
  negocio, mercado, ask, historia, y lo que haga falta — abierto, no un enum cerrado)

**Formularios** (un `Accelerator` con sus `Question`, espejando `contracts.py`):
- `Accelerator`: nombre, url, deadline, texto_pegado_original
- `Question`: FK a `Accelerator`; `type` (`text`/`multiple_choice`/`video`);
  `original_text`, `is_required`; campos según type (nullable si no aplica):
  `category` (enum `QuestionArchetype`, aplica a text y multiple_choice),
  `max_chars`, `options`, `allow_multiple`, `focus` (enum `VideoFocus`),
  `min_seconds`, `max_seconds`, `orientation`, `language`, `who`.

**Answer bank**:
- `CanonicalAnswer`: `category` (único), texto largo editable a mano. No existe
  para categorías en `NON_SHAREABLE`.

**Respuestas por aplicación**:
- `GeneratedAnswer`: FK a `Question`, texto adaptado al wording/límite exacto de esa
  pregunta, generado por LLM y editable a mano.

## 4. Flujo / páginas

1. **Contexto de empresa** — alta/edición de `TeamMember` y `CompanyContextBlock`.
2. **Agregar aceleradora** — pegás el texto crudo → botón "Extraer" (LLM, vía
   `LLMPort.extract_form`) → crea `Accelerator` + `Question`s → pantalla de revisión
   donde se puede corregir cualquier campo mal clasificado antes de confirmar. Este
   es el punto frágil que señala el brief: la extracción se revisa una vez, antes de
   generar nada.
3. **Plan** — vista calculada al vuelo (sin persistencia propia, sin modelo `Plan`):
   ejecuta la función de planificación (código puro, sin LLM) sobre los `Question`
   actuales en DB y renderiza el resultado. Cada carga de página está siempre al
   día con los datos guardados, sin botón de recálculo.
4. **Answer bank** — una fila por `category` en uso (excluyendo `NON_SHAREABLE`).
   Botón "Generar" (LLM + contexto de empresa) si no existe canonical; siempre
   editable a mano.
5. **Respuestas por aplicación** — por `Accelerator`, lista de `Question` con su
   `GeneratedAnswer`. Botón "Generar/Regenerar": toma la `CanonicalAnswer` de la
   categoría (o, si es `NON_SHAREABLE`, genera directo desde el contexto de
   empresa) y la adapta al wording y límite exactos de esa pregunta puntual. El
   límite de caracteres se valida en código, nunca se confía en que el LLM lo
   respete. Editable a mano.

## 5. Lógica del planner (pura, sin LLM, testeable con asserts)

**Eje texto** — agrupar `Question` de tipo text/multiple_choice por `category`
(excluyendo `NON_SHAREABLE`). Por grupo: aplicaciones que lo comparten, y rango
[min(max_chars), max(max_chars)].

**Eje video** — tres pasos, en este orden:
1. Agrupar por `focus` (nunca se mezclan focos distintos).
2. Dentro de cada `focus`, resolver `orientation`/`language`/`who`: `any` se
   absorbe en cualquier grupo concreto existente; solo valores concretos y
   distintos entre sí fuerzan grupos separados.
3. Dentro de cada grupo de dimensiones, resolver duración por solapamiento de
   ventanas `[min_seconds, max_seconds]`: si `max(mínimos) <= min(máximos)`, una
   sola toma cubre todo el grupo. Si no solapan, se separa en subgrupos: el de
   ventana más larga es la grabación "master", los demás son "corte derivado" de
   esa master (nunca al revés, nunca una grabación nueva).

**Costo marginal** — ordenar `Accelerator` por cantidad de preguntas exclusivas
(categorías `NON_SHAREABLE` + preguntas de video que no calzan en ningún grupo ya
cubierto) de menor a mayor; desempate por `deadline` ascendente.

## 6. Testing

`test_planner.py` con asserts sobre casos concretos: ventanas de duración que
solapan y que no solapan (con el corte derivado marcado correctamente), `any`
absorbido en un grupo concreto sin generar grupo aparte, categorías
`NON_SHAREABLE` excluidas del answer bank grouping. Es la única lógica no trivial
del sistema — el resto es CRUD de Django y llamadas a LLM.

## 7. Fuera de alcance de este v0

- Autenticación / multi-usuario.
- Deploy (Vercel u otro) — corre solo en local.
- HTMX/JS — full page reload alcanza.
- Modelo `Plan` persistido — se recalcula siempre al vuelo.
- Cualquier adapter de LLM más allá de OpenAI y DeepSeek (el puerto los admite, no
  se implementan ahora).
