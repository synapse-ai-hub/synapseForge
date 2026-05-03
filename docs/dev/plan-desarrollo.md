<p align="center">
  <img src="../../src/LogoBlancoGrande2.png" alt="Logo" width="150">
</p>

<h1 align="center">synapseForge</h1>

<p align="center">
  Plan de Desarrollo Integral
</p>

---

# Plan de Desarrollo - synapseForge

## 1. Objetivo del Documento

Este documento establece el plan de desarrollo integral para synapseForge, un framework Python diseñado para construir, orquestar y desplegar agentes de IA mediante un constructor conversacional. El plan se elabora en base a la arquitectura técnica definida en `arquitectura-tecnica.md` y las decisiones tomadas derivadas de las respuestas del usuario en `preguntas-desarrollo.md`.

El documento tiene como propósito guiar el desarrollo desde la fase de investigación preliminar hasta el despliegue del MVP, proporcionando tareas específicas, dependencias entre tareas, entregables definidos y los agentes responsables de cada área que requiere iteración.

---

## 2. Visión del Producto

synapseForge es un framework que permite a usuarios construir agentes de IA mediante descripción en lenguaje natural, sin necesidad de escribir código. El constructor conversacional genera una especificación técnica, itera con el usuario hasta obtener aprobación, y compila código Python ejecutable que incluye el agente, herramientas personalizadas, configuración,tests unitarios y documentación.

La diferenciación principal respecto a frameworks existentes (LangChain, CrewAI, AutoGen, n8n) radica en tres pilares: el constructor conversacional que elimina la necesidad de programación, el framework propio sin dependencias externas que evita limitaciones de librerías de terceros, y la validación exhaustiva que garantiza calidad del código generado mediante revisiones automatizadas.

El framework opera bajo cuatro principios arquitectónicos fundamentales: independencia total de cualquier librería externa, validación obligatoria antes de cada ejecución, serialización completa del estado para persistencia y recuperación, y aislamiento de sesiones entre usuarios.

---

## 3. Arquitectura de Componentes

### 3.1 Capas del Sistema

El sistema se organiza en seis capas claramente diferenciadas que proporcionan la funcionalidad completa del framework.

La primera capa corresponde al Constructor Conversacional, responsable de receber la descripción del usuario en lenguaje natural, generar la especificación técnica en formato Markdown, gestionar los ciclos de iteración hasta obtener aprobación del usuario, y compilar el código Python ejecutable final. Esta capa constituye la interfaz principal entre el usuario no técnico y el sistema.

La segunda capa corresponde al Núcleo del Framework, que contiene las primitivas propias del sistema: la entidad Agent que encapsula el comportamiento del agente, la entidad Tool que define funciones ejecutables, el sistema de Memory que gestiona memoria de corto y largo plazo, y la State Machine que controla el estado del agente durante la ejecución.

La tercera capa corresponde al Pipeline de Ejecución, compuesto por cuatro componentes secuenciales: el Router que determina el modo de operación según el input recibido, el Planner que genera el plan de ejecución para tareas complejas, el Executor que ejecuta las herramientas definidas en el plan, y el Validator que valida inputs y outputs en cada paso del pipeline.

La cuarta capa corresponde al Sistema de Proveedores, que abstrae la comunicación con diferentes modelos de lenguaje. El sistema soporta múltiples proveedores incluyendo Groq, OpenAI, Anthropic, Bedrock y Ollama para modelos locales, con rate limiting configurable por usuario y el usuario.

La quinta capa corresponde al Sistema de Persistencia, que gestiona el almacenamiento de agentes generados, configuraciones, history de ejecuciones, métricas, y memoria de largo plazo. Toda la información se persiste en base de datos, sin utilización de archivos locales para el almacenamiento principal.

La sexta capa corresponde al Sistema de Observabilidad, que provee tracing completo de ejecuciones, métricas de usage por cada llamada LLM, logging estructurado y debugging integrado sin dependencias externas.

### 3.2 Flujo de Construcción de Agente

El flujo de construcción de un agente mediante el constructor conversacional sigue una secuencia definida de seis etapas.

En la primera etapa, el usuario describe en lenguaje natural lo que necesita el agente. Por ejemplo: "Quiero un agente que busque información de empresas en la web, les envíe un email personalizado con los hallazgos, y guarde los resultados en una base de datos."

