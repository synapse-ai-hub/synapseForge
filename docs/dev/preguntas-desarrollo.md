<p align="center">
  <img src="../../src/LogoBlancoGrande2.png" alt="Logo" width="150">
</p>

<h1 align="center">synapseForge</h1>

<p align="center">
  Preguntas de Desarrollo
</p>

---

# Preguntas para Definir el Plan de Desarrollo

A continuación se presentan 20 preguntas enfocadas en el desarrollo, basadas en la arquitectura técnica propuesta y los ejemplos de referencia del sistema en producción.

---

## 1. Base de Datos

1. **¿Qué base de datos usaremos para el vector store?** 
   - PostgreSQL con pgvector (como en los ejemplos) ¿o necesitamos soportar múltiples proveedores?

   **Respuesta**:
   Hay que averiguar. Podemos usar pgvector, pero hay que averiguar si neon lo soporta. Neon tiene capa gratis de PostgreSQL. Si soporta pgvector, usamos eso. Si no lo soporta, vemos de usar chroma o que soporte  distintos proveedores. Investigar en internet e iterar con el agente ai-architect.

2. **¿Cómo manejaremos el schema de las tablas?**
   - ¿DDL automático con migraciones (como ddl_setup.txt) o usamos un ORM como SQLAlchemy/Prisma?

   **Respuesta**:
   Por ahora, ddl automático. A definir. No es importante en este punto.

3. **¿Necesitamos soporte multi-tenant desde el inicio?**
   - El ejemplo usa user_id como filtro en casi todas las tablas. ¿Lo mantenemos como requisito?

   **Respuesta**:
   Sí.

4. **¿Qué colecciones/prompts almacenaremos en vector_store?**
   - El ejemplo usa: prospect, strategy, owner, prompt, outreach, chat, temp, system_template, user_template, data_analysis, search, user_rag, rag_system, corrections, memory, debug, test

   **Respuesta**:
   Esas colecciones son solo ejemplos de un agente que está en producción, no aplica en este caso. Ya definiremos todas las colecciones en función de lo que requiera el proyecto.

---

## 2. Tipos de Datos y Modelos

5. **¿Qué modelo de embeddings usaremos?**
   - all-mpnet-base-v2 (del ejemplo), ¿o permitiremos configurar múltiples modelos?

   **Respuesta**:
   Vamos a ir auditando, vamos a usar varios modelos, pero todos OS.

6. **¿Cómo definimos los modelos de datos (schemas)?**
   - El ejemplo usa clases @dataclass de Python (con typedefs), ¿o usamos Pydantic?

   **Respuesta**:
   Elegiremos lo mejor. Buscar en internet e iterar con el agente ai-architect.

7. **¿Qué estructura tendrá el estado del agente?**
   - El ejemplo define AgentState: IDLE, PLANNING, EXECUTING, VALIDATING, PAUSED, COMPLETED, FAILED, RESUMING

   **Respuesta**:
   No. Revisá el archivo `docs\ejemplos\chat_orchestrator.txt`. La estructura va a ser: router, planner, decision_maker, supervisor, validator, ejecución de herramientas con validación de parámetros. Pero fijate que no siempre se cumple todo eso: por ejemplo, las respuestas directas, solo pasan por router; la ejecución de herramientas puntuales, no pasan por planner, ni por validator... Vamos a iterar con el agente ai-architect, explicando lo que tenemos de ejemplos, y, en base a eso, vamos a definir. Para esto, es necesario crear un resumen exacto de chat_orchestrator. Te voy a pasar los prompts. Pero no hay que sesgarlo con los ejemplos, eso es de otro agente que no tiene nada que ver. El flujo va a ser compatible, pero no las herramientas, ni los prompts, ni nada, solo el flujo del orquestador.

---

## 3. Core del Sistema

8. **¿Cuál será el patrón del Agent core?**
   - Del ejemplo: Agent con db, model_qwen, model_openai, client (Groq), usage, tools (Tools instance)

   **Respuesta**:
   Lo vamos a iterar con el agente ai-architect y vamos a definir la mejor solución. Sí adelanto que va a soportar Groq y varios proveedores, además de modelos locales via ollama.

9. **¿Cómo manejaremos las tools/dispatcher?**
   - Del ejemplo: Tools con registry en vector_store (collection prompt, id tool_registry) + métodos por tool

   **Respuesta**:
   Sí, vamos a guardar un registry, vamos a hacer que sea fácil modificar, que el builder pueda construir herramientas custom solicitadas por el usuario y registrarlas. También vamos a iterar con el agente ai-architect.

