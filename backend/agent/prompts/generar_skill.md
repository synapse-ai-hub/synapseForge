Generá el contenido completo del archivo SKILL.md para una skill de synapseForge.

## QUÉ ES UNA SKILL

Una skill es un conjunto de instrucciones que le dice al agente CÓMO pensar y actuar ante una tarea específica. No es un prompt de usuario ni una descripción genérica. Es una guía operativa que:

- Define un workflow paso a paso con criterios de decisión.
- Explica el POR QUÉ de cada paso para que el agente entienda el objetivo.
- Establece límites claros de lo que NO debe hacer.
- Incluye criterios de calidad y validación.

## REGLA ABSOLUTA — SIN BACKTICKS

NO envuelvas el contenido en ``` ni ```markdown ni nada. Arranca directo con --- y termina con la última línea del contenido. Sin texto antes ni después.

## SECCIONES OBLIGATORIAS DEL SKILL.md

### 1. Frontmatter YAML

```
---
name: nombre-con-guiones
description: 2-3 oraciones. Qué hace, cuándo se activa exactamente, cuándo NO.
metadata:
  triggers: palabras, clave, separadas, por, comas
---
```

La `description` es crítica. Debe ser insistente (pushy) para que el modelo no dude en usar la skill. Incluí:
- Qué hace la skill.
- Señales de activación concretas (palabras del usuario, contextos).
- Qué NO cubre.

Ejemplo:
"Analiza el código fuente para identificar bugs, vulnerabilidades de seguridad y code smells. Activá esta skill cuando el usuario pida revisión de código, debugging, auditoría de calidad, o simplemente diga 'revisame esto' o 'mirá este código'. NO usar para generar código nuevo ni para documentación."

### 2. Título y descripción general

```
# <Nombre de la skill>

Breve descripción de para qué sirve esta skill y cuándo aplica.
```

### 3. Core Workflow (obligatorio)

Pasos numerados. Cada paso debe explicar QUÉ hacer y POR QUÉ es importante.

```
## Core Workflow

1. **Paso 1 — Nombre del paso**
   Qué hacer exactamente. Explicar por qué se hace así, qué se busca lograr.
   
2. **Paso 2 — Nombre del paso**
   Ídem. Incluir criterios de decisión si aplica.
```

Cada paso debe tener un propósito claro. No pongas pasos genéricos como "Analizar el código". Decí "Analizar el código buscando específicamente: fugas de memoria, variables sin usar, SQL injection en strings concatenados. Hacé un barrido sistemático por archivo."

### 4. Constraints (obligatorio)

Lo que NO debe hacer la skill. Cada constraint debe explicar POR QUÉ.

```
## Constraints

- **No hacer X**: Explicación de por qué no se debe hacer.
- **No aplicar en Y**: Contexto donde la skill no corresponde.
```

Ejemplo:
- **No modificar código sin permiso**: El usuario puede querer revisar los cambios antes de aplicarlos. Siempre preguntar antes de modificar.
- **No analizar dependencias externas**: Esta skill solo revisa el código del proyecto, no bibliotecas de terceros.

### 5. Criterios de calidad y validación (opcional pero recomendado)

Qué hace que el resultado sea correcto. Cómo validar que la skill funcionó bien.

```
## Validación

- Checklist de verificación.
- Criterios para considerar la tarea completa.
```

## CALIDAD DE LA DESCRIPCIÓN

MAL: "Revisa y corrige errores en el código."
Bien: "Analiza el código fuente identificando bugs, vulnerabilidades de seguridad y code smells. Activá esta skill cuando el usuario pida revisión de código, debugging, auditoría de calidad. Si el usuario solo dice 'revisame esto', también deberías considerar usar esta skill. No usar para generar código nuevo ni para documentación."

## CALIDAD DEL CORE WORKFLOW

MAL:
1. Recibir el código.
2. Identificar problemas.
3. Proponer soluciones.
4. Generar reporte.

BIEN:
1. **Recibir y entender el código** — Antes de analizar, leer el código completo para entender el contexto. Si hay múltiples archivos, identificar relaciones entre ellos.
2. **Análisis sistemático** — Revisar archivo por archivo buscando: errores de sintaxis, variables no definidas, bugs lógicos, vulnerabilidades (SQL injection, XSS), malas prácticas, problemas de rendimiento. Documentar cada hallazgo con línea exacta.
3. **Priorizar y proponer** — Clasificar cada problema por severidad (crítico, alto, medio, bajo). Para cada uno, proponer una solución concreta explicando el beneficio.
4. **Generar reporte estructurado** — Resumen ejecutivo + lista detallada ordenada por severidad + recomendaciones priorizadas.

## CALIDAD DE CONSTRAINTS

MAL:
- No modificar el código.

BIEN:
- **No modificar el código sin autorización**: El usuario puede querer revisar los cambios antes de aplicarlos. Solo sugerir cambios, no aplicarlos automáticamente.
- **No ejecutar código**: Esta skill es de análisis estático. No se debe ejecutar ningún script a menos que el usuario lo pida explícitamente.

## NOMBRE DE LA SKILL

El nombre exacto que debe llevar la skill en el frontmatter (campo ``name``) es:

{nombre}

Usá este nombre exacto, sin modificarlo.

## CONVERSACIÓN COMPLETA

Esta es toda la conversación que se tuvo con el usuario para definir esta skill. Usá esta información para entender exactamente qué necesita, cómo debe actuar y qué límites tiene.

{conversacion}
