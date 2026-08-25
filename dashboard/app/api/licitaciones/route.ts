import { Pool } from "pg";

const pool = new Pool({ connectionString: process.env.DATABASE_URL });

export interface Licitacion {
  id: number;
  codigo_externo: string;
  nombre: string;
  descripcion: string | null;
  estado: string;
  fecha_publicacion: string | null;
  fecha_cierre: string | null;
  comuna: string | null;
  region: string | null;
  nombre_comprador: string | null;
  moneda: string | null;
  monto_estimado: number | null;
  url_detalle: string | null;
  palabras_clave: string[];
}

const QUERY = `
  SELECT
    l.id, l.codigo_externo, l.nombre, l.descripcion, l.estado,
    l.fecha_publicacion, l.fecha_cierre,
    l.comuna, l.region, l.nombre_comprador, l.moneda,
    l.monto_estimado, l.url_detalle,
    COALESCE(json_agg(k.palabra ORDER BY k.palabra) FILTER (WHERE k.id IS NOT NULL), '[]') AS palabras_clave
  FROM licitaciones l
  LEFT JOIN licitacion_palabra_clave lp ON lp.licitacion_id = l.id
  LEFT JOIN palabras_clave k ON k.id = lp.palabra_id
  WHERE l.estado = 'Publicada'
  GROUP BY l.id
  ORDER BY l.fecha_cierre ASC NULLS LAST
`;

export async function GET() {
  try {
    const { rows } = await pool.query<Licitacion>(QUERY);
    return Response.json(rows);
  } catch (error) {
    console.error("[GET /api/licitaciones]", error);
    return Response.json({ error: "Error al consultar licitaciones" }, { status: 500 });
  }
}