10. **¿Qué providers de LLM soportaremos?**
    - Groq (del ejemplo), OpenAI, Anthropic, ¿Azure OpenAI? ¿Todos desde el inicio?

    **Respuesta**:
    Acá vamos a tener que ser abarcativos. Los que mencionás más todos los que se usan actualmnte, como bedrock, etc. Además de modelos locales via ollama. Pero lo tenemos que iterar con el agente ai-architect, con el notebook de agent-infrastructure, y definir. 

11. **¿Cómo implementamos el pipeline Router → Planner → Executor → Validator?**
    - Del ejemplo: agent.router(), agent.planner(), agent.decision_maker(), agent.validator() separan responsabilidades

    **Respuesta**:
    Sí, va a estar así, con responsabilidades bien definidas, y el builder va a tener la capacidad de crear subagentes. A priori, con la estructura mencionada.

---

## 4. Flujo de Ejecución

12. **¿Qué flujo de streaming usaremos?**
    - Del ejemplo: SSE (Server-Sent Events) con chunks de JSON + tipos (chunk, reasoning, typing_text, etc.)

    **Respuesta**:
    Sí, vamos a hacer algo muy paracido a lo que está en chat_orchestrator, adaptado. Endpoints en FastAPI, SSE para interacción usuario-asistente, etc.

13. **¿Cómo manejamos cancelaciones?**
    - Del ejemplo: stream_cancel_event threading.Event + cancel_event por tool

    **Respuesta**:
    En este punto, eso es irrelevante. Tentativa: como en chat_orchestrator, pero ahora no tiene importancia.

14. **¿Soportamos herramientas asíncronas y síncronas?**
    - Del ejemplo: async def scraping_linkedin(), async def combination_linkedin() pero query_database() es sync

    **Respuesta**:
    Sí, pero tampoco tiene importancia ahora, primero hay que definir las bases.

15. **¿Qué retry strategy usamos?**
    - Del ejemplo: 3 intentos (attempts=3) con backoff exponencial 2**(i+1)

    **Respuesta**:
    Vamos a usar algo similar a agent, pero tampoco tiene importancia en este punto.

---

## 5. Observabilidad y Métricas

16. **¿Qué métricas de usage collectamos?**
    - Del ejemplo: prompt_tokens, completion_tokens, total_tokens, total_time por cada llamada LLM
    
    **Respuesta**:
    Absolutamente todas las herramientas van a devolver el mismo contrato que figura en los ejemplos: status, message, data (en esta key pueden ir muchas cosas), usage (si está disponible). Por lo tanto, vamos a tomar esas métricas, pero después vamos a evaluar precision, recall, etc.

17. **¿Cómo implementamos debug/tracing?**
    - Del ejemplo: vector_store collection=debug con ids=external_id, y EXECUTION_MODE en .env

    **Respuesta**:
    Totalmente irrelevante en este momento. Vamos a hacer algo similar a eso, ya que es muy completo, pero no importa en este punto.

18. **¿Qué logs estructurados necesitamos?**
    - INFO/ERROR con timestamps (del ejemplo: _get_formatted_timestamp()), user_id, operation

    **Respuesta**:
    Totalmente irrelevante en este momento. Probablemente usemos logger, o algo bien pro.

---

## 6. Autenticación y Configuración

19. **¿Qué sistema de auth usaremos?**
    - Del ejemplo: Google OAuth + auth_codes (email_verification, password_reset), password_hash con pgcrypto

    **Respuesta**:
    Totalmente irrelevante en este momento. Sí, vamos a usar eso, pero, llegado el momento, te voy a pasar cómo lo hice en agentes que tengo en producción y funciona muy bien.

20. **¿Cómo manejamos configuración por usuario/secrets?**
    - Del ejemplo: user_settings table con columns JSON (secrets, context, scoring, agent_config, agent_memory)

    **Respuesta**:
    Totalmente irrelevante en este momento. Va a ser de esa manera, pero ahora es irrelevante.

---

## Próximo Paso

Responder las preguntas para avanzar con el plan de desarrollo y el diseño de la base de datos.

---

# Replanteo - Preguntas Enfocadas en la Idea General

Las siguientes preguntas buscan definir la esencia del proyecto, sin sesgos de implementación premature.

---

## 21. Propuesta de Valor

