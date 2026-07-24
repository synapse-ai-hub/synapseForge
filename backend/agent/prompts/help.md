# Ayuda del sistema

Ésta es la documentación de referencia del sistema. Acá se explica cómo configurar agentes, tools, skills y las opciones disponibles. Si tenés dudas sobre cómo usar o configurar el sistema, preguntale directamente al agente. El agente tiene acceso a herramientas internas para leer archivos, buscar en la web, ejecutar comandos, etc. Para más detalles sobre las herramientas disponibles, indicar que se consulte la documentación del agente.

## Agentes

Los sub-agentes son agentes especializados que se definen externamente al código. Cada uno tiene su propio rol, herramientas y skills.

### Crear un agente

1. Crear un archivo `.md` en la carpeta de agentes de la configuración (`~/.config/synapseForge/agents/`).
2. El nombre del archivo (sin la extensión `.md`) es el identificador que se usa para invocarlo mediante `task`.
3. El archivo debe contener un bloque de frontmatter YAML al inicio, delimitado por `---`. Campos disponibles:

   - **`name`**: Nombre legible del agente.
   - **`description`**: Descripción breve que explica qué hace y cuándo debe ser usado.
   - **`permission`**: Define las tools y sub-agentes a los que tiene acceso. Si una tool no está listada, no estará disponible. Los valores posibles son `allow` (permitido) y `deny` (denegado).
     - Para tools planas: `read: allow`
     - Para `task` (delegación a sub-agentes): `task: { nombre_agente: allow }`
   - **`skill`**: Define qué skills puede cargar. Misma sintaxis que `permission`.
   - **`parameters`**: Configuración del modelo para este agente: `temperature`, `top_p`, `model`, `seed`.

4. Debajo del frontmatter va el cuerpo del prompt del agente: su rol, instrucciones específicas, reglas de comportamiento.

### Cómo se resuelven los permisos

Cuando el agente principal delega una tarea a un sub-agente mediante `task`, el sistema:
1. Lee el archivo `.md` del sub-agente.
2. Extrae el frontmatter.
3. Filtra las tools según `permission`: solo las marcadas como `allow` estarán disponibles.
4. Filtra las skills según `skill`.
5. Usa el cuerpo del markdown como system prompt del sub-agente.

Esto significa que un sub-agente solo puede usar lo que su archivo de definición le permite. No tiene acceso a tools no declaradas.

---

## Tools externas

Además de las tools internas del sistema, se pueden crear herramientas personalizadas.

### Crear una tool externa

1. Crear un archivo `.py` en la carpeta `tools/` de la configuración (`~/.config/synapseForge/tools/`).
2. El nombre del archivo (sin `.py`) debe coincidir con el nombre de la herramienta y con el de la función que contiene.
3. La primera línea del docstring del módulo es la descripción que el LLM usará para decidir si invocar la tool.
4. La función debe ser `async` y debe devolver el contrato `{status, message, data, usage}`.
5. Una vez creada, se puede habilitar para cualquier agente agregándola en su `permission`.

---

## Skills

Las skills son conjuntos de instrucciones y material de referencia que se cargan bajo demanda.

### Crear una skill

1. Crear una carpeta en `~/.config/synapseForge/skills/`.
2. Dentro de esa carpeta, crear `SKILL.md` con frontmatter YAML:
   - `name`: nombre de la skill.
   - `description`: descripción breve.
3. El cuerpo de `SKILL.md` es el contenido que se inyecta como contexto cuando el agente carga la skill.
4. Opcionalmente, crear una subcarpeta `references/` con archivos adicionales (catálogos, manuales, guías) que pueden cargarse individualmente con la herramienta `reference`.

---

## Configuración del modelo

El modelo y proveedor se configuran desde el panel de Configuración en la interfaz:

1. **Proveedor**: seleccionar entre los disponibles (Groq para API, Ollama para local).
2. **Modelo**: elegir entre los modelos disponibles para ese proveedor.
3. Los cambios persisten en la base de datos SQLite y se aplican al siguiente mensaje.

Soportados:
- **Groq**: modelos de API (Mixtral, Llama, etc.).
- **Ollama**: modelos locales.

---

## Ventana de contexto

Controla cuántos turnos de la conversación se recuerdan al responder:
- `-1`: todo el historial.
- `N`: los últimos N turnos.

Se configura desde el panel de Configuración.

---

## Modo verbose

Cuando está activado, las herramientas y sub-agentes se muestran en la interfaz durante la conversación. Se activa/desactiva desde el panel de Configuración.

---

## Archivos de contexto (Instrucciones y documentos)

Se pueden subir archivos desde el panel de Configuración en la sección **Instrucciones y documentos**. Los archivos subidos se inyectan automáticamente en el system prompt del agente como contexto adicional.

Formatos soportados: PDF, Word, TXT, MD, CSV, JSON, YAML, XML, PY.

Son útiles para proveer información de referencia permanente: manuales de empresa, reglas de negocio, documentación técnica, etc.

---

**ANTE CUALQUIER DUDA, PROHIBIDO INVENTAR, EXPLICARLE AL USUARIO QUE PUEDE CONSULTAR LA DOCUMENTACIÓN DEL AGENTE EN `Docs`, EN LA PARTE SUPERIOR DERECHA DEL AGENTE**.