En la segunda etapa, el constructor procesa la descripción y genera una especificación técnica preliminar en formato Markdown. Esta especificación incluye la descripción del agente, el pipeline de ejecución definiciónado en pasos, las herramientas personalizadas requeridas con sus parámetros, la configuración de memoria, y las validaciones específicas.

En la tercera etapa, el usuario revisa la especificación generada y proporciona feedback. Esta iteración puede continuar múltiples veces hasta que el usuario aprueba la especificación.

En la cuarta etapa, una vez aprobada la especificación, el compilador genera el código Python ejecutable, creando los archivos agente.py, tools.py, config.yaml, requirements.txt, tests unitarios con mocks, y README con instrucciones.

En la quinta etapa, el sistema ejecuta validación automática del código generado, incluyendo code review automatizado, tests unitarios, y type checking.

En la sexta etapa, el agente queda disponible para ejecución, ya sea mediante la API REST del sistema o integrado en la aplicación del usuario.

### 3.3 Flujo de Ejecución de Agente

El flujo de ejecución de un agente ya construido sigue una lógica de branching basada en la complejidad del input recibido.

Para consultas simples que no requieren planificación, el Router determina el modo de ejecución directa y entrega la respuesta sin pasar por el Planner.

Para tareas complejas que requieren múltiples pasos, el Router determina el modo de ejecución planificación y llama al Planner para generar un plan de ejecución. El plan contiene pasos definidos, dependencias entre pasos, validaiones requeridas y estrategias de fallback. Luego el Executor ejecuta cada paso del plan secuencialmente (o en paralelo si los pasos son independientes), con validación de input antes de cada ejecución, validación de output después de cada ejecución, gestión automática de errores con retry, y checkpoints guardados después de cada paso completado. El Validator revisa el resultado final y, si es válido, lo retorna al usuario; si no es válido, ejecutaa estrategia de fallback o reporta error.

---

## 4. Fase 0: Investigación Preliminar

### 4.1 Objetivos de la Fase

La Fase 0 tiene como objetivo realizar toda la investigación necesaria antes de comenzar la implementación del código. Esta fase es crítica para tomar decisiones arquitectónicas informadas y evitar errores de diseño que serían costosos de corregir posteriormente.

### 4.2 Tareas de Investigación

#### Tarea F0.1: Evaluación de Proveedores de Vector Store

Esta tarea determina qué proveedor de base de datos vectorial se utilizará para el sistema de memoria de largo plazo y potentially para el almacenamiento de configuraciones y history.

El análisis debe considerar Neon PostgreSQL como opción primaria debido a su capa gratuita, evaluando específicamente si soporta la extensión pgvector necesaria para búsquedas vectoriales. En caso de que Neon no soporte pgvector, la evaluación debe considerar alternativas incluyendo Chroma (embebido), Qdrant, y Weaviate, comparando capacidades, costos, y facilidad de integración.

Para desarrollar esta tarea, se recomienda utilizar el agente ai-architect con capacidad de investigación web para obtener información actualizada sobre las limitaciones actuales de cada proveedor.

**Entregable:** Documento de análisis comparativo con recomendación de proveedor y justificación técnica.

**Dependencias:** Ninguna.

#### Tarea F0.2: Análisis del Sistema de Referencia (Chat Orchestrator)

Esta tarea documenta el flujo de ejecución del sistema existente que funciona como referencia arquitectónica. El objetivo no es copiar las herramientas o prompts, sino solo entender el flujo del orquestador para garantizar compatibilidad arquitectónica.

El análisis debe documentar específicamente: cómo el Router determina el modo de operación, cómo el Planner genera planes de ejecución, cómo el Executor ejecutaa herramientas, cómo el Validator valida inputs y outputs, cómo se manejan los errores sin interrumpir el flujo, cómo se implementa el streaming SSE, y cómo se persiste el estado.

**Entregable:** Documento técnico con diagrama de flujo del orquestador, focused únicamente en la arquitectura de ejecución.

**Dependencias:** Ninguna.

**Nota importante:** Este análisis es exclusivamente para compatibilidad arquitectónica. Las herramientas, prompts, y cualquier implementación específica del sistema de referencia NO se transfieren a synapseForge. El nuevo sistema tiene su propia implementación desde cero, tylko el flujo general de ejecución es compatible.

#### Tarea F0.3: Selección de Tecnologías de Implementación

Esta tarea evalúa y selecciona las tecnologías específicas para la implementación del framework.

