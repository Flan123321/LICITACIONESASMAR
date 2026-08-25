"""Inicializa la BD local: crea 'licitaciones' y aplica db/schema.sql."""

import sys
from pathlib import Path

import psycopg2

DB_CONFIG = {"host": "localhost", "port": 5433, "user": "postgres"}
SCHEMA = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


def main() -> int:
    conn = psycopg2.connect(dbname="postgres", **DB_CONFIG)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'licitaciones'")
        if cur.fetchone():
            print("BD 'licitaciones' ya existe")
        else:
            cur.execute("CREATE DATABASE licitaciones")
            print("BD 'licitaciones' creada")
    conn.close()

    conn = psycopg2.connect(dbname="licitaciones", **DB_CONFIG)
    with conn, conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        cur.execute(SCHEMA.read_text(encoding="utf-8"))
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        print("Tablas:", [r[0] for r in cur.fetchall()])
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