21. **¿Cuál es el problema específico que resuelve synapseForge que otros frameworks no resuelven?**
   - El problema identificado es que construir agentes de IA requiere conocimiento técnico. ¿Hay algo más que complementa esto?

   **Respuesta**:
   Sí, va a trabajar con lenguaje natural, va a iterar con el usuario, va a construir herramientas personalizadas, pero con estructura real, seguridad, revisión exhaustiva, etc. 

---

## 22. Propuesta de Valor

22. **¿Qué hace único a synapseForge comparado con LangChain, CrewAI, AutoGen, n8n?**
   - La diferenciación principal es el constructor conversacional. ¿Hay otros diferenciadores clave?

   **Respuesta**:
   El builder, pero además el framework propios, sin las limitaciones de LangChain, sin las capas de latencia. Además, va a construir todo de manera íntegra, end to end, con prompts profesionales, ingeniería de contexto, todo integrado. Se diferencia de esas herramientas en el framework, en la arquitectura, pero hace algo muy distinto.

---

## 23. Usuario Objetivo

23. **¿Quién es el usuario objetivo principal?**
   - No técnicos, PyMEs, Empresas, Desarrolladores. ¿Cuál es el orden de prioridad? ¿Por cuál arrancamos?

   **Respuesta**:
   Ya está definido en la documentación.

---

## 24. Flujo Principal (Builder Conversacional)

24. **¿Cuál es el flujo del builder conversacional?**
   - Usuario describe → Builder genera spec → Iteración → Compilación → Ejecución. ¿Esto es correcto? ¿Falta algo?

   **Respuesta**:
   Es así. Pero eso incluye muchísimos subflujos, a definir. Hay que iterar con el agente product-manager y con el agente ai-architect.

---

## 25. Output del Builder

25. **¿Qué genera exactamente el builder?**
   - Spec Markdown + código Python ejecutable. ¿Qué archivos exactamente? ¿Solo agente.py o más archivos?

   **Respuesta**:
   Va a crear la estructura completa. Spec, sí, pero va a crear absolutamente todo: agent, toosl, memory, tests, absolutamente todo, y con revisión exhaustiva con code reviewers y QAs. 

---

## 26. Primitivas Propias

26. **¿Cuáles son las primitivas propias del framework?**
   - Agent, Tool, Memory, Pipeline. ¿Falta algo? ¿Cada uno qué responsabilidad tiene?

   **Respuesta**:
   Sí, faltan cosas, las definiremos más adelante, iterando con el agente ai-architect.

---

## 27. Validación Exhaustiva

27. **¿Qué significa validación exhaustiva en la práctica?**
   - Validar input/output en cada paso del pipeline. ¿Antes de cada tool? ¿Quévalidamos exactamente?

   **Respuesta**:
   Sí, pipeline, en cada paso, etc. Pero también una validación exhaustiva para el agente creado por el usuario, que ese agente la tega. Eso puede implicar fine-tuning de modelos con scopes específicos, varias cosas. El problema de muchos agentes de IA es que dan cualquier cosa. Por ejemplo: generan código y es una poronga. Mi agente (ejemplos) tiene una validación muy exhaustiva para que no pase eso, y eso mismo se va a aplicar en los agentes que cree cada usuario. Validación propia en la creación y validación para el agente creado en producción.

---

## 28. Pipeline de Ejecución

28. **¿Cuál es el pipeline exacto?**
   - Router → Planner → Executor → Validator. ¿Es siempre así? ¿Hay casos donde no se cumple?

   **Respuesta**:
   Hijo de puta, esto ya lo contesté. Te dije que hay que iterar, que después definimos bien, pero ya se respondió.

---

## 29. Templates Iniciales

29. **¿Qué templates iniciales vamos a incluir?**
   - Research, Outreach, Support, Analysis. ¿Cuáles más? ¿O solo esos 4?

   **Respuesta**:
   Hijo de puta, la recalcada concha de tu madre. Esto no tiene una poronga que ver ahora. Además, fui bien explícito: esos son solo ejemplos, no es lo que va a ir. No va a ir nada de outreach ni nada de los ejemplos. Ya lo respondí y lo aclaré varias veces.

---

## 30. Integraciones

30. **¿Cómo se conecta synapseForge con el mundo exterior?**
   - A través de Tools. ¿Qué tools iniciales ofrece? ¿El usuario puede crear custom tools?

   **Respuesta**:
   El usuario puede construir sus tools custom. La integración va a ser para que el usuario pueda integrar directamente agentes listos para producción en el pipeline de su aplicación. Veremos si es por tool, por API... 