Las decisiones a tomar incluyen: selección entre @dataclass de Python versus Pydantic para definición de esquemas de datos, selección de biblioteca HTTP asíncrona (aiohttp o built-in asyncio), selección de biblioteca de hashing para passwords (bcrypt o pgcrypto), y selección de biblioteca de logging estructurado.

Para desarrollar esta tarea, se recomienda utilizar el agente ai-architect para evaluar las opciones técnicas.

**Entregable:** Documento de decisiones tecnológicas con justificaciones.

**Dependencias:** F0.2 (conocer el sistema de referencia para entender patrones existentes).

### 4.3 Entregables de la Fase

Al concluir la Fase 0, se debe contar con: documento de evaluación de proveedores de vector store con recomendación, documento de análisis del flujo del orquestador para compatibilidad, y documento de decisiones tecnológicas para la implementación.

### 4.4 Timeline de la Fase

La Fase 0 tiene una duración estimada de dos semanas. Las tareas F0.1 y F0.2 pueden desarrollarse en paralelo, mientras que F0.3 depende de F0.2 para entender los patrones existentes en el sistema de referencia.

---

## 5. Fase 1: Foundation - Núcleo del Framework

### 5.1 Objetivos de la Fase

La Fase 1 tiene como objetivo implementar las primitivas fundamentales del framework y el pipeline de ejecución. Estas abstracciones base son necesarias porque todo lo demás del sistema depende de ellas.

### 5.2 Primitivasdel Framework

#### Tarea F1.1: Implementación de la Clase Agent Base

La clase Agent constituye la entidad principal del framework. Esta clase debe encapsular: configuración del modelo (provider, nombre, parámetros), lista de herramientas disponibles, sistema de memoria, máquina de estados, y configuración adicional.

La implementación debe seguir el patrón de Entity described in the arquitectura técnica, con métodos principales para ejecución, planificación y validación. La clase debe ser extendible para permitir personalización mediante herencia o composición.

**Entregable:** Módulo Python con clase Agent base y tests unitarios.

**Dependencias:** F0.3 (decisiones tecnológicas), F1.5 (definicióndel Tool).

#### Tarea F1.2: Implementación de la Interfaz Tool

La interfaz Tool define el contrato obligatorio que toda herramienta debe respetar. Este contrato es estrictamente obligatorio: todas las herramientas deben devolver exactamente el formato `{status, message, data, usage}`.

La implementación debe definir: atributos de identificación (name, description, category), definiciónde parámetros con tipos y validaciones requeridas, método de ejecución asíncrono, método de validación de input, y método de validación de output.

**Entregable:** Módulo Python con clase base Tool y ejemplos de implementación.

**Dependencias:** Ninguna.

#### Tarea F1.3: Implementación del Sistema de Memory

El sistema de Memory gestiona la memoria de corto plazo (sesión actual) y largo plazo (histórico por usuario). La implementación debe обеспеcer: aislamento total entre sesiones de diferentes usuarios, persistencia en base de datos, búsqueda semántica para recuperación de memoria de largo plazo, y serialización completa para checkpoints.

El sistema de memoria se utiliza también para almacenar configuraciones de agentes, history de interacciones, y datos de contexto que persisten entre sesiones.

**Entregable:** Módulo Python con clases de Memory y tests unitarios.

**Dependencias:** Tarea F0.1 (proveedor de vector store seleccionado).

#### Tarea F1.4: Implementación de la Máquina de Estados

La State Machine gestiona los estados posibles del agente durante la ejecución. Los estados posibles incluyen IDLE, PLANNING, EXECUTING, VALIDATING, PAUSED, COMPLETED, FAILED, y RESUMING.

La implementación debe proporcionar: transiciones de estado definidas,serialización completa del estado para checkpoints, y capacidad de restauración desde checkpoint.

**Entregable:** Módulo Python con clase StateMachine y tests unitarios.

**Dependencias:** F1.3 (Memory para serialización).

#### Tarea F1.5: Implementación del Sistema de Registry de Herramientas

El sistema de Registry permite almacenar y recuperardefiniciones de herramientas personalizadas. El registro se almacena en la base de datos (no hardcoded), lo que permite modificación dinámica sin redeploy.

La implementación debe proporcionar: registro de nuevas herramientas, recuperación de herramientas registradas, listadode herramientas disponibles, y actualización de herramientas existentes.

**Entregable:** Módulo Python con clase ToolRegistry y scripts de base de datos.

**Dependencias:** F1.2 (interfaz Tool definida).

