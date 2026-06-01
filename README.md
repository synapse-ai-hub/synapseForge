<p align="center">
  <img src="https://github.com/synapse-ai-hub/sources/raw/main/logo.png" alt="Logo" width="150">
</p>

<h1 align="center">synapseForge</h1>

<p align="center">
  Framework Python para construir, orquestar y desplegar agentes de IA a escala.
</p>

<p align="center">
  <a href="./LICENSE">
    <img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License: Apache 2.0" />
  </a>
</p>

---

## Qué es synapseForge

**synapseForge** es un framework que permite construir agentes de IA sin necesidad de programar. El usuario describe lo que necesita en lenguaje natural, el builder genera la estructura del agente, se itera hasta que queda conforme, y luego se compila en código ejecutable.

A diferencia de LangChain, CrewAI, AutoGen y n8n — que requieren escribir código o configurar nodos manualmente — synapseForge funciona en modo conversacional: vos explicás lo que necesitás y el framework lo construye solo.

El framework incluye primitivas propias para Agent, Tool, Memory y Pipelines de ejecución, con validación exhaustiva, prompting estructurado, y observabilidad completa.

---

## El Problema

Construir agentes de IA requiere saber programar. LangChain y CrewAI exigen escribir código Python. n8n requiere configurar nodos visualmente. En todos los casos, si no sabés de código, estás limitado.

synapseForge invierte esa ecuación: el conocimiento está en el framework, no en el usuario. Vos describís la intención en lenguaje natural y el builder se encarga del resto.

---

## Arquitectura

```
synapseForge/
├── core/           # Primitivas propias: Agent, Tool, Memory, State
├── pipelines/      # Pipeline de ejecución: Router, Planner, Executor, Validator
├── builder/        # Asistente conversacional
└── templates/      # Arquetipos de agentes predefinidos
```

### Core — Primitivas del Framework

- **Agent**: Entidad autónoma con modelo, herramientas, memoria y configuración
- **Tool**: Funciones ejecutables que el agente puede invocar
- **Memory**: Memoria de corto plazo (sesión) y largo plazo (histórico)
- **State**: Gestión de estado para workflows complejos

### Pipelines — Orquestación

Pipeline de ejecución robusto que incluye:

- **Router**: Decide el modo de operación según el input
- **Planner**: Genera el plan de ejecución
- **Executor**: Ejecuta las herramientas
- **Validator**: Valida inputs y outputs en cada paso

Cada paso incluye validación exhaustiva, retry inteligente con backoff, y streaming progresivo.

### Builder — Constructor Conversacional

Flujo completo:

1. **Usuario describe** en lenguaje natural lo que necesita
2. **Builder genera** una especificación preliminar
3. **Iteración** hasta que el usuario queda conforme
4. **Compilación** a código Python ejecutable

### Templates — Arquetipos

Agentes predefinidos listos para usar o personalizar:

- Research Agent
- Outreach Agent
- Support Agent
- Analysis Agent
- Orchestrator

---

## Comparación con Frameworks Existentes

| Feature | synapseForge | LangChain | CrewAI | AutoGen | n8n |
|---------|-------------|----------|-------|--------|-----|
| **Modo de uso** | Conversacional | Código | Código | Código | Visual |
| **Programar** | No requerido | Requiere | Requiere | Requiere | Parcial |
| **Spec visual** | Sí (Markdown) | No | No | No | Parcial |
| **Iteración** | Sí | No | No | No | Limitado |
| **Compilación** | Automática | No | No | No | No |
| **Primitivas propias** | Sí | No | No | No | No |
| **Validación exhaustiva** | Sí | No | No | No | Limitado |
| **Prompting estructurado** | Sí | No | No | No | No |
| **Multi-agente** | Sí | Sí | Sí | Sí | Limitado |
| **Memoria** | Corto y largo plazo | Básica | Básica | Moderada | Básica |
| **Observabilidad** | Completa | LangSmith | Limitada | Azure | Logs |
| **Streaming** | Sí | Sí | Sí | Sí | Sí |

---

## Diferenciadores Clave

### Sin Programar

El usuario no escribe código. Describe en lenguaje natural y el builder genera todo. Esto es lo que ningún otro framework ofrece.

### Primitivas Propias

synapseForge no depende de LangChain ni ninguna otra librería. Todo está implementado desde cero: Agent, Tool, Memory, Pipeline. El builder genera código que usa exclusivamente el framework propio.

### Validación Exhaustiva