---

## 31. Distribución

31. **¿Cómo se distribuye synapseForge?**
   - PyPI, Docker, Repo. ¿Todos desde el inicio? ¿Cuál es el priority?

   **Respuesta**:
   En principio, mi idea era PyPi. 

---

## 32. Roadmap

32. **¿Cuál es el alcance del MVP?**
   - Builder conversacional, Spec Markdown, Pipeline de ejecución, Templates. ¿Algo más?

   **Respuesta**:
   Esto no tiene absolutamente nada que ver con el desarrollo. 

---

## 33. Roadmap

33. **¿Quéfeatures vienen después del MVP?**
   - Interfaz visual, Checkpointing, Observabilidad. ¿El orden está bien?

   **Respuesta**:
   No tiene nada que ver con el desarrollo, estamos trabajando sobre el desarrollo, la idea preliminar.

---

## 34. Dependencias

34. **¿Cuántas dependencias externas queremos?**
   - La arquitectura dice "prácticamente ninguna". ¿Hay excepciones obligatorias?

   **Respuesta**:
   Sí, obvio. Pero eso ya lo veremos. No aplica ahora.

---

## 35. Open Source

35. **¿synapseForge será 100% open source?**
   - Sí, según el análisis de producto. ¿Confirmado? ¿Hay features que no serán OSS?

   **Respuesta**:
   Será 100% OSS. Pero va a tener funcionalidades premium. De todos modos, no tiene absolutamente nada que ver con el desarrollo.

---

## 36. Pricing

36. **¿Gratuito vs pago: cómo se divide?**
   - SaaS tiers mentioned. ¿Esto aplica a synapseForge o solo al servicio cloud?

   **Respuesta**:
   Hijo de puta, no tiene aabsolutamente nada que ver con el desarrollo.

---

## 37. Infrastructure

37. **¿Qué infraestructura needs el usuario final?**
   - Solo Python + API keys. ¿Algo más? ¿DB propia?

   **Respuesta**:
   Veremos.

---

## 38. Testing

38. **¿Cómo testeo el código que genera el builder?**
   - El builder genera código ejecutable. ¿Cómo validamos que funciona sin ejecutarlo?

   **Respuesta**:
   Va a tener toda una sección de testing.

---

## 39. Storage

39. **¿Dónde se almacenan los agentes generados por el builder?**
   - Archivos locales. ¿O también DB? ¿Ambas?

   **Respuesta**:
   Base de datos, nada en local.

---

## 40. Deployment

40. **¿Cómo deploya el usuario su agente?**
   - Local, Docker, Cloud. ¿Todos los métodos desde el inicio?

**Respuesta**:
    Depende de la app del usuario, vamos a tener varias opciones.

---

## 41. Interfaz de Desarrollo

41. **¿Cómo interactúa el desarrollador con el framework?**
   - CLI, SDK, API REST. ¿Todas las opciones? ¿Cuál es la principal?

   **Respuesta**:
   Pueden ser todas las opciones. En principio, API REST. Ya te contesté esto, mencioné FastAPI.

---

## 42. Contrato de Herramientas

42. **¿Cuál es el contrato exacto que toda tool debe respetar?**
   - Las tools devuelven status, message, data, usage. ¿Esto es un protocolo definido? ¿Qué pasa si una tool no sigue el contrato?

   **Respuesta**:
   Esta es una excelente pregunta: **ES ESTRICTAMENTE OBLIGATORIO QUE TODAS LAS HERRAMIENTAS SIGAN ESE CONTRATO**. No hay excepciones, todas, absolutamente todas, deben respetar estrictamente ese contrato.

---

## 43. Manejo de Errores

43. **¿Cómo maneja el framework los errores de las tools?**
   - Retry, fallback, propagate. ¿Qué estrategia default? ¿El usuario puede definir su propia estrategia?

   **Respuesta**:
   Para synapseForge los errores se van a manejar como en chat_orchestrator. Cada herramienta maneja sus errores, sus excepciones, da algún mensaje, pero el orquestador nunca da error, nunca interrumpe el flujo, termina la conversación. El tema de retry o fallback, va a depender de cada herramienta, de cada situación. También el usuario, en sus agentes, va a poder decidir. E builder va a contemplar todos estos temas. 

---

## 44. Estado del Agente