### 5.3 Pipeline de Ejecución

#### Tarea F1.6: Implementación del Router

El Router determina el modo de operación según el input recibido. La lógica de routing debe clasificar el input en categorías: consulta simple (ejecución directa), tarea compleja (requiere planificación), solicitud de herramienta específica, o solicitud de aprobación humana.

La implementación debe retornar: el tipo de ejecución seleccionada, el pipeline a utilizar, y los parámetros procesados.

**Entregable:** Módulo Python con clase Router y tests unitarios.

**Dependencias:** F1.4 (State Machine).

#### Tarea F1.7: Implementación del Planner

El Planner generael plan de ejecución para tareas complejas. El plan debe contener: pasos a ejecutar, dependencias entre pasos, validaciones requeridas para cada paso, estrategias de fallback para errores, y checkpoints programados.

La implementación debe utilizar el sistema de herramientas disponibles para seleccionar las herramientas apropiadas para cada paso del plan.

**Entregable:** Módulo Python con clase Planner y tests unitarios.

**Dependencias:** F1.6 (Router), F1.5 (Registry).

#### Tarea F1.8: Implementación del Executor

El Executor ejecuta las herramientasdefinidas en el plan. La implementación debe manejar: ejecución secuencial y paralela de pasos independientes, validación de input antes de cada ejecución, validación de output después de cada ejecución, guardadode checkpoint después de cada paso, y streaming de resultados progresivos.

**Entregable:** Módulo Python con clase Executor y tests unitarios.

**Dependencias:** F1.7 (Planner), F1.5 (Registry), F1.2 (Tool).

#### Tarea F1.9: Implementación del Validator

El Validator validainputs antes de la ejecución y outputs después de la ejecución. La validación de input debe verificar: parámetros requeridos presentes, tipos de parámetros correctos, y restricciones personalizadas. La validación de output debe verificar: estructura del resultado, contenido del resultado, y calidad mínima del resultado.

La implementación debe proporcionar retry automático con backoff exponencial ante errores: 3 intentos máximos con delay de 2**(i+1) segundos donde i es el número de intento.

**Entregable:** Módulo Python con clase Validator y tests unitarios.

**Dependencias:** F1.2 (Tool), F1.8 (Executor).

#### Tarea F1.10: Integración del Pipeline Completo

Esta tarea integra los cuatro componentes (Router, Planner, Executor, Validator) en un pipeline unificado. La integración debe proporcionar: ejecución del flujo completo desde que ingresa el input hasta que obtiene la respuesta, manejo de errores global sin interrupción del flujo (el orquestador nunca lanza excepciones al usuario), y logging de cada paso para observabilidad.

**Entregable:** Módulo Python con pipeline integrado y tests de integración.

**Dependencias:** F1.6, F1.7, F1.8, F1.9 (todas las tareas anteriores del pipeline).

### 5.4 Sistema de Proveedores LLM

#### Tarea F1.11: Implementación de Adaptadores para Proveedores

El sistema debe soportar múltiples proveedores de LLM. Cada proveedor requiere un adaptador específico que abstrae las diferencias de API.

Los proveedores a implementar incluyen: Groq (provider primario del sistema de referencia), OpenAI, Anthropic, Ollama (para modelos locales), y Bedrock (AWS).

Cada adaptador debe implementar una interfaz común con métodos para: generación de completions, streaming de completions, y obtención de información de usage.

Adicionalmente, se debe implementar rate limiting configurable por usuario con un máximo global seteado por el sistema.

**Entregable:** Módulo Python con adaptadores para cada provider y tests de integración.

**Dependencias:** Ninguna.

### 5.5 Entregables de la Fase

Al concluir la Fase 1, se debe contar con: módulo Agent con clase base, módulo Tool con interfaz y contrato obligatorio, módulo Memory con persistencia en DB, módulo StateMachine con serialización, módulo ToolRegistry con almacenamiento en DB, módulo Router, módulo Planner, módulo Executor, módulo Validator, pipeline integrado, y adaptadores para proveedores LLM.

### 5.6 Timeline de la Fase

La Fase 1 tiene una duración estimada de seis semanas. Las tareas F1.1 a F1.5 (Primitivas) ocupan las semanas 1-2. Las tareas F1.6 a F1.10 (Pipeline) occupy las semanas 3-5. La tarea F1.11 (Proveedores) ocupa la semana 6.

---

## 6. Fase 2: Constructor Conversacional

