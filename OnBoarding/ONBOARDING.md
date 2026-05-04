<p align="center">
  <img src="../src/LogoBlancoGrande2.png" alt="Logo de synapse.ai" width="80">
</p>

---

# Onboarding rápido

Bienvenido/a al proyecto `synapseForge`. Estos son los pasos mínimos para dejar tu entorno listo y comenzar a contribuir.

---

## 1. Clonar el repositorio

```bash
>>> git clone https://github.com/synapse-ai-hub/synapseForge.git
>>> cd synapseForge
```

---

## 2. Instalar dependencias

```bash
>>> python -m venv .synapseForge
>>> .\synapseForge\Scripts\Activate.ps1
>>> pip install -r requirements.txt
```

---

## 3. Comandos básicos Git

- Crear y cambiar a una rama:

```bash
git checkout -b feature/mi-nueva-feature
```

- Mantener tu rama actualizada (rebase recomendado):

```bash
git fetch origin
git rebase origin/main
```

- Subir la rama:

```bash
git push origin feature/mi-nueva-feature
```

---

## 4. Abrir Pull Request

Al abrir PR en GitHub, usar el template correspondiente según el tipo de cambio:

- **General**: `?template=general.md`
- **Feature**: `?template=feature.md`
- **Fix**: `?template=fix.md`

```bash
# Ejemplo: abrir PR con template de feature
https://github.com/synapse-ai-hub/synapseForge/compare/main...feature/mi-feature?template=feature.md
```

---

## 5. Recursos y ayuda

- Revisá [GIT_WORKFLOW.md](./OnBoarding/GIT_WORKFLOW.md) para el flujo de trabajo.
- Si tenés dudas, abrí un issue o consultá al equipo.

---

Autor: synapse.ai  
Última actualización: 2025-10-13