Cada input y output se valida antes de ejecutarse. Si una tool falla, el framework no continúa ciegamente — valida, reporta el error, y permite corregir antes de seguir.

### Prompting Estructurado

El framework incluye ingeniería de prompts integrada. No vas a escribir prompts a mano — el builder los genera con estructura específica para cada caso de uso.

### Memoria Robusta

Memoria de corto plazo (sesión actual) y largo plazo (histórico por usuario). Aislamiento total entre sesiones.

### Observabilidad Completa

Traces, métricas, errores detallados, cost tracking. Todo built-in, sin dependencias externas.

---

## Cómo Funciona el Builder

### Paso 1: Descripción

El usuario escribe:

```
"Quiero un agente que busque información de empresas en la web,
les envíe un email personalizado con los hallazgos,
y guarde los resultados en una base de datos."
```

### Paso 2: Generación

El builder genera una spec en Markdown.

### Paso 3: Iteración

El usuario revisa, sugiere cambios. El builder regenera con los cambios.

### Paso 4: Compilación

Cuando el usuario aprueba, el builder genera:

- `agente.py`: Clase principal
- `tools.py`: Herramientas personalizadas
- `config.yaml`: Configuración
- `requirements.txt`: Dependencias
- `README.md`: Instrucciones

### Paso 5: Ejecución

```python
from mi_agente import Agent

agent = Agent(config="config.yaml")
agent.run(query="empresas de tecnología en Buenos Aires")
```

---

## Público Objetivo

### Desarrolladores

Pueden usar el framework directamente o usar el builder para prototipar. El código generado es código Python estándar, readable y modificable.

### No-Técnicos

El builder les da acceso a Agent sin saber programar. Describir, iterar, usar.

### Empresas

Self-hosting, control total, sin dependencias de terceros. El agente se ejecuta donde quieras.

---

## Por Qué Elegir synapseForge

1. **No necesitás programar** — Describís y usan. LangChain requiere código; synapseForge no.

2. **Es flexible y adaptable** — El framework es tuyo, no dependés de las limitaciones de LangChain o n8n. Herramientas custom, validaciones custom, prompting custom.

3. **Validación exhaustiva** — LangChain pasa errores; synapseForge valida, reporta, y permite corregir.

4. **Prompting integrado** — El builder genera prompts con ingeniería estructura, no a mano.

5. **Memoria robusta** — Aislamiento total entre sesiones y usuarios.

6. **Herramientas propias** — Definís las herramientas que necesitás. Ninguna predefinida. Todo lo creás vos.

---

## Estado Persistente

Checkpointing nativo con:

- **Pause & Resume**: Pausar, esperar input humano, continuar
- **Time-travel**: Volver a un estado anterior y re-ejecutar
- **Multi-thread**: Múltiples ejecuciones paralelas con aislamiento

---

## Roadmap

### Fase 1: MVP

- Builder conversacional básico
- Spec en Markdown
- Pipeline de ejecución
- Templates 3 agentes
- Ejecución CLI

### Fase 2: Beta

- Iteración visual (interfaz)
- Compilación automática
- Checkpointing básico
- Observabilidad integrada

### Fase 3: Production

- Agentes multi-thread
- Dashboard de métricas
- Deployment simplificado

### Fase 4: Enterprise

- Teams y multi-tenant
- RBAC
- Plugins personalizables

---

## Instalación

1. **Clonar el repositorio**

```bash
git clone https://github.com/synapse-ai-hub/synapseForge.git
cd synapseForge
```

2. **Crear y activar un entorno virtual** (recomendado Python 3.12+)

```bash
py -3.12 -m venv .synapseForge
.\synapseForge\Scripts\Activate.ps1
```

3. **Instalar dependencias**

```bash
pip install -r requirements.txt
```

4. **Inicializar base de datos**

```bash
python db/ddl_setup.py
```

---

## Uso

### Constructor Conversacional

```python
from synapseforge import Builder

builder = Builder()
spec = await builder.generate_spec("Quiero un agente que...")
await builder.compile(spec)
```

### Framework Directo

```python
from synapseforge import Agent

agent = Agent(tools=[...])
await agent.run("tu query")
```

---

## Stack

- Python 3.12+
- FastAPI
- PostgreSQL + pgvector
- Multi-provider: Groq, OpenAI, Anthropic, Bedrock, Ollama

---

## Licencia

Apache 2.0 - Ver archivo [LICENSE](./LICENSE)

---

## Recursos

- Repositorio: https://github.com/synapse-ai-hub/synapseForge
- Documentación: Ver carpeta `docs/producto/`