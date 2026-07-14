<p align="center">
  <img src="<logo>url_logo</logo>" alt="Logo" width="<width>ancho_logo</width>">
</p>

---

<h1 align="center">[API Routes — <descripcion>nombre_proyecto</descripcion>]</h1>

---

<p align="center">
  <a href="./LICENSE">
    <img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License: Apache 2.0" />
  </a>
</p>

---

<h3 align="center">[Endpoints HTTP de la API del <descripcion>nombre_proyecto</descripcion>]</h3>

---

## Descripción

Documentación de los endpoints HTTP expuestos por `backend/routes`. Se documentan los módulos **`chat`**, **`sessions`** y **`config`**.

### ✨ Rutas documentadas

- **`chat`**: conversación streaming vía Server-Sent Events (SSE).
- **`sessions`**: listado, obtención y eliminación de sesiones de chat.
- **`config`**: gestión de proveedores, modelos y ventana de contexto.

---

## Rutas

### 1. Chat (`backend/routes/chat.py`)

#### `POST /api/chat`

Streaming de un turno de conversación vía Server-Sent Events. Acepta el mensaje del usuario como `FormData`, opcionalmente con archivos adjuntos, y devuelve un `StreamingResponse` con `text/event-stream`. Internamente instancia `AgentLoop` y ejecuta `agent_loop.run(...)`.

**Parámetros (FormData):**

- `message` (str, **requerido**): mensaje del usuario.
- `session_id` (str, opcional): id de sesión. Si no se envía, se genera uno (`uuid4`).
- `stream_id` (str, opcional): id de stream.
- `files` (File, opcional): uno o varios archivos adjuntos. El texto se extrae con `extract_text_from_bytes` y se pasa al loop como `file_contents`.

**Respuesta:** `text/event-stream`. Eventos `data: {json}` y un evento final `data: [DONE]`. Si el cliente se desconecta, se cancela el stream vía `stream_cancel_event`.

---

### 2. Sessions (`backend/routes/sessions.py`)

#### `GET /api/sessions/titles`

Devuelve todos los títulos de sesiones existentes.

**Respuesta:** `JSONResponse` `{status, data: string[]}`.

#### `GET /api/sessions`

Devuelve todas las sesiones de chat ordenadas por actividad más reciente.

**Respuesta:** `JSONResponse` `{status, data: Session[]}` donde `Session` incluye `session_id`, `created_at`, `updated_at`, `title`, `preview`, `message_count`.

#### `GET /api/sessions/{session_id}`

Devuelve el historial completo de mensajes de una sesión.

Solo se retornan mensajes con `role` `user` y `assistant`, mapeados a formato frontend-friendly (`id`, `type`, `content`, `toolCalls`, `toolResults`).

**Respuesta:** `JSONResponse` `{status, data: {session_id, messages[]}}`.

#### `DELETE /api/sessions/{session_id}`

Elimina una sesión y todos sus mensajes.

**Respuesta:** `JSONResponse` `{status, message}`.

#### `DELETE /api/conversations`

Elimina **todas** las conversaciones (tabla `conversaciones` completa). Operación destructiva, usar con precaución.

**Respuesta:** `JSONResponse` `{status, message}`.

---

### 3. Config (`backend/routes/config.py`)

#### `GET /api/config/providers`

Lista los proveedores disponibles (Ollama si `ollama list` responde, Groq si hay `GROQ_API_KEY` configurada).

**Respuesta:** `JSONResponse` `{status, providers: string[]}`.

#### `GET /api/config/models`

Lista los modelos disponibles según `provider` (query param `provider=LOCAL|API`).

- `LOCAL` → ejecuta `ollama list`.
- `API` → consulta la API de Groq.

**Respuesta:** `JSONResponse` `{status, provider, models: string[], model: string}`.

#### `POST /api/config/models/select`

Selecciona un modelo para la sesión y lo guarda en `agent._resolved_model` y `agent.provider`.

**Body (JSON):** `{"model": "nombre_modelo", "provider": "LOCAL|API"}`

**Respuesta:** `JSONResponse` `{status, message, model}`.

- `400` → si `model` está vacío.
- `503` → si el agente no está inicializado.

#### `GET /api/config/context-window`

Devuelve el límite de turns de contexto (`-1` = todos).

**Respuesta:** `JSONResponse` `{status, max_turns}`.

#### `POST /api/config/context-window`

Setea el límite de turns de contexto.

**Body (JSON):** `{"max_turns": 10}`

- `-1` = todos los turns. Debe ser `-1` o un entero positivo (no `0`).

**Respuesta:** `JSONResponse` `{status, message, max_turns}`.

#### `GET /api/config/mcp/servers`

Lista los servidores MCP configurados en `config.json`.

**Respuesta:** `JSONResponse` `{status, servers: object}`.

#### `GET /api/config/mcp/health`

Verifica la salud de todos los servidores MCP configurados.

**Respuesta:** `JSONResponse` `{status, results: McpServerStatus[]}`.

---

## Pruebas

Servidor corriendo en `http://127.0.0.1:8000` (uvicorn `backend.main:app`).

### `POST /api/chat`

**cURL**
```bash
curl -X POST http://127.0.0.1:8000/api/chat -F "message=Hola, ¿qué podés hacer?"
```

**Invoke (PowerShell)**
```powershell
$resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/chat" -Method Post -ContentType "application/x-www-form-urlencoded" -Body "message=Hola, ¿qué podés hacer?" -TimeoutSec 120
$resp.Content
```

Con `session_id` fijo:

**cURL**
```bash
curl -X POST http://127.0.0.1:8000/api/chat -F "session_id=test-1" -F "message=Hola, ¿qué podés hacer?"
```

**Invoke (PowerShell)**
```powershell
$resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/chat" -Method Post -ContentType "application/x-www-form-urlencoded" -Body "session_id=test-1&message=Hola, ¿qué podés hacer?" -TimeoutSec 120
$resp.Content
```

### `GET /api/sessions`

**cURL**
```bash
curl -X GET http://127.0.0.1:8000/api/sessions
```

**Invoke (PowerShell)**
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/sessions"
```

### `GET /api/config/providers`

**cURL**
```bash
curl -X GET http://127.0.0.1:8000/api/config/providers
```

**Invoke (PowerShell)**
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/config/providers"
```

### `GET /api/config/models?provider=LOCAL`

**cURL**
```bash
curl -X GET "http://127.0.0.1:8000/api/config/models?provider=LOCAL"
```

**Invoke (PowerShell)**
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/config/models?provider=LOCAL"
```

### `POST /api/config/models/select`

**cURL**
```bash
curl -X POST http://127.0.0.1:8000/api/config/models/select -H "Content-Type: application/json" -d "{\"model\": \"llama3.2\", \"provider\": \"LOCAL\"}"
```

**Invoke (PowerShell)**
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/config/models/select" -Method Post -ContentType "application/json" -Body '{"model": "llama3.2", "provider": "LOCAL"}'
```

### `POST /api/config/context-window`

**cURL**
```bash
curl -X POST http://127.0.0.1:8000/api/config/context-window -H "Content-Type: application/json" -d "{\"max_turns\": 10}"
```

**Invoke (PowerShell)**
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/config/context-window" -Method Post -ContentType "application/json" -Body '{"max_turns": 10}'
```

---

## Licencia

Este proyecto está licenciado bajo los términos especificados en el archivo [LICENSE](./LICENSE) ubicado en la raíz del repositorio.

---

Copyright (c) 2026 <legal>nombre_legal_empresa</legal>

---