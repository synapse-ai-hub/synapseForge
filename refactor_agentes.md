# Refactor de Agentes — Plan de Tareas

> Documento de seguimiento. No modificar código hasta que el usuario lo indique.
> Cada tarea se implementa por separado, respetando las indicaciones.

---

## Tarea 1 — AGENT.md se inyecta (no reemplaza el system prompt)

**Estado actual:** en `backend/agent/loop_helpers.py` (`build_system_prompt`), si existe
`AGENT.md` en el config dir, se usa **como system prompt del router** (reemplaza).
Si no existe, se usa `system_prompt.md`.

**Comportamiento deseado:**
- `system_prompt.md` es siempre la base del prompt del router.
- Si existe `AGENT.md` → se **concatena al final** bajo un header `## Behavior` (h2, revisar títulos/subtítulos).
- Si no existe → no se inyecta nada (obvio).
- AGENT.md queda para **comportamiento general** (compatibilidad con opencode/claude code).

**Archivos:**
- `backend/agent/loop_helpers.py` (`build_system_prompt`)

---

## Tarea 2 — Bloque `## MANDATORY:` inyectado a TODOS los agentes

**Comportamiento deseado:** al final del prompt de sistema de **todos** los agentes
(router **y** subagentes) se inyecta una sección `## MANDATORY:` que indica:

1. Extraer el **objetivo fiel** del usuario: sin agregar ni inventar nada.
2. Si hay dudas → formularle al usuario las preguntas correspondientes (preguntas útiles, no pelotudeces).
3. Iterar usando **tools y/o subagentes** hasta cumplir el objetivo.
4. No inventar.
5. Si por algún motivo no se puede realizar → informarle al usuario que no se puede y darle
   indicaciones **no técnicas** (lenguaje natural, claras para un usuario no técnico) de cómo proceder
   para que el agente pueda realizar la tarea.

**Referencia:** revisar `D:/synapse-ai-hub/opencode` — el usuario ya puso el tema de **fidelidad** ahí, tomar ese estilo.

**Archivos:**
- `backend/agent/loop_helpers.py` (`build_system_prompt` — punto central que aplica a router y subagentes)

---

## Tarea 3 — init verifica modelos de Ollama + modelo por defecto local = qwen

### 3a. Verificación/instalación de modelos en `init`

**Comportamiento deseado:** al crear el proyecto (`synapseforge init`), se debe:

- Verificar que **ollama esté instalado** (requisito). Si no está → avisar.
- Ejecutar `ollama list` y verificar que el usuario tenga estos modelos (literal):
  - `qwen3.5:4b`
  - `gemma4:e2b`
  - `phi4-mini-reasoning:3.8b`
  - `granite3.1-moe:3b`
  - `nemotron-3-nano:4b`
- Si falta `qwen3.5:4b` → instalarlo con `ollama pull qwen3.5:4b` (**solo ese** se instala).
- Los otros 4 **solo se verifican**: si no están, se avisa (no se instalan).

**Archivos:**
- `synapseforge/tk/init_app.py` (GUI)
- `pipeline/init/main.py` (pasos de creación del proyecto)

### 3b. Modelo por defecto en LOCAL = qwen

**Estado actual:** `_default_model_for_provider` en `backend/routes/config.py` devuelve
`models[0]` (el **primero** de `ollama list`) para LOCAL.

**Comportamiento deseado:**
- Para **LOCAL**, el modelo por defecto pasa a ser **`qwen3.5:4b`** (si está en la lista).
- Razón: acepta tools. Hoy, si el primer modelo de la lista no acepta tools, el usuario
  hace una pregunta y falla. Se inicializa con qwen para evitarlo.
- **El cambio aplica solo a LOCAL**, a cómo se toma el modelo por defecto.
- Si `qwen3.5:4b` no está en la lista → fallback al primer modelo (comportamiento actual).

**Archivos:**
- `backend/routes/config.py` (`_default_model_for_provider`)

---

## Tarea 4 — Explicación de colores orientada al usuario (2 GUIs)

