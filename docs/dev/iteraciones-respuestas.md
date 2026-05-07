<p align="center">
  <img src="../../src/LogoBlancoGrande2.png" alt="Logo" width="150">
</p>

<h1 align="center">synapseForge</h1>

<p align="center">
  Iteraciones con Agentes - Respuestas
</p>

---

# Iteraciones con Agentes - Respuestas

Este documento registra las iteraciones con agentes especializados y sus respuestas. Es un documento vivo que se actualiza conforme avanza el desarrollo.

**Nota**: Este documento NO modifica el archivo origen `items-iteracion.md.origin`.

---

## Fase 0: Investigación Preliminar

### F0.1 - Proveedor de Vector Store

| Atributo | Detalle |
|----------|---------|
| **Item** | Selección de proveedor de base de datos vectorial |
| **Agente** | ai-architect + NotebookLM (agent-infrastructure) + Web Search |
| **Estado** | Completado |
| **Fecha** | Mayo 2026 |

**Pregunta formulada:**
1. ¿Neon PostgreSQL soporta la extensión pgvector? ¿Hay limitaciones en la capa gratuita?
2. Si Neon no soporta pgvector, ¿cuáles son las mejores alternativas considerando? (Chroma, Qdrant, Weaviate)
3. Para cada alternativa, considerar: capacidades vectoriales, costos, facilidad de integración con Python, y si tiene tier gratuito.

**Respuesta:**

## Recomendación Principal: Neon + pgvector

### Justificación técnica (fuentes verificadas)

**Documentación de Neon pgvector:**
- https://neon.tech/docs/extensions/pgvector - Docs oficiales confirman soporte completo de pgvector (versión 0.8.0/0.8.1) con tipos vector, HNSW, IVFFlat
- https://neon.tech/docs/reference/pg-extensions/ - Tabla de extensiones soportadas

**Características confirmadas:**
- Tipos vector suportados: `vector` (hasta 2000 dimensiones), `halfvec` (hasta 4000), `bit` (hasta 64000), `sparsevec`
- Índices: HNSW (recomendado para producción, 95-99% recall), IVFFlat
- Funciones de distancia: L2, inner product, cosine, L1, Hamming, Jaccard
- ACID guarantees completos del estándar PostgreSQL
- SQL ecosystem completo para combinar búsqueda semántica con filtros relacionales

**Precios (fuentes verificadas):**
- https://www.neon.tech/pricing - Free: 0.5 GB/project, 100 CU-hours/month, 5 GB egress
- https://neon.com/blog/new-usage-based-pricing - Launch: $0.106/CU-hour, $0.35/GB-month; Scale: $0.222/CU-hour
- https://dev.to/kencho/vector-database-performance-compared -Costo estimado: Neon ~$30-150/mes vs RDS ~$260

### Alternativas evaluadas con pros/contras

| Proveedor | Pros | Contras | Fuentes |
|----------|------|--------|----------|
| **Neon + pgvector** | Storage unificado (configs + history + vectors), SQL completo, multi-tenant nativo con RLS, ACID guarantees, tier gratuito (0.5 GB) | 500MB free limit, latencia >200ms tras 1M vectores | https://neon.tech/docs/extensions/pgvector, https://neon.tech/pricing |
| **Chroma** | Open source gratis, embedded mode (no server), 3 líneas de código, API simple | Limited scale, no multi-user en embedded, no para producción masiva | https://docs.trychroma.com/docs/overview/getting-started |
| **Qdrant** | <10ms latencia (10M vectors), rich filtering, self-hosted gratis, Cloud desde $25/mes | Smaller ecosystem, managed menos maduro | https://qdrant.tech/documentation |
| **Supabase** | Similar a Neon, más features | Mismas limitaciones de pgvector, 500MB free | https://neon.tech/docs/extensions/pg-extensions/ |

### Recomendaciones finales

1. **Neon + pgvector** como proveedor principal para synapseForge
2. Usar schema multi-tenant con Row Level Security para aislamiento
3. Implementar abstracción VectorStore para permitir migración futura
4. Start con Neon Launch ($9-30/mes) para desarrollo
5. Considerar Qdrant si escala >1M vectors

### Fuentes completas

- [1] https://neon.tech/docs/extensions/pgvector - pgvector extension docs
- [2] https://neon.tech/docs/reference/pg-extensions/ - Supported extensions
- [3] https://www.neon.tech/pricing - Pricing plans
- [4] https://neon.com/blog/new-usage-based-pricing - New pricing (Aug 2025)
- [5] https://dev.to/kencho/vector-database-performance-compared-pgvector-vs-pinecone-vs-qdrant-vs-weaviate-2b4h - Cost comparison
- [6] https://docs.trychroma.com/docs/overview/getting-started - Chroma docs
- [7] https://qdrant.tech/documentation - Qdrant docs
- [8] NotebookLM agent-infrastructure: Neon + pgvector documentation
- [9] NotebookLM agent-infrastructure: Chroma vector database docs
- [10] NotebookLM agent-infrastructure: Qdrant docs
- [11] NotebookLM agent-infrastructure: Supabase + vector storage docs

