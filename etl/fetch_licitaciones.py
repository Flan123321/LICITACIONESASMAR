"""
ETL - Mercado Público de Chile
=============================
Consume la API oficial (http://api.mercadopublico.cl) para obtener las
licitaciones del día, filtra por estado 'Publicada' y por palabras clave,
persiste los registros limpios en PostgreSQL y exporta un JSON.

Variables de entorno requeridas:
    MP_TICKET      -> Ticket/API key obtenido en https://api.mercadopublico.cl
    DATABASE_URL   -> ej: postgresql://user:pass@localhost:5432/licitaciones

Uso:
    set MP_TICKET=TU_TICKET && set DATABASE_URL=... && python fetch_licitaciones.py [YYYY-MM-DD]
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import psycopg2
import psycopg2.extras
import requests

# ─── Carga .env si existe ───
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass  # python-dotenv no instalado; se usan vars de entorno del sistema

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

BASE_URL = os.getenv(
    "MP_API_BASE", "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
)
TICKET = os.getenv("MP_TICKET", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

KEYWORDS = ["desalinizadora", "hospital de campaña", "logística", "radar", "carpas"]

ESTADO_PUBLICADA_CODIGO = 5  # CodigoEstado oficial para 'Publicada'
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mercado-publico")

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def normalizar(texto: str) -> str:
    """Lowercase + eliminación de acentos para matching insensible."""
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def parse_fecha_cierre(valor: Optional[str]) -> Optional[datetime]:
    """La API entrega formatos variables; se intentan los conocidos."""
    if not valor:
        return None
    valor = valor.strip()
    try:
        return datetime.fromisoformat(valor)
    except ValueError:
        pass
    for fmt in ("%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(valor, fmt)
        except ValueError:
            continue
    log.warning("No se pudo parsear fecha: %r", valor)
    return None


def url_ficha(codigo_externo: str) -> str:
    return (
        "https://www.mercadopublico.cl/Procurement/Modules/RFB/"
        f"DetailsAcquisition.aspx?idtoc={codigo_externo}"
    )

# ---------------------------------------------------------------------------
# Extracción (API Mercado Público)
# ---------------------------------------------------------------------------


def obtener_licitaciones_del_dia(fecha: date) -> list[dict[str, Any]]:
    """Descarga las licitaciones publicadas para la fecha indicada."""
    params = {
        "fecha": fecha.strftime("%d%m%Y"),
        "ticket": TICKET,
    }
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    listado = data.get("Listado") or []
    total = data.get("Cantidad", len(listado))
    log.info("API respondió %s licitaciones para %s", total, fecha.isoformat())
    return listado


def esta_publicada(licitacion: dict[str, Any]) -> bool:
    """Filtro defensivo por estado: código 5 o texto 'Publicada' en Etapa/Estado."""
    if licitacion.get("CodigoEstado") == ESTADO_PUBLICADA_CODIGO:
        return True
    etapa = normalizar(str(licitacion.get("Etapa") or licitacion.get("Estado") or ""))
    return etapa == "publicada"


def texto_busqueda(licitacion: dict[str, Any]) -> str:
    """Nombre + nombres de items (si la respuesta los incluye)."""
    partes = [str(licitacion.get("Nombre") or "")]
    for item in licitacion.get("Items") or []:
        partes.append(str(item.get("NombreItem") or ""))
    return normalizar(" ".join(partes))


def limpiar_texto(valor: Any) -> Optional[str]:
    """Convierte a string recortado; vacío/None → None."""
    texto = str(valor).strip() if valor is not None else None
    return texto or None

# ---------------------------------------------------------------------------
# Transformación
# ---------------------------------------------------------------------------


def transformar(listado: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keywords_norm = {normalizar(k): k for k in KEYWORDS}
    limpias: list[dict[str, Any]] = []

    for lic in listado:
        if not esta_publicada(lic):
            continue

        texto = texto_busqueda(lic)
        coincidencias = sorted({orig for norm, orig in keywords_norm.items() if norm in texto})
        if not coincidencias:
            continue

        codigo = str(lic.get("CodigoExterno") or "").strip()
        if not codigo:
            continue

        limpias.append(
            {
                "codigo_externo": codigo,
                "nombre": str(lic.get("Nombre") or "").strip(),
                "descripcion": None,
                "estado": lic.get("Etapa") or lic.get("Estado") or "Publicada",
                "fecha_publicacion": None,
                "fecha_cierre": parse_fecha_cierre(lic.get("FechaCierre")),
                "comuna": lic.get("Comuna"),
                "region": lic.get("RegionUnidad"),
                "rut_comprador": lic.get("RutComprador"),
                "nombre_comprador": lic.get("NombreComprador"),
                "moneda": lic.get("Moneda"),
                "monto_estimado": lic.get("PresupuestoEstimadoCLP") or lic.get("MontoEstimado"),
                "url_detalle": url_ficha(codigo),
                "palabras_clave": coincidencias,
            }
        )

    log.info("%s licitaciones pasaron el filtro (estado + keywords)", len(limpias))
    return limpias


def _detalle_licitacion(codigo: str) -> Optional[dict[str, Any]]:
    resp = requests.get(
        BASE_URL, params={"codigo": codigo, "ticket": TICKET}, timeout=30
    )
    resp.raise_for_status()
    listado = resp.json().get("Listado") or []
    return listado[0] if listado else None


def enriquecer(registros: list[dict[str, Any]]) -> None:
    """Completa comuna/región/comprador/fechas/monto desde el detalle y
    re-ejecuta el matching de keywords sobre descripción e items."""
    keywords_norm = {normalizar(k): k for k in KEYWORDS}

    for reg in registros:
        try:
            detalle = _detalle_licitacion(reg["codigo_externo"])
        except requests.RequestException as exc:
            log.warning("Sin detalle para %s: %s", reg["codigo_externo"], exc)
            continue
        if not detalle:
            continue

        comprador = detalle.get("Comprador") or {}
        fechas = detalle.get("Fechas") or {}
        items = (detalle.get("Items") or {}).get("Listado") or []

        reg["descripcion"] = limpiar_texto(detalle.get("Descripcion"))
        reg["comuna"] = limpiar_texto(comprador.get("ComunaUnidad"))
        reg["region"] = limpiar_texto(comprador.get("RegionUnidad"))
        reg["rut_comprador"] = limpiar_texto(comprador.get("RutUnidad"))
        reg["nombre_comprador"] = limpiar_texto(
            comprador.get("NombreOrganismo") or comprador.get("NombreUnidad")
        )
        reg["fecha_publicacion"] = parse_fecha_cierre(fechas.get("FechaPublicacion"))
        reg["fecha_cierre"] = (
            parse_fecha_cierre(fechas.get("FechaCierre")) or reg["fecha_cierre"]
        )
        reg["moneda"] = detalle.get("Moneda")
        reg["monto_estimado"] = detalle.get("MontoEstimado")

        texto_items = " ".join(
            f"{i.get('NombreProducto')} {i.get('Descripcion')} {i.get('Categoria')}"
            for i in items
        )
        texto = normalizar(f"{reg['nombre']} {reg['descripcion'] or ''} {texto_items}")
        coincidencias = {orig for norm, orig in keywords_norm.items() if norm in texto}
        reg["palabras_clave"] = sorted(set(reg["palabras_clave"]) | coincidencias)

        time.sleep(0.3)  # cortesía con la API

# ---------------------------------------------------------------------------
# Carga (PostgreSQL)
# ---------------------------------------------------------------------------

UPSERT_LICITACION = """
INSERT INTO licitaciones (
    codigo_externo, nombre, descripcion, estado, fecha_publicacion, fecha_cierre,
    comuna, region, rut_comprador, nombre_comprador, moneda, monto_estimado, url_detalle
) VALUES (%(codigo_externo)s, %(nombre)s, %(descripcion)s, %(estado)s,
          %(fecha_publicacion)s, %(fecha_cierre)s, %(comuna)s, %(region)s,
          %(rut_comprador)s, %(nombre_comprador)s, %(moneda)s, %(monto_estimado)s,
          %(url_detalle)s)