### 6.1 Objetivos de la Fase

La Fase 2 tiene como objetivo implementar el constructor conversacional que permite a usuarios no técnicos crear agentes mediante descripción en lenguaje natural.

### 6.2 Constructor Core

#### Tarea F2.1: Implementación del Intent Parser

El Intent Parser analiza la descripción del usuario y extrae la intención principal, parámetros relevantes, y restricciones. La implementación debe utilizar un LLM para procesar el lenguaje natural y convertirlo en una estructura estructurada.

La salida del Intent Parser debe incluir: objetivo principal del agente, pasos del workflow requeridos, herramientas necesarias, configuración de memoria requerida, y restricciones específicas.

**Entregable:** Módulo Python con clase IntentParser y tests de integración.

**Dependencias:** F1.11 (adaptadores de proveedores).

#### Tarea F2.2: Implementación del Spec Generator

El Spec Generator convierte el intent parseado en una especificación técnica formal en formato Markdown. La especificación debe seguir el formato definido en la arquitectura técnica.

La especificación generada debe incluir: descripción detallada del agente, pipeline de ejecución definiçãoado en pasos,definiciones de herramientas con parámetros, configuración de memoria, configuración del modelo, y validaciones específicas.

**Entregable:** Módulo Python con clase SpecGenerator y tests de integración.

**Dependencias:** F2.1 (Intent Parser).

#### Tarea F2.3: Implementación del Sistema de Iteración

El sistema de iteración gestiona el ciclo de feedback entre el usuario y el constructor. Cada iteración permite al usuario sugerir modificaciones y el sistema regenerar la especificación con los cambios.

Los tipos de feedback soportados incluyen: modificación de pasos del pipeline, ajuste de parámetros de herramientas, cambios en configuración de memoria, actualización de parámetros del modelo, y añadir o eliminar restricciones.

**Entregable:** Módulo Python con clase IterativeRefiner y tests de integración.

**Dependencias:** F2.2 (Spec Generator), F1.11 (adaptadores de proveedores).

#### Tarea F2.4: Implementación del Compilador

El Compilador transforma la especificación aprobada en código Python ejecutable. Los archivos generados deben incluir: agente.py (clase principal), tools.py (herramientas personalizadas), config.yaml (configuración), requirements.txt (dependencias), y README.md (documentación).

El código generado debe seguir: las primitivas del framework (no dependencias externas), type hints completos, docstrings para documentación, y estructura modular.

**Entregable:** Módulo Python con clase Compilador y tests de integración.

**Dependencias:** F2.3 (Sistema de Iteración), F1.x (todas las primitivas).

### 6.3 Validación del Builder

#### Tarea F2.5: Implementación de Code Review Automatizado

El sistema genera código que debe pasar validación de calidad. El code review automatizado debe verificar: sintaxis correcta, convenciones de código del framework, imports válidos, y adherence a las primitivas del framework.

**Entregable:** Módulo de code review automatizado y tests.

**Dependencias:** F2.4 (Compilador).

#### Tarea F2.6: Implementación de Generación de Tests

El constructor genera tests unitarios para el código creado. Los tests deben incluir: tests básicos de funcionalidad, mocks para dependencias externas, y fixtures para configuración.

**Entregable:** Módulo de generación de tests y tests generados para ejemplos.

**Dependencias:** F2.4 (Compilador), F2.5 (Code Review).

#### Tarea F2.7: Implementación de Type Checking

El código generado debe incluir type hints. El sistema debe verificar la consistencia de tipos mediante análisis estático o en tiempo de ejecución.

**Entregable:** Módulo de type checking y configuración.

**Dependencias:** F2.4 (Compilador).

### 6.4 Herramientas Custom

#### Tarea F2.8: Sistema de Creación de Herramientas Custom

El usuario puede crear herramientas personalizadas mediante descripción en lenguaje natural. El sistema genera la definición de la herramienta, la registra en el registry, y la hace disponible para uso.

**Entregable:** Módulo de creación de herramientas custom y examples.

**Dependencias:** F1.5 (Registry), F2.x (constructor).

### 6.5 Entregables de la Fase

Al concluir la Fase 2, se debe contar con: Intent Parser, Spec Generator, Sistema de Iteración, Compilador, Code Review Automatizado, Generación de Tests, Type Checking, y Sistema de Herramientas Custom.

### 6.6 Timeline de la Fase