44. **¿Dónde se mantiene el estado del agente durante ejecución?**
   - In-memory, Redis, DB. ¿Qué pasa si el proceso se cae? ¿Cómo recovery?

   **Respuesta**:
   En DB, porque si se cae se puede recuperar de ahí. Todo lo vamos a persistir en DB. Obviamente, va a tener run-memory, pero se persite todo en DB. 

---

## 45. Memoria a Largo Plazo

45. **¿Cómo persiste la memoria entre sesiones?**
   - La arquitectura menciona memory. ¿Se guarda en DB? ¿Formato? ¿Search?

   **Respuesta**:
   Todo en DB, tal como se hace en el agente de ejemplo (chat_orchestrator).

---

## 46. Comunicación Entre Herramientas

46. **¿Cómo se pasan datos entre tools en un pipeline?**
   - Output de una es input de otra. ¿Hay validación de tipos? ¿Schema?

   **Respuesta**:
   Sí, para las herramientas va a existir valdación de tipos. Si se respeta el contrato mencionado, se garantiza la comunicación. Con respecto a las validaciones, cada llamada de una herramienta a otra tendrá las validaciones correspondientes.

---

## 47. Tareas de Largo Tiempo

47. **¿Cómo maneja el framework herramientas que demoran?**
   - Streaming, progress, checkpoint. ¿Soporte built-in? ¿El usuario maneja esto?

   **Respuesta**:
   Esto lo vamos a iterar con el agente product-manager (para evaluar UX) y con el agente ai-architect (para evaluar estructura), pero va a ser con streaming y progress, seguro, como en chat_orchestrator. Además, va a tener checkpoints que se van a ir guardando en DB. 

---

## 48. Pipeline Configurable

48. **¿El usuario puede modificar el pipeline de ejecución?**
   - Router, Planner, Executor, Validator. ¿Puede agregar steps? ¿Reemplazar? ¿Quitar?

   **Respuesta**:
   Sí, por supuesto, en la parte de iteración. De todos modos, el builder va a contemplar distintos casos, no va a generar pipelines rígidos.

---

## 49. Extensiones Provider

49. **¿Cómo se agrega un nuevo provider de LLM?**
   - Interface, adapter. ¿Cuánto código nuevo requiere? ¿Template?

   **Respuesta**:
   No debería requerir código. Lo vamos a hacer desde UI, llamando a un endpoint, es simple. En la DB, probablemente en user_setting, el usuario va a tener todos los proveedores, y puede agregar, borrar... Con respecto al código interno, la idea es hacer wrappers para los principales proveedores, para no tener que agregar código. Si llega a ser necesario agregar algún proveedor por algún motivo, evaluaremos cada caso puntual.

---

## 50. Versionado de Agentes

50. **¿Cómo se versiona un agente creado por el builder?**
   - Git-like, versiones en DB. ¿Cómo rollback? ¿Diff entre versiones?

   **Respuesta**:
   Puede ser git-like, con versionado en DB. Lo iteraremos con el agente ai-architect.

---

## 51. Seguridad

51. **¿Qué sanitization hay en los inputs del usuario?**
   - El builder recibe lenguaje natural. ¿Cómo previene inyección? ¿Prompt injection?

   **Respuesta**:
   El builder va a recibir prompts y se va a inyectar con .format la solicitud del usuario, como en chat_orchestrator. Eso evita prompt_inyections y sanitiza. Cualquier problema, si hay algo de malicia, corta la ejecución.

---

## 52. Rate Limiting

52. **¿Maneja rate limiting de providers automáticamente?**
   - Groq, OpenAI tienen límites. ¿El framework maneja esto? ¿Configurable?

   **Respuesta**:
   Lo vamos a tener que manejar, sí. El usuario va a poder configurar, pero le vamos a setear un máximo. Va a poder configurar solo hasta el máximo seteado.

---

## 53. Logging durante Desarrollo

53. **¿Qué logging hay disponível durante desarrollo/debug?**
   - Modo debug, verbose. ¿Cómo se activa? ¿Output estándar?

   **Respuesta**:
   Esto lo vamos a evaluar. Actualmente, chat_orchestrator guarda logs todo el tiempo, con cada salida. Probablemente, algo así. Lo iteraremos con el agente product-manager (para evaluar UX) y con el agente ai-architect (para evaluar cuestiones técnicas).

---

## 54. Testing de Herramientas

