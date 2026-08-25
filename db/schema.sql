-- ============================================================
-- Esquema: Licitaciones Mercado Público de Chile (PostgreSQL)
-- ============================================================

CREATE TABLE IF NOT EXISTS licitaciones (
    id               BIGSERIAL PRIMARY KEY,
    codigo_externo   VARCHAR(20)   UNIQUE NOT NULL,      -- CodigoExterno de la API
    nombre           TEXT          NOT NULL,             -- Nombre de la licitación
    descripcion      TEXT,
    estado           VARCHAR(50)   NOT NULL DEFAULT 'Publicada',
    fecha_publicacion TIMESTAMPTZ,
    fecha_cierre     TIMESTAMPTZ,
    comuna           VARCHAR(120),
    region           VARCHAR(120),
    rut_comprador    VARCHAR(20),
    nombre_comprador VARCHAR(200),
    moneda           CHAR(3)       DEFAULT 'CLP',
    monto_estimado   NUMERIC(18, 2),
    url_detalle      TEXT,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_licitaciones_fecha_cierre ON licitaciones (fecha_cierre);
CREATE INDEX IF NOT EXISTS idx_licitaciones_estado       ON licitaciones (estado);
CREATE INDEX IF NOT EXISTS idx_licitaciones_nombre_trgm  ON licitaciones USING gin (nombre gin_trgm_ops);
-- Nota: para el índice trigram ejecutar antes: CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Catálogo de palabras clave del filtro ETL
CREATE TABLE IF NOT EXISTS palabras_clave (
    id      SERIAL PRIMARY KEY,
    palabra VARCHAR(100) UNIQUE NOT NULL
);

-- Relación N:M licitación <-> keyword (una licitación puede matchear varias)
CREATE TABLE IF NOT EXISTS licitacion_palabra_clave (
    licitacion_id BIGINT NOT NULL REFERENCES licitaciones (id) ON DELETE CASCADE,
    palabra_id    INT    NOT NULL REFERENCES palabras_clave (id) ON DELETE CASCADE,
    PRIMARY KEY (licitacion_id, palabra_id)
);

-- ============================================================
-- Consulta de inserción (upsert idempotente) usada por el ETL
-- ============================================================
-- INSERT INTO licitaciones (codigo_externo, nombre, estado, fecha_cierre,
--                           comuna, region, rut_comprador, nombre_comprador,
--                           moneda, monto_estimado, url_detalle)
-- VALUES (%s, %s, 'Publicada', %s, %s, %s, %s, %s, %s, %s, %s)
-- ON CONFLICT (codigo_externo) DO UPDATE SET
--     nombre = EXCLUDED.nombre,
--     fecha_cierre = EXCLUDED.fecha_cierre,
--     updated_at = now();

-- ============================================================
-- Consulta para el dashboard: licitaciones + keywords agregadas
-- ============================================================
SELECT
    l.id,
    l.codigo_externo,
    l.nombre,
    l.estado,
    l.fecha_cierre,
    l.comuna,
    l.region,
    l.nombre_comprador,
    l.moneda,
    l.monto_estimado,
    l.url_detalle,
    COALESCE(
        json_agg(k.palabra ORDER BY k.palabra) FILTER (WHERE k.id IS NOT NULL),
        '[]'
    ) AS palabras_clave
FROM licitaciones l
LEFT JOIN licitacion_palabra_clave lp ON lp.licitacion_id = l.id
LEFT JOIN palabras_clave k            ON k.id = lp.palabra_id
WHERE l.estado = 'Publicada'
GROUP BY l.id
ORDER BY l.fecha_cierre ASC NULLS LAST;