**Estado actual:** labels pelados en `synapseforge/tk/init_app.py` (tab Colores) y
`synapseforge/tk/colors_app.py`:
- "Color principal (botones, headers, burbujas)"
- "Color secundario (hover, detalles light)"
- "Color de texto (botones, headers)"
- "Color secundario del gradiente"

**Comportamiento deseado:** explicación **breve pero explicativa**, orientada al usuario,
que explique **qué configura** cada color y **dónde se aplica** (no una mención boluda, no una lista).

**Uso real verificado en la app:**
- `primary` → acento principal: botones, headers, burbujas del asistente, enlaces, avatar, ring de foco, typing, inicio del gradiente de actividad.
- `secondary` → detalles light: hovers, fin del gradiente, ring de foco del textarea, spinner.
- `primary_text` → color del texto que va sobre fondo primario (ícono enviar, texto de botones).
- `gradient_secondary` → segundo color del gradiente (botón enviar, línea de actividad).
- `usar_gradiente` → toggle: si se desactiva, el gradiente se reemplaza por el color principal sólido.

**Archivos:**
- `synapseforge/tk/init_app.py` (tab Colores)
- `synapseforge/tk/colors_app.py`

---

## Tarea 5 — Permisos del agente principal desde `config.yaml`

**Estado actual:**
- El agente principal (router) **no tiene permisos de tools ni skills, solo `task`** — mantener eso.
- En `loop.py` (`run()`), el router recibe `tool_permissions=None` → todas las tools. Esto hay que cambiarlo.
- `permissions.py` resuelve permisos desde el frontmatter de los agentes `.md`:
  - Entradas planas (`tool: allow`) y anidadas (`task: {nombre_agente: allow}`) se preservan.
  - `task` acepta **diccionario**: solo los subagentes listados explícitamente tienen permiso.

**Comportamiento deseado:**
- Nuevo archivo `~/.config/synapseForge/config.yaml` (opcional).
- Estructura:
  ```yaml
  permissions:
    tool: ...
    skill: ...
    task:
      nombre_agente: allow
  ```
- En `loop.run()`: si el yaml existe → tomar de ahí los permisos del router
  (mismo formato que `permissions.py`, leído igual).
- Si el yaml **no** existe → el router queda como hoy: **sin tools ni skills directas, solo `task`**
  (delegación siempre disponible).
- `task` debe aceptar el diccionario: el router solo puede delegar a los subagentes
  que estén explícitamente en el yaml.

**Archivos:**
- Nuevo: `~/.config/synapseForge/config.yaml` (ejemplo/referencia)
- `backend/agent/loop.py` (`run()` — aplicar permisos del router desde el yaml)
- `backend/agent/permissions.py` (referencia del formato a respetar)

---

## Tarea 6 — Actualizar documentación

**Comportamiento deseado:** actualizar toda la documentación que describa el comportamiento
que cambia con este refactor, para que quede consistente:

- `backend/agent/README.md` — resolución de prompts, permisos, resolución de modelo.
- `backend/routes/README.md` — proveedores y selección de modelo (default local).
- `backend/agent/prompts/help.md` — documentación que ve el usuario en la app:
  cómo se configuran agentes, permisos, skills (agregar `config.yaml` del router,
  el `## MANDATORY:`, AGENT.md como comportamiento general).
- `docs/` — documentación del proyecto.
- `README.md` — si describe el flujo de agentes/modelos, reflejar los cambios.

Cada cambio funcional de las tareas 1-5 debe tener su contraparte en documentación
en la misma iteración.

**Archivos:**
- `backend/agent/README.md`
- `backend/routes/README.md`
- `backend/agent/prompts/help.md`
- `docs/`
- `README.md`

---

## Orden de implementación sugerido

1. Tarea 2 (MANDATORY) — base de comportamiento para todos los agentes. [x]
2. Tarea 1 (AGENT.md inyectado). [x]
3. Tarea 5 (permisos desde config.yaml). [x]
4. Tarea 3 (init verifica modelos + default local = qwen). [x]
5. Tarea 4 (explicación de colores). [x]
6. Tarea 6 (actualizar documentación) — junto con cada cambio, no al final. [x]

> Esperar indicaciones del usuario antes de modificar cualquier cosa.