La Fase 2 tiene una duración estimada de ocho semanas. Las tareas F2.1 a F2.4 (Constructor Core) occupy las semanas 1-5. Las tareas F2.5 a F2.7 (Validación) occupy las semanas 6-7. La tarea F2.8 (Herramientas Custom) ocupa la semana 8.

---

## 7. Fase 3: API y Observabilidad

### 7.1 Objetivos de la Fase

La Fase 3 tiene como objetivo implementar la capa de API REST y el sistema de observabilidad completo.

### 7.2 API REST

#### Tarea F3.1: Implementación de Endpoints REST

La API REST proporciona acceso programático al constructor y a los agentes generados. Los endpoints deben seguir las mejores prácticas de diseño de API RESTful con FastAPI.

Los endpoints principales incluyen: POST /builder/spec para crear especificación, POST /builder/compile para compilar especificación, POST /agent/{id}/execute para ejecutar agente, GET /agent/{id}/status para obtener estado, y POST /agent/{id}/cancel para cancelar ejecución.

Todos los endpoints deben soportar streaming mediante Server-Sent Events (SSE) para respuestas progresivas.

**Entregable:** Módulo FastAPI con endpoints documentados con OpenAPI.

**Dependencias:** F2.x (Constructor), F1.x (Pipeline).

#### Tarea F3.2: Implementación de Autenticación

Aunque la autenticación completa se implementa en fases posteriores, la estructura de autenticación se prepara en esta fase. El sistema utiliza Google OAuth más códigos de verificación (email verification, password reset) con password hashing mediante pgcrypto.

**Entregable:** Estructura de autenticación preparada (implementación posterom).

**Dependencias:** F3.1 (API).

### 7.3 Sistema de Observabilidad

#### Tarea F3.3: Implementación de Logging Estructurado

El logging estructurado registra cada operación con timestamp, user_id, operación, y resultado. Los logs se almacenan en la base de datos para consulta posterior.

**Entregable:** Módulo de logging y queries de consulta.

**Dependencias:** F1.x (Pipeline).

#### Tarea F3.4: Implementación de Métricas

Las métricas de usage se recolectan de cada llamada LLM: prompt_tokens, completion_tokens, total_tokens, y tiempo total. Métricas derivadas incluyen precision (cuando es aplicable), recall (cuando es aplicable), y costo estimado.

**Entregable:** Módulo de métricas y dashboard básico.

**Dependencias:** F1.11 (proveedores LLM).

#### Tarea F3.5: Implementación de Debug/Tracing

El sistema almacena información de debug en vector_store (colección debug) para trazabilidad completa de ejecuciones.

**Entregable:** Módulo de debug y herramientas de consulta.

**Dependencias:** F1.x (Pipeline).

### 7.4 Persistencia

#### Tarea F3.6: Implementación de DDL Automático

El sistema gestiona el schema de base de datos automáticamente, similar al sistema de referencia. El DDL automático crea tablas requeridas y aplica migraciones cuando es necesario.

**Entregable:** Scripts de DDL y módulo de migraciones.

**Dependencias:** Ninguna.

#### Tarea F3.7: Implementación de Almacenamiento de Agentes

Los agentes generados se almacenan en la base de datos (no en archivos locales). El almacenamiento incluye: definiciones de agentes, configuraciones, versiones, y history de ejecuciones.

**Entregable:** Módulo de persistencia de agentes.

**Dependencias:** F2.x (Constructor), F3.6 (DDL).

#### Tarea F3.8: Implementación de Versionado de Agentes

El sistema implementa versionado de agentes estilo git con versiones almacenadas en la base de datos. El versionado permite rollback a versiones anteriores y diff entre versiones.

**Entregable:** Módulo de versionado.

**Dependencias:** F3.7 (Almacenamiento).

### 7.5 Entregables de la Fase

Al concluir la Fase 3, se debe contar con: API REST completa, estructura de autenticación preparada, sistema de logging estructurado, sistema de métricas completo, sistema de debug/tracing, DDL automático, almacenamiento de agentes en DB, y versionado de agentes.

### 7.6 Timeline de la Fase

La Fase 3 tiene una duración estimada de seis semanas. Las tareas F3.1 a F3.2 (API) occupy las semanas 1-2. Las tareas F3.3 a F3.5 (Observabilidad) occupy las semanas 3-4. Las tareas F3.6 a F3.8 (Persistencia) occupation las semanas 5-6.

---

## 8. Fase 4: Herramientas y Templates

