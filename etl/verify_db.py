"""Verifica integridad de datos cargados (sin depender del codepage de consola)."""

import psycopg2

with psycopg2.connect("postgresql://postgres@localhost:5433/licitaciones") as conn, conn.cursor() as cur:
    cur.execute(
        "SELECT k.palabra = 'logística', l.nombre LIKE '%Logística%', l.region = 'Región de Atacama' "
        "FROM licitaciones l "
        "JOIN licitacion_palabra_clave lp ON lp.licitacion_id = l.id "
        "JOIN palabras_clave k ON k.id = lp.palabra_id "
        "LIMIT 1"
    )
    keyword_ok, nombre_ok, region_ok = cur.fetchone()
    print(f"keyword exacta: {keyword_ok} | nombre con acento: {nombre_ok} | region: {region_ok}")
