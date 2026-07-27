# accel — mejoras de UI/UX (v0.1)

Fecha: 2026-07-27
Fuente: brainstorming en conversación, tras merge de [2026-07-27-accel-django-app-design.md](2026-07-27-accel-django-app-design.md).

## 1. Qué es

Segunda vuelta sobre la webapp Django ya mergeada: arregla problemas de usabilidad
encontrados en las 7 pantallas existentes (campos irrelevantes por tipo de pregunta,
enums crudos, falta de contexto de aplicabilidad, borrado sin confirmación, sin
feedback de límite de caracteres) y suma un framework CSS classless vendorizado para
subir el nivel visual sin JS ni build step.

**Disparador concreto:** la pantalla de revisión (`/accelerators/<id>/review/`) usa un
único formset genérico que muestra los 13 campos de `Question` para cada fila sin
importar el tipo — una pregunta de texto muestra `focus`, una de video muestra
`max_chars`. El pedido explícito del usuario: "cada pregunta debe tener lo que le
aplica."

## 2. Alcance

Toda la app (7 pantallas: contexto, agregar aceleradora, revisión, plan, answer bank,
respuestas por aplicación, y las de editar/borrar contexto agregadas después del v0).
Profundidad: usabilidad/claridad + un framework CSS classless. Explícitamente fuera de
alcance: JS de cualquier tipo (contador de caracteres en vivo, confirmación vía
`confirm()`, autocompletado), reestructurar el modelo de datos o el planner, agregar
delete UI para `Accelerator` (gap conocido, no pedido en esta vuelta).

## 3. Fundación visual

- **Pico.css vendorizado**: `aplicator/static/aplicator/pico.min.css`, servido vía
  `django.contrib.staticfiles` (ya en `INSTALLED_APPS`). Un `{% load static %}` +
  `<link>` en `base.html`. Classless — el HTML plano existente no necesita clases
  nuevas para verse bien. Respeta `prefers-color-scheme` (ya usábamos
  `color-scheme: light dark` a mano).
- El `<style>` artesanal de `base.html` se recorta a lo que Pico no cubre: el layout
  inline de los mini-forms de "borrar" dentro de una `<li>`.
- **Labels legibles para enums**: `aplicator/templatetags/aplicator_extras.py` con dos
  filtros, `category_label` y `focus_label`, que mapean el valor crudo (`"why_now"`) a
  su label humano vía `dict(QuestionArchetype.choices)` / `dict(VideoFocus.choices)`.
  Necesario en `plan.html` y `answer_bank.html`, que trabajan con los dataclasses del
  planner (`TextGroup`, `Recording`), no con instancias de modelo — no tienen
  `get_FOO_display()` gratis. Donde sí hay instancia de modelo (`application_answers.html`,
  el formset de revisión), se usa `get_category_display`/`get_focus_display` nativo de
  Django, sin filtro custom.

## 4. Pantalla de revisión (el pedido original)

El view (`accelerator_review_view`) no cambia — sigue siendo un único
`modelformset_factory` sobre `Question`, misma validación, mismo POST. Cambia el
template: en vez de `{{ form.as_p }}` genérico, cada fila renderiza solo los campos
que aplican a `form.instance.type`:

- **`text`**: pregunta original (label de solo lectura), `is_required`, `category`,
  `max_chars`.
- **`multiple_choice`**: pregunta original, `is_required`, `category` (el archetype),
  `options`, `allow_multiple`.
- **`video`**: pregunta original, `is_required`, `focus`, `min_seconds`,
  `max_seconds`, `orientation`, `language`, `who`.

El campo `type` se muestra como texto fijo (no editable) más `{{ form.type.as_hidden }}`
para que el POST siga siendo válido — cambiar el tipo sin cambiar los campos
aplicables no tiene sentido en esta UI. Los campos no renderizados para un tipo dado
ya son `None`/`False` en el modelo para ese tipo (nunca se les asignó otra cosa en
extracción), así que omitirlos del render no arriesga pisar datos reales al guardar —
Django simplemente no ve esos campos en el POST y su valor limpio cae a su default
(`None`/`False`), que es idéntico al valor ya almacenado.