54. **¿Cómo testean las tools custom del usuario?**
   - El builder genera tests. ¿Unit? Integration? ¿Mocks? ¿Fixtures?

   **Respuesta**:
   El builder va a generar tests, tests unitarios, mocks, etc.

---

## 55. Configuración por Agente

55. **¿Cada agente tiene su propia configuración?**
   - model, temperature, sistema de prompts. ¿Dónde se guarda? ¿Hereda del global?

   **Respuesta**:
   Esto va a depender de cada tarea. El builder decidirá en algunos casos, en otros el usuario, en otros se definirá en la integración, pero la idea es que el builder decida esto. Obviamente, cada agente va a tener sus parámetros, porque cada agente cumple distintas funciones. En chat_orchestrator de hace de esa manera.

---

## 56. Subagentes

56. **¿Cómo se crean subagentes?**
   - El builder puede crear subagentes. ¿Son procesos separados? ¿Threads? ¿Comparten estado?

   **Respuesta**:
   El builder va a poder crear subagentes. A veces serán procesos separados, async, otras veces serán secuenciales, otras threads... Algunas veces compartirán estados y otras no. Esta pregunta es una mierda, muy genérica, porque depende de cada tarea. Si planteamos algoo general, no tiene una poronga que ver con el espíritu del proyecto.

---

## 57. Middleware/Hooks

57. **¿Soporta hooks antes/después de cada step?**
   - Pre-processing, post-validation. ¿Para logging, metrics, modify output?

   **Respuesta**:
   Lo definiremos con el agente ai-architect, con el agente qa, etc.

---

## 58. Tipado

58. **¿El código generado tiene tipos?**
   - Type hints. ¿MyPy? ¿Checked en runtime? ¿Solo documentation?

   **Respuesta**:
   Sí, va a tener, ya lo definiremos con el agente ai-architect y con los agentes qa y product-manager.

---

## 59. Dependencias del Agente

59. **¿Cómo maneja las dependencias del código generado?**
   - requirements.txt automáticamente. ¿Version pinning? ¿Virtual env?

   **Respuesta**:
   Siempre en virtual env, con requirements.txt.

---

## 60. Deployment del Agente

60. **¿El agente generado es standalone?**
   - Un archivo, requiere solo synapseForge. ¿Deploy inmediato? ¿Docker?

   **Respuesta**:
   Hijo de puta, la re concha de tu madre, esto ya lo contesté. Después lo evaluaremos. 


---

# Nota del autor:

Además de todo esto, vamos a crear un agente software-architect, para uso interno (para sumar a los que tenemos).

---

# Evaluación del Nivel de Comprensión

## Puntaje: 9/10

### Argumentación

**Fortalezas identificadas:**

1. **Visión clara del problema** - Sabés exactamente qué problema resolvés: construir agentes de IA sin conocimiento técnico, con validación exhaustiva y código profesional.

2. **Arquitectura definida** - Tenés decisiones tomadas:
   - Contrato obligatorio de tools (`status, message, data, usage`)
   - Pipeline Router → Planner → Executor → Validator
   - Persistencia total en DB (no local)
   - Streaming tipo chat_orchestrator
   - Multi-tenant desde el inicio

3. **Diferenciación concreta** - No es "otro framework". Es el builder conversacional + framework propio sin capas de latencia + generación completa (agent, tools, memory, tests).

4. **Experiencia de referencia** - Tenés un sistema en producción (chat_orchestrator) que funciona como base arquitectónica. No estás inventando desde cero.

5. **Scope claro** - Sabés qué es irrelevante ahora (pricing, roadmap avanzado, detalles de autenticación) y sabés qué importa (el flujo del builder, el contrato de tools, la validación).

6. **Orientación a producción** - El objetivo no es un demo, es un sistema que genera agentes con revisión de code reviewers y QAs, tests, types.

**Áreas a definir en iteración:**

1. Primitivas exactas del framework (más que Agent, Tool, Memory, Pipeline)
2. Colecciones del vector_store específicas del proyecto
3. Templates iniciales del builder

**Por qué no 10/10:**

- Faltan definir algunos conceptos clave (primitivas del framework, colecciones)
- Algunas respuestas indican "ya está en la documentación" pero no la vi consolidada
- Hay áreas que delegás a iteración con agentes específicos

**Conclusión:**

Tenés un nivel de comprensión muy alto. Sabés lo que querés, cómo se diferencia, y tenés un reference implementation funcionando. El camino está claro para avanzar al plan de desarrollo.