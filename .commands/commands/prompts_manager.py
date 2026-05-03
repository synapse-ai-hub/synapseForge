"""
Script para sincronizar los prompts del sistema en la base de datos
con los archivos .md en backend/prompts/.

Funciona exactamente como sync_prompt_system.py:
- Lee todos los archivos .md de backend/prompts/
- Compara con los registros en la tabla prompts
- Agrega los nuevos, actualiza los modificados, borra los que ya no existen en local

Uso:
    python db/prompts_manager.py
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno desde la raíz donde se ejecuta el script
load_dotenv(override=True)


def main():
    import psycopg2
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL no configurada")
        return
    
    prompts_dir = Path("backend/prompts")
    if not prompts_dir.exists():
        print(f"ERROR: No se encontró el directorio de prompts: {prompts_dir}")
        return
    
    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # 1. Obtener prompts actuales en DB
        cursor.execute("SELECT prompt_id, prompt_content FROM prompts")
        rows = cursor.fetchall()
        db_map = {str(row[0]): row[1] for row in rows}
        
        # 2. Leer archivos .md locales
        local_entries = {}
        for md_file in prompts_dir.glob("*.md"):
            prompt_id = md_file.stem
            with open(md_file, 'r', encoding='utf-8') as f:
                local_entries[prompt_id] = f.read()
        
        local_ids = set(local_entries.keys())
        existing_ids = set(db_map.keys())
        
        to_add = local_ids - existing_ids
        to_delete = existing_ids - local_ids
        to_update = [
            pid for pid in (local_ids & existing_ids)
            if db_map[pid] != local_entries[pid]
        ]
        
        added = 0
        updated = 0
        deleted = 0
        
        # 3. Agregar nuevos
        for prompt_id in to_add:
            cursor.execute(
                "INSERT INTO prompts (prompt_id, prompt_content, created_at, updated_at) VALUES (%s, %s, %s, %s)",
                (prompt_id, local_entries[prompt_id], datetime.now(), datetime.now())
            )
            added += 1
            print(f"+ {prompt_id}")
        
        # 4. Actualizar modificados
        for prompt_id in to_update:
            cursor.execute(
                "UPDATE prompts SET prompt_content = %s, updated_at = %s WHERE prompt_id = %s",
                (local_entries[prompt_id], datetime.now(), prompt_id)
            )
            updated += 1
            print(f"~ {prompt_id}")
        
        # 5. Borrar los que ya no están en local
        for prompt_id in to_delete:
            cursor.execute("DELETE FROM prompts WHERE prompt_id = %s", (prompt_id,))
            deleted += 1
            print(f"- {prompt_id}")
        
        if added == 0 and updated == 0 and deleted == 0:
            print("Sin cambios")
        else:
            print(f"Sincronizado: {added} agregados, {updated} actualizados, {deleted} borrados")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    main()