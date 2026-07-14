<p align="center">
  <img src="<logo>url_logo</logo>" alt="Logo" width="150">

---
  
</p><h1 align="center">🚀 Comandos CLI y entorno virtual</h1>

---

## ⚡ Uso

### Manual (sin configurar nada)

Ejecutar esto **cada vez** que abrís la terminal:

```powershell
.\.\TU_VENV\Scripts\Activate.ps1
. .\.commands\init.ps1
```

Reemplazar `TU_VENV` por el nombre de tu entorno virtual.
i¡sto! Ya podés usar: push, sync o tus comandos

---

### Automático (una sola vez)

Para que se active solo cada vez que abrís la terminal:

#### 1. Configurar perfil de PowerShell

```powershell
code $PROFILE
```

#### 2. Pegar esto y guardar:

```powershell
# Busca .commands en la carpeta actual
if (Test-Path ".commands") {
    # Activa el entorno virtual (cualquier nombre con Scripts/Activate.ps1)
    Get-ChildItem -Directory | Where-Object {
        Test-Path "$_\Scripts\Activate.ps1"
    } | Select-Object -First 1 | ForEach-Object {
        & "$_\Scripts\Activate.ps1"
    }
    # Carga tus comandos
    . ".commands\init.ps1"
}
```

Li¡sto! La próxima vez que abras la terminal se activa solo.

---

## 📝 Agregar Comandos

Editar .commands/commands.json:

```json
{
    "alias": "nuevo",
    "command": "python script.py",
    "description": "Descripción"
}
`powershell
.\venv\Scripts\Activate.ps1
. .\.commands\init.ps1
```

---

## 🔧 Debug

- ¿Comandos no cargan? → Reiniciar terminal
- ¿Venv no activa? → Verificar Scripts/Activate.ps1 existe