### 8.1 Objetivos de la Fase

La Fase 4 tiene como objetivo implementar las herramientas integradas básicas y los templates iniciales del framework.

### 8.2 Herramientas Integradas

#### Tarea F4.1: Implementación de Herramientas Básicas

Las herramientas básicas integradas proporcionan funcionalidad fundamental sin necesidad de que el usuario las defina. Las herramientas incluyen HTTP Tool (para requests externos), File System Tool (para lectura/escritura de archivos), Database Tool (para querying), y Web Search Tool (para búsquedas web).

**Entregable:** Módulo con herramientas básicas.

**Dependencias:** F1.2 (interfaz Tool).

### 8.3 Templates Iniciales

#### Tarea F4.2: Implementación de Templates

Los templates proporcionan puntos de partida comunes para diferentes tipos de agentes. La definición de templates específicos se realiza en conjunto con el agente product-manager, dado que los ejemplos de la arquitectura no aplican directamente al proyecto.

Los templates a definir incluyen: Research Agent (búsqueda y análisis), Support Agent (atención al cliente), y Analysis Agent (análisis de datos). Nota: El template "Outreach" de la arquitectura NO aplica al proyecto.

**Entregable:** Módulo con templates y documentación.

**Dependencias:** F1.x (framework).

### 8.4 Entregables de la Fase

Al concluir la Fase 4, se debe contar con: herramientas básicas integradas (HTTP, File, Database, Search) y templates iniciales (Research, Support, Analysis).

### 8.5 Timeline de la Fase

La Fase 4 tiene una duración estimada de cuatro semanas. Las tareas F4.1 y F4.2 se desarrollan en paralelo.

---

## 9. Fase 5: Seguridad y Calidad

### 9.1 Objetivos de la Fase

La Fase 5 tiene como objetivo implementar las medidas de seguridad y los sistemas de calidad restante.

### 9.2 Seguridad

#### Tarea F5.1: Implementación de Sanitización de Inputs

El constructor recibeprompts del usuario y los inyecta utilizando .format() (no concatenación directa) para prevenir prompt injections. Cualquier intento de inyección maliciosa detecteda debe resultar en terminación inmediata de la ejecución.

**Entregable:** Módulo de sanitización y políticas de seguridad.

**Dependencias:** F2.x (Constructor).

#### Tarea F5.2: Implementación de Rate Limiting

El sistema gestiona rate limiting de proveedores. El usuario puede configurar límites hasta un máximo global establecido por el sistema.

**Entregable:** Módulo de rate limiting.

**Dependencias:** F1.11 (proveedores LLM).

### 9.3 Configuración por Usuario

#### Tarea F5.3: Sistema de Configuración de Usuario

El sistema implementa user_settings para configuración por usuario, incluyendo: secrets (API keys, credenciales), context (templates,company info), y configuración de agentes.

**Entregable:** Módulo de configuración y tabla de base de datos.

**Dependencias:** F3.6 (DDL).

### 9.4 Entregables de la Fase

Al concluir la Fase 5, se debe contar con: sanitización de inputs, detección de inyecciones maliciosas, rate limiting, y sistema de configuración por usuario.

### 9.5 Timeline de la Fase

La Fase 5 tiene una duración estimada de cuatro semanas.

---

## 10. Fase 6: Distribución

### 10.1 Objetivos de la Fase

La Fase 6 tiene como objetivo preparar la distribución del framework.

### 10.2 Distribución

#### Tarea F6.1: Configuración de PyPI

El framework se empaqueta para distribución vía PyPI. El paquete incluye: código fuente, documentación, ejemplos, y setup.py/pyproject.toml configuración.

**Entregable:** Paquete PyPI configurado.

**Dependencias:** Todas las fases anteriores.

#### Tarea F6.2: Configuración de Docker

Disponibilidad de imagen Docker para ejecución en contenedores. La imagen incluye: todas las dependencias preinstaladas y configuración de ejemplo.

**Entregable:** Dockerfile y imagen configurada.

**Dependencias:** Todas las fases anteriores.

#### Tarea F6.3: Gestión de Dependencias

El framework utiliza virtual environment con requirements.txt. El formato de requirements incluye version pinning para reproducibilidad.

**Entregable:** requirements.txt y documentación de setup.

**Dependencias:** F0.3 (decisiones tecnológicas).

### 10.4 Entregables de la Fase

