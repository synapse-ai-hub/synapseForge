"""
Script para realizar consultas en la base de datos de Turnero.
Uso: python db/query.py "SELECT * FROM conversations"
"""
import sys
import os
import argparse
from dotenv import load_dotenv

load_dotenv(override=True)

parser = argparse.ArgumentParser(
    description="Consultas en la base de datos de Turnero"
)

parser.add_argument(
    "query",
    type=str,
    help="Query en SQL"
)

args = parser.parse_args()

import psycopg2

database_url = os.getenv("DATABASE_URL")
if not database_url:
    print("ERROR: DATABASE_URL no configurada")
    sys.exit(1)

conn = psycopg2.connect(database_url)
conn.autocommit = True
cursor = conn.cursor()

cursor.execute(args.query)

if args.query.strip().upper().startswith("SELECT"):
    rows = cursor.fetchall()
    for row in rows:
        print(row)
else:
    print("Ejecutado")

cursor.close()
conn.close()