**Mensaje flash post-extracción**: `accelerator_add_view` agrega un mensaje vía
`django.contrib.messages` ("Se extrajeron N preguntas — revisalas antes de
continuar") antes de redirigir a la revisión, para que el operador tenga contexto de
qué acaba de pasar. `base.html` agrega el render de `{% if messages %}` (Pico.css
estiliza `<article>`/mensajes sin clases extra necesarias más allá de las que Django
messages ya permite pasar, ej. usar el `message.tags` como clase).

## 5. Resto de las pantallas

- **Answer bank** (`answer_bank_view`, `answer_bank.html`): cada fila de categoría
  muestra ahora a cuántas/cuáles aceleradoras aplica — dato que `group_text_questions()`
  ya calcula (`TextGroup.accelerator_names`) y hoy se descarta al construir `rows`. Se
  agrega un badge textual "sin borrador" vs "borrador guardado" según si existe
  `CanonicalAnswer` para esa categoría.
- **Respuestas por aplicación** (`application_answers.html`): junto al límite, se
  muestra el conteo actual del texto guardado — "115/500 caracteres" — calculado
  server-side (`answer.text|length` vs `question.max_chars`), sin JS ni contador en
  vivo (se recalcula en cada carga de página, consistente con el resto de la app). Si
  `len(text) == max_chars` (y `max_chars` no es `None`), se agrega una nota "posible
  truncado por límite" — heurística simple y barata, sin falsos positivos costosos de
  evitar.
- **Plan** (`plan.html`): se arregla el "None–None" cuando ningún `Question` del
  grupo tiene `max_chars` (mostrar "sin límite" en su lugar). Se arregla también
  `application_answers_view`'s prompt al LLM, que hoy interpola literalmente
  `"Límite de caracteres: None"` cuando `max_chars` es `None` — se omite esa línea del
  prompt en ese caso.
- **Contexto** (`context.html` + nuevas vistas): el borrado de `TeamMember` y
  `CompanyContextBlock` deja de ser un botón de un solo click dentro de la lista. Pasa
  a un link a una pantalla chica de confirmación (`team_member_delete_confirm.html` /
  `context_block_delete_confirm.html`, o una plantilla genérica compartida como
  `edit_form.html` ya se comparte) — "¿Confirmás borrar a {{ member.name }}?" + botón
  "Sí, borrar" que hace el POST real. Sin JS, dos pasos en vez de uno. La lista de
  miembros del equipo muestra ahora una vista previa corta (`truncatewords`) de
  `bio`/`track_record`, no solo nombre y rol, para que el operador vea si ya cargó
  datos sin tener que entrar a editar cada uno.

## 6. Testing

Cambios de template puro (labels, contadores, badges) no necesitan test nuevo más
allá de los `assertContains` ya existentes en las vistas correspondientes, ampliados
donde haga falta para cubrir el contenido nuevo. Los cambios de comportamiento real
(el borrado de dos pasos, el mensaje flash, el prompt sin "None") sí necesitan test:
la confirmación de borrado no debe borrar en el `GET` de la página de confirmación,
solo en el `POST` de esa página; el flash message debe aparecer en la respuesta
redirigida; el prompt sin `max_chars` no debe contener la palabra `None`.

## 7. Fuera de alcance de esta vuelta

- JS de cualquier tipo (contador en vivo, `confirm()` nativo, etc.).
- Delete UI para `Accelerator` (gap conocido, documentado en memoria, no pedido acá).
- Mejorar el widget de `options` (hoy un textarea de JSON crudo para preguntas
  multiple_choice) — no se pidió, se deja como está.
- Cualquier cambio al modelo de datos, al planner, o al LLM port.