Al concluir la Fase 6, se debe contar con: paquete PyPI configurado, imagen Docker, y gestión de dependencias documentada.

### 10.5 Timeline de la Fase

La Fase 6 tiene una duración estimada de tres semanas.

---

## 11. Resumen de Fases y Timeline

### 11.1 Duración Total

| Fase | Descripción | Duración |
|------|-----------|----------|
| F0 | Investigación Preliminar | 2 semanas |
| F1 | Foundation | 6 semanas |
| F2 | Constructor Conversacional | 8 semanas |
| F3 | API y Observabilidad | 6 semanas |
| F4 | Herramientas y Templates | 4 semanas |
| F5 | Seguridad y Calidad | 4 semanas |
| F6 | Distribución | 3 semanas |
| **Total** | | **33 semanas** |

### 11.2 Resumen de Dependencias Críticas

| De | A | Dependencia |
|----|---|-----------|
| F0.1 | F1.3 | Proveedor de vector store |
| F0.2 | F1.6-1.10 | Patrones del orquestador |
| F0.3 | F1.x | Decisiones tecnológicas |
| F1.x | F2.x | Primitivas para Constructor |
| F1.11 | F2.1-2.3 | Proveedores para Constructor |
| F2.x | F3.1 | Constructor para API |
| F1.x | F3.x | Primitivas para API |
| F2.4 | F3.7 | Compilador para persistencia |
| F2.5-2.7 | F4.x | Validación para tools |
| F5.x | F6.x | Seguridad para distribución |

---

## 12. Áreas que Requieren Iteración con Agentes

Algunas áreas del desarrollo requieren iteración con agentes especializados para definición detallada. Estas áreas están identificadas en las tareas correspondientes pero se elaboran completamente durante la ejecución.

### 12.1 Agente ai-architect

El agente ai-architect se utiliza para: definición detallada de primitivas del framework, evaluación de tecnologías específicas, diseño de arquitectura de componentes complejos, y resolución de problemas técnicos de implementación.

### 12.2 Agente product-manager

El agente product-manager se utiliza para: definición de templates específicos del proyecto, flujos de UX del constructor, y priorización de features.

### 12.3 Agente code-reviewer

El agente code-reviewer se utiliza para: validación de código generado, identificación de issues de calidad, y recomendaciones de mejora.

### 12.4 Agente qa

El agente qa se utiliza para: diseño de tests, validación de coverage, y definición de criterios de aceptación.

---

## 13. Criterios de Éxito del MVP

El MVP de synapseForge se considera completo cuando cumple los siguientes criterios:

1. El usuario puede describir un agente en lenguaje natural y recibe una especificación técnica.
2. El usuario puede iterar sobre la especificación hasta obtener aprobación.
3. El sistema compila código Python ejecutable a partir de la especificación aprobada.
4. El código generado pasa los tests unitarios generados automáticamente.
5. El agente generado ejecuta correctamente mediante la API REST.
6. El streaming de respuestas funciona correctamente.
7. El estado se persiste en base de datos entre ejecuciones.
8. Los errores se manejan sin interrumpir el flujo (el usuario nunca recibe una excepción).
9. El logging y métricas de usage se registran correctamente.
10. El código generado sigue las primitivas del framework (sin dependencias externas).

---

## 14. Consideraciones de Implementación

### 14.1 Manejo de Errores

El principio fundamental del manejo de errores es que el orquestador nunca lanza excepciones al usuario. Cuando una herramienta falla, el sistema intenta retry automático (3 intentos con backoff exponencial). Si continúa fallando, el sistema reporta el error al usuario de manera amigable y permite continuar con otras operaciones.

### 14.2 Contrato de Herramientas

Todas las herramientas (construidas por el constructor o integradas)deben respetar estrictamente el contrato: `{status, message, data, usage}`. No existen excepciones a esta regla.

### 14.3 Multi-tenancy

El aislamiento entre usuarios es obligatorio desde el inicio. El user_id filtra toda la información accesible, sin excepciones.

### 14.4 Persistencia

Toda la información relevante se persiste en base de datos. No se utiliza almacenamiento en archivos locales para datos principales (solo para logs temporales o archivos de debugging).

### 14.5 Testing

El constructor genera tests unitarios para el código creado. Adicionalmente, el sistema mantiene un conjunto de tests de integración para el pipeline completo y todos los componentes del framework.

---

*Documento generado: Mayo 2026*
*Versión: 1.0*
*Tipo: Plan de Desarrollo*