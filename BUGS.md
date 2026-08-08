# Bugs — synapseForge

> Documento de contexto para no perder el hilo. Cada bug incluye: síntoma, causa raíz (verificada en código/logs) y qué hay que hacer.
>
> **Estado: los 4 bugs están FIXEADOS (2026-08-07).** Ver sección "Cambios aplicados" al final.

---

## Bug 1 — El contenedor de conversaciones (Sidebar) se corta

**Síntoma:** La lista de conversaciones en la pestaña "Conversaciones" se corta y no se puede scrollear hasta el final. Debería comportarse igual que las pestañas de skills/tools (scroll completo).

**Causa raíz:** En `frontend/src/components/sessionsTab.tsx` (línea 61), el contenedor de historial tiene un `style={{ maxHeight: "70%" }}` que limita la lista al 70% del alto y corta el resto. Las otras pestañas (config/agent/create) usan `overflow-y-auto` sin ese límite.

**Qué hacer:**
- Quitar el `maxHeight: "70%"` del contenedor de historial en `sessionsTab.tsx` para que scrollee completo (dejar `flex-1 overflow-y-auto min-h-0`).

---

## Bug 2 — Una task que terminó sin respuesta queda con spinner (no se marca como error)

**Síntoma:** Cuando un sub-agente termina sin dar una respuesta final al padre (o falla internamente), la burbuja de `task` queda "activa, con spinner" en vez de marcarse como error. Luego el padre vuelve a llamar a `task`, pero la primera burbuja sigue con spinner.

**Causa raíz (2 partes):**

1. **Lógica de status en el frontend** (`frontend/src/components/chatBlocks.tsx`, línea 250):
   ```js
   const status = waitingForChunk
     ? "calling"
     : hasResult
       ? (isError ? "error" : "success")
       : ...
   ```
   `waitingForChunk` se evalúa **primero**. Como `waitingForChunk = message.isStreaming && !hasTextBlock`, mientras el padre sigue trabajando (isStreaming=true) y aún no produjo un bloque de texto, **todas** las burbujas de task muestran "calling" (spinner), incluso las que ya tienen `result`.

2. **Detección de error** (`chatBlocks.tsx`, línea 207): `isError` solo detecta `state="error"` en el XML del resultado. Pero el backend devuelve `state="completed"` cuando el sub-agente falla internamente (el loop del sub-agente captura su propio error y no propaga excepción a `task()`), así que el XML queda `state="completed"` con un `task_result` vacío o con texto de error → el frontend lo muestra como "success".

**Qué hacer:**
- **Frontend:** Reordenar la lógica de status para que `hasResult` tenga prioridad sobre `waitingForChunk`:
  ```js
  const status = hasResult
    ? (isError ? "error" : "success")
    : waitingForChunk
      ? "calling"
      : (isStreaming && isLatestTool ? "calling" : (isStreaming ? "done" : (isTask ? (hasChildResponse ? "success" : "error") : "error")));
  ```
- **Backend (`backend/agent/tools.py`, `task()`):** marcar `state="error"` cuando el sub-agente no produce una respuesta final (final_text vacío) o cuando su loop devuelve un error. Así el XML refleja el error real.
- **Frontend:** ampliar `isError` para detectar `task_result` vacío o con texto de error (además de `state="error"`).

---

## Bug 3 — El mensaje de bienvenida no aparece al recargar / cargar una conversación

**Síntoma:** El mensaje "¡Hola! Soy el asistente..." aparece en la UI al iniciar, pero al refrescar la página o cargar una conversación guardada, no aparece. Debe aparecer siempre.

**Causa raíz:** `WELCOME_MESSAGE` (`frontend/src/components/ChatInterface.tsx`, línea 31) es un mensaje solo de frontend (`id: "welcome"`), no se guarda en backend. En `App.tsx`:
- `handleNewChat` (línea 180) lo setea: `setMessages([WELCOME_MESSAGE])` ✅
- `handleSelectSession` (línea 195) lo reemplaza: `setMessages(mapSessionMessages(data.messages))` ❌ (no incluye el welcome)

**Qué hacer:**
- En `App.tsx` `handleSelectSession`, anteponer el `WELCOME_MESSAGE` a los mensajes cargados:
  ```js
  setMessages([WELCOME_MESSAGE, ...mapSessionMessages(data.messages)]);
  ```

---

## Bug 4 — El sub-agente tarda muchísimo en empezar a trabajar (tiempos)

**Síntoma:** La burbuja de `task` aparece rápido, pero el sub-agente tarda ~2 minutos en hacer su primera llamada al LLM.

**Verificación en logs (NO es la ventana de contexto):**
- El sub-agente `4455af8a`: `build_initial_messages` a las `22:43:32.361` → `ANTES_llm` a las `22:45:31.785` = **~119s**.
- En ese tramo, `messages in context: 2` → **NO es la ventana de contexto** (son solo 2 mensajes).
- El gap está entre `build_initial_messages` y el primer `ANTES_llm`, que es donde corre la **generación de título**.

**Causa raíz:** En `backend/agent/loop.py` (líneas ~406-440), cuando `turn_number == 1` (toda sesión nueva, incluida **cada sub-sesión**), se genera el título con `llm_process` **no-streaming** (`max_tokens=2000`). Esa llamada bloquea el loop antes de empezar a trabajar. Cada sub-agente crea una sesión hija nueva (turn 1) → genera título → ~120s de bloqueo.

**Qué hacer:**
- Agregar prints de debug (con timestamp) alrededor de la generación de título para confirmar el tiempo exacto.
- **No generar título para sub-agentes** (`depth > 0`): los sub-agentes no necesitan título.
- Evaluar hacer la generación de título no-bloqueante (en background) para la sesión raíz.

---

## Notas / pendientes de contexto

- El fix del bug de "segunda llamada al mismo sub-agente muestra el trabajo previo" ya se aplicó (frontend-only, `chatBlocks.tsx` con `taskIndex`). Verificado con `tsc --noEmit`.
- Los cambios de frontend se copian a `D:\test-forge` (copia de despliegue).

---

## Cambios aplicados (2026-08-07)

| Bug | Archivo(s) | Cambio |
|-----|-----------|--------|
| 1 | `frontend/src/components/sessionsTab.tsx` | Se quitó `maxHeight: "70%"` del contenedor de historial → scrollea completo. |
| 2 (frontend) | `frontend/src/components/chatBlocks.tsx` | Status: `hasResult` tiene prioridad sobre `waitingForChunk` (una task terminada muestra su estado aunque el padre siga streamando). `isError` ampliado: detecta `state="error"`, `task_result` vacío y "Ocurrió un error". |
| 2 (backend) | `backend/agent/tools.py` | `task()` marca `state="error"` cuando el sub-agente termina sin respuesta final (final_text vacío) o devuelve el mensaje de error del loop. |
| 3 | `frontend/src/App.tsx` | `handleSelectSession` antepone `WELCOME_MESSAGE` a los mensajes cargados. |
| 4 | `backend/agent/loop.py` | Título solo en `turn_number == 1 and depth == 0` (sub-agentes NO generan título). Para depth 0, la generación corre en background task (no bloquea el stream) con `max_tokens=100` (antes 2000, causa del ~120s). El resultado se emite vía cola drenada en cada iteración. |

**Verificación:** `python -c "import ast; ast.parse(...)"` OK en `loop.py` y `tools.py`; `npx tsc --noEmit` sin errores. Archivos copiados a `D:\test-forge`.