"use client";

import { useEffect, useMemo, useState } from "react";
import type { Licitacion } from "@/app/api/licitaciones/route";

const KEYWORD_STYLES: Record<string, string> = {
  desalinizadora: "bg-sky-100 text-sky-700 ring-sky-200",
  "hospital de campaña": "bg-rose-100 text-rose-700 ring-rose-200",
  logística: "bg-amber-100 text-amber-700 ring-amber-200",
  radar: "bg-violet-100 text-violet-700 ring-violet-200",
  carpas: "bg-emerald-100 text-emerald-700 ring-emerald-200",
};

const clp = new Intl.NumberFormat("es-CL", {
  style: "currency",
  currency: "CLP",
  maximumFractionDigits: 0,
});

function formatearFecha(valor: string | null) {
  if (!valor) return "—";
  return new Date(valor).toLocaleString("es-CL", { dateStyle: "medium", timeStyle: "short" });
}

export default function LicitacionesTable() {
  const [licitaciones, setLicitaciones] = useState<Licitacion[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busqueda, setBusqueda] = useState("");

  useEffect(() => {
    fetch("/api/licitaciones")
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then(setLicitaciones)
      .catch(() => setError("No se pudieron cargar las licitaciones."))
      .finally(() => setCargando(false));
  }, []);

  const filtradas = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    if (!q) return licitaciones;
    return licitaciones.filter((l) =>
      [l.nombre, l.nombre_comprador, l.comuna, l.codigo_externo]
        .filter(Boolean)
        .some((campo) => campo!.toLowerCase().includes(q)),
    );
  }, [licitaciones, busqueda]);

  return (
    <section className="space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Licitaciones filtradas
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Mercado Público · estado <span className="font-medium">Publicada</span> ·{" "}
            {filtradas.length} resultado(s)
          </p>
        </div>
        <input
          type="search"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Buscar por nombre, comprador, comuna…"
          className="w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm text-slate-900 shadow-sm outline-none placeholder:text-slate-400 focus:border-slate-400 focus:ring-2 focus:ring-slate-200 sm:w-72"
        />
      </header>

      {error && (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
            <tr>
              <th className="px-4 py-3">Código</th>
              <th className="px-4 py-3">Nombre y coincidencias</th>
              <th className="hidden px-4 py-3 lg:table-cell">Comprador</th>
              <th className="hidden px-4 py-3 md:table-cell">Cierre</th>
              <th className="px-4 py-3 text-right">Monto estimado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {cargando && (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center text-slate-400">
                  Cargando licitaciones…
                </td>
              </tr>
            )}
            {!cargando && filtradas.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center text-slate-400">
                  Sin licitaciones que coincidan con el filtro.
                </td>
              </tr>
            )}
            {!cargando &&
              filtradas.map((l) => (
                <tr key={l.id} className="transition-colors hover:bg-slate-50/80">
                  <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-slate-500">
                    {l.codigo_externo}
                  </td>
                  <td className="max-w-md px-4 py-3">
                    <a
                      href={l.url_detalle ?? "#"}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-slate-900 hover:text-sky-600 hover:underline"
                    >
                      {l.nombre}
                    </a>
                    <p className="mt-0.5 text-xs text-slate-400">
                      {[l.comuna, l.region].filter(Boolean).join(", ") || "—"}
                    </p>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {l.palabras_clave.map((kw) => (
                        <span
                          key={kw}
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${
                            KEYWORD_STYLES[kw] ?? "bg-slate-100 text-slate-600 ring-slate-200"
                          }`}
                        >
                          {kw}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="hidden whitespace-nowrap px-4 py-3 text-slate-600 lg:table-cell">
                    {l.nombre_comprador ?? "—"}
                  </td>
                  <td className="hidden whitespace-nowrap px-4 py-3 text-slate-600 md:table-cell">
                    {formatearFecha(l.fecha_cierre)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-slate-800">
                    {l.monto_estimado ? clp.format(Number(l.monto_estimado)) : "—"}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
