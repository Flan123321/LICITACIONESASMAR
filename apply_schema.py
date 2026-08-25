import psycopg2
conn = psycopg2.connect('postgresql://neondb_owner:npg_Vys4aQcX5LxP@ep-little-frost-axxbzyx8-pooler.c-4.us-east-2.aws.neon.tech/neondb?sslmode=require')
conn.autocommit = True
with conn.cursor() as cur:
    cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    cur.execute(open('E:/licitaciones/db/schema.sql', encoding='utf-8').read())
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
    print('Tablas creadas:', [r[0] for r in cur.fetchall()])
conn.close()
print('LISTO')