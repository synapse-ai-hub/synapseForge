Generá una skill para synapseForge en formato SKILL.md.

## Estructura

### 1. Frontmatter YAML (entre ---)

Sin comillas en los valores salvo que sea estrictamente necesario.

- name: nombre corto con guiones (ej: analisis-competencia)
- description: máximo 2-3 oraciones. Incluye para qué sirve, cuándo se usa y cuándo NO. BREVE.
- metadata.triggers: palabras clave separadas por comas

Formato:

```
---
name: <nombre>
description: <descripción breve, 2-3 oraciones>
metadata:
  triggers: <palabras clave>
---
```

### 2. Cuerpo markdown

- # <Nombre de la Skill>
- ## Core Workflow (pasos detallados)
- ## Constraints (lo que NO debe hacer)

### 3. Estilo

Instructivo, directo, concreto.

## Datos

Tarea: {tarea}
Nombre sugerido: {nombre}
Cuándo se usa: {triggers}
Cuándo NO se usa: {no_triggers}
Material de referencia: {refs}

## Salida

SOLO el contenido del archivo SKILL.md. Sin texto adicional.