ON CONFLICT (codigo_externo) DO UPDATE SET
    nombre            = EXCLUDED.nombre,
    descripcion       = EXCLUDED.descripcion,
    estado            = EXCLUDED.estado,
    fecha_publicacion = EXCLUDED.fecha_publicacion,
    fecha_cierre      = EXCLUDED.fecha_cierre,
    comuna            = EXCLUDED.comuna,
    region            = EXCLUDED.region,
    rut_comprador     = EXCLUDED.rut_comprador,
    nombre_comprador  = EXCLUDED.nombre_comprador,
    moneda            = EXCLUDED.moneda,
    monto_estimado    = EXCLUDED.monto_estimado,
    url_detalle       = EXCLUDED.url_detalle,
    updated_at        = now()
RETURNING id;
"""

UPSERT_PALABRA = """
INSERT INTO palabras_clave (palabra) VALUES (%s)
ON CONFLICT (palabra) DO UPDATE SET palabra = EXCLUDED.palabra
RETURNING id;
"""

INSERT_RELACION = """
INSERT INTO licitacion_palabra_clave (licitacion_id, palabra_id)
VALUES (%s, %s)
ON CONFLICT (licitacion_id, palabra_id) DO NOTHING;
"""


def cargar(registros: list[dict[str, Any]]) -> int:
    if not registros:
        log.warning("Nada que insertar.")
        return 0
    if not DATABASE_URL:
        log.warning("DATABASE_URL no definida: se omite la carga en BD (JSON ya exportado).")
        return 0

    insertados = 0
    with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        for reg in registros:
            cur.execute(UPSERT_LICITACION, reg)
            licitacion_id = cur.fetchone()[0]

            for palabra in reg["palabras_clave"]:
                cur.execute(UPSERT_PALABRA, (palabra,))
                palabra_id = cur.fetchone()[0]
                cur.execute(INSERT_RELACION, (licitacion_id, palabra_id))
            insertados += 1
    log.info("Upsert completado: %s registros.", insertados)
    return insertados

# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------


def exportar_json(registros: list[dict[str, Any]], fecha: date) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    destino = OUTPUT_DIR / f"licitaciones_filtradas_{fecha:%Y%m%d}.json"
    payload = {"fecha": fecha.isoformat(), "cantidad": len(registros), "licitaciones": registros}
    destino.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    log.info("JSON exportado: %s", destino)
    return destino


def main() -> int:
    if not TICKET:
        log.error("Define la variable de entorno MP_TICKET (https://api.mercadopublico.cl).")
        return 1

    fecha = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()

    try:
        listado = obtener_licitaciones_del_dia(fecha)
        registros = transformar(listado)
        enriquecer(registros)
        exportar_json(registros, fecha)
        cargar(registros)

        # ── Notificación si hay matches ───
        if registros:
            try:
                from notify import enviar_email
                enviar_email(registros)
            except Exception as exc:
                log.warning("Notificación falló: %s", exc)

    except requests.RequestException as exc:
        log.error("Error consumiendo la API: %s", exc)
        return 2
    except psycopg2.Error as exc:
        log.error("Error de base de datos: %s", exc)
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
