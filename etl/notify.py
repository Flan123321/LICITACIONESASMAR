"""Notificador de licitaciones filtradas por email."""

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict, Any

# ─── Config desde entorno ───
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)


def _html_table(rows: List[Dict[str, Any]]) -> str:
    head = (
        "<tr style='background:#1e293b;color:white'>"
        "<th style='padding:8px;border:1px solid #334155'>Código</th>"
        "<th style='padding:8px;border:1px solid #334155'>Nombre</th>"
        "<th style='padding:8px;border:1px solid #334155'>Comprador</th>"
        "<th style='padding:8px;border:1px solid #334155'>Comuna</th>"
        "<th style='padding:8px;border:1px solid #334155'>Región</th>"
        "<th style='padding:8px;border:1px solid #334155'>Cierre</th>"
        "<th style='padding:8px;border:1px solid #334155;text-align:right'>Monto (CLP)</th>"
        "<th style='padding:8px;border:1px solid #334155'>Palabras clave</th>"
        "<th style='padding:8px;border:1px solid #334155'>Acción</th></tr>"
    )
    body_rows = []
    for i, r in enumerate(rows):
        bg = "#f8fafc" if i % 2 == 0 else "white"
        kw = ", ".join(r.get("palabras_clave") or [])
        monto = f"${r['monto_estimado']:,.0f}" if r.get("monto_estimado") else "—"
        cierre = r["fecha_cierre"].strftime("%d-%m-%Y %H:%M") if r.get("fecha_cierre") else "—"
        url = r.get("url_detalle") or "#"
        body_rows.append(
            f"<tr style='background:{bg}'>"
            f"<td style='padding:8px;border:1px solid #e2e8f0;font-family:monospace;font-size:12px'>{r['codigo_externo']}</td>"
            f"<td style='padding:8px;border:1px solid #e2e8f0'>{r['nombre']}</td>"
            f"<td style='padding:8px;border:1px solid #e2e8f0'>{r.get('nombre_comprador') or '—'}</td>"
            f"<td style='padding:8px;border:1px solid #e2e8f0'>{r.get('comuna') or '—'}</td>"
            f"<td style='padding:8px;border:1px solid #e2e8f0'>{r.get('region') or '—'}</td>"
            f"<td style='padding:8px;border:1px solid #e2e8f0'>{cierre}</td>"
            f"<td style='padding:8px;border:1px solid #e2e8f0;text-align:right;font-family:monospace'>{monto}</td>"
            f"<td style='padding:8px;border:1px solid #e2e8f0;font-size:12px'>{kw}</td>"
            f"<td style='padding:8px;border:1px solid #e2e8f0'><a href='{url}' style='color:#0ea5e9;text-decoration:none'>Ver en MP</a></td>"
            f"</tr>"
        )
    return (
        f"<table style='border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:13px;border:1px solid #e2e8f0'>"
        f"{head}{''.join(body_rows)}</table>"
    )


def _texto_plano(rows: List[Dict[str, Any]]) -> str:
    lineas = []
    for r in rows:
        kw = ", ".join(r.get("palabras_clave") or [])
        monto = f"${r['monto_estimado']:,.0f} CLP" if r.get("monto_estimado") else "—"
        cierre = r["fecha_cierre"].strftime("%d-%m-%Y %H:%M") if r.get("fecha_cierre") else "—"
        lineas.append(
            f"• {r['codigo_externo']} | {r['nombre'][:80]}… | {r.get('nombre_comprador') or '—'} | "
            f"{r.get('comuna') or '—'}, {r.get('region') or '—'} | Cierre: {cierre} | Monto: {monto} | Keys: {kw} | "
            f"{r.get('url_detalle')}"
        )
    return "\n".join(lineas)


def enviar_email(rows: List[Dict[str, Any]]) -> bool:
    """Envía reporte por SMTP (STARTTLS). Requiere SMTP_HOST, SMTP_USER, SMTP_PASS, EMAIL_TO."""
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and EMAIL_TO):
        print("⚠️ Email no configurado (faltan vars SMTP_* / EMAIL_TO)")
        return False
    if not rows:
        return True

    fecha = rows[0].get("fecha_cierre")
    fecha_str = fecha.strftime("%d-%m-%Y") if fecha else "hoy"
    asunto = f"🔔 {len(rows)} licitación(es) clave detectada(s) — Mercado Público — {fecha_str}"

    html = f"""<!DOCTYPE html>
<html><body style="margin:0;padding:20px;background:#f1f5f9">
  <div style="max-width:900px;margin:0 auto;background:white;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1)">
    <div style="background:#0f172a;color:white;padding:20px">
      <h1 style="margin:0;font-size:20px">{asunto}</h1>
      <p style="margin:8px 0 0;opacity:.8">Reporte automático del ETL Mercado Público</p>
    </div>
    <div style="padding:20px">{_html_table(rows)}</div>
    <div style="background:#f8fafc;padding:16px 20px;border-top:1px solid #e2e8f0;font-size:12px;color:#64748b">
      Generado automáticamente — no responder a este correo
    </div>
  </div>
</body></html>"""

    texto = f"{asunto}\n\n{_texto_plano(rows)}\n\n---\nGenerado automáticamente por el ETL Mercado Público"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(texto, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    ctx = ssl.create_default_context()
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls(context=ctx)
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"[OK] Email enviado a {EMAIL_TO} ({len(rows)} licitaciones)")
        return True
    except Exception as e:
        print(f"[ERROR] Error enviando email: {e}")
        return False


if __name__ == "__main__":
    import json
    from datetime import datetime
    test = [{
        "codigo_externo": "TEST-001",
        "nombre": "Licitación de prueba con logística y radar",
        "nombre_comprador": "Municipalidad Demo",
        "comuna": "Santiago",
        "region": "Región Metropolitana",
        "fecha_cierre": datetime(2026, 9, 15, 12, 0),
        "monto_estimado": 125000000,
        "url_detalle": "https://www.mercadopublico.cl/...",
        "palabras_clave": ["logística", "radar"],
    }]
    enviar_email(test)