**Notas adicionales:**
- Crear cuenta Neon al inicio del proyecto
- Dependencias: F0.2 (configs), F0.3 (history), F0.4 (vector search) dependen de F0.1
- Para <1M vectors, pgvector es suficiente y más einfach zu integrieren que databases separadas


---

### F0.2 - Análisis del Sistema de Referencia

| Atributo | Detalle |
|----------|---------|
| **Item** | Documentar flujo de ejecución del chat_orchestrator para compatibilidad arquitectónica |
| **Agente** | ai-architect + NotebookLM (synapse-architecture, ai-architect) |
| **Estado** | Completado |
| **Fecha** | Mayo 2026 |

**Pregunta formulada:**
Analizar el flujo de ejecución del chat_orchestrator para definir compatibilidad arquitectónica con synapseForge. Solo el flujo es compatible, no las herramientas ni prompts. Incluir: comportamiento según status (success/error/canceled), contratos de herramientas, puntos de bypass, observabilidad, prompts dinámicos, y gestión de modelos.

**Respuesta:**

## Resumen del Análisis - Arquitectura AI-Native

### 1. Flujo del Orquestador (5 etapas)
- **Router (LLM0)**: Clasifica intención y determina ruta (11 rutas posibles: direct, planner, clarify, etc.)
- **Planner (LLM1)**: Genera plan de pasos si la solicitud es compleja
- **Decision Maker (LLM2)**: Traduce lenguaje natural a parámetros JSON
- **Executor (Tools)**: Ejecuta las herramientas
- **Validator (LLM4)**: Valida output antes de síntesis final

### 2. Comportamiento según Status
- **Success**: El flujo continúa al siguiente paso o a la síntesis final
- **Error/Canceled**: Se activa bucle de corrección - el feedback se reinyecta al Planner para ajustar estrategia

### 3. Puntos de Bypass
- **Direct**: Respuestas simples saltan Planner/Decision Maker/Validator
- **Single tool**: Omite Planner si es una sola herramienta
- **Consultas determinísticas**: Omite Validator
- **Nombre de persona**: Bypass de RAG, usa búsqueda de perfiles

### 4. Contrato de Herramientas
```
{status, message, data: {reasoning, output, correction}, usage}
```

### 5. Observabilidad
- **_debug_id**: Identificador de rastreo que se propaga
- **reasoning**: Campo obligatorio en todos los agentes
- **usage**: Métricas de tokens y tiempo de ejecución

### 6. Prompt Engineering vs Context Engineering
- **Prompt Engineering**: "Constitución" del sistema - reglas fijas, formato JSON, "no inventar datos"
- **Context Engineering**: Inyección dinámica en runtime - memoria usuario, historial, feedback loops

### 7. Gestión de Modelos (LLM vs SLM)
- **LLMs**: Router, Planner, Decision Maker, Validator, Síntesis final
- **SLMs/Especializados**: Embeddings (búsqueda semántica), Reranking, Búsqueda web
- **Justificación**: Reducción de latencia, precisión por descomposición, eficiencia en RAG, resiliencia

---

## Evaluación con Prácticas Modernas (2026)

| Componente | Nivel de Alineación |
|------------|---------------------|
| Router (Handoff dinámico) | Máximo |
| Planner (Magentic Task-Ledger) | Excelente |
| Decision Maker (Separation of Concerns) | Alto |
| Validator (Maker-Checker/LLM Judge) | Máximo |
| Bypasses (Tiered Complexity) | Excelente |
| Clarify (Human-in-the-Loop) | Necesario |

**Conclusión**: Arquitectura "AI-Native" - trata a la IA como plano de control de un sistema distribuido. Escalable, auditable, financieramente sostenible.

**Documentos completos:**
- `docs/dev/F0.2-analisis-sistema-referencia.md`
- `docs/dev/F0.2-evaluacion-practicas-modernas.md`




---

### F0.3 - Selección de Tecnologías

| Atributo | Detalle |
|----------|---------|
| **Item** | Selección de tecnologías de implementación |
| **Agente** | ai-architect |
| **Estado** | [Pendiente/In Progress/Completado] |
| **Fecha** | |

**Pregunta formulada:**


**Respuesta:**


**Notas adicionales:**


---

*Documento generado: Mayo 2026*
*Versión: 1.0*
*Tipo: Iteraciones con Agentes*