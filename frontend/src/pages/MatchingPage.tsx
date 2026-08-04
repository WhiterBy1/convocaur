import { motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useState } from "react";
import { MatchTree } from "../components/MatchTree";
import { api, apiPost, pollJob, type JobStatus } from "../lib/api";

type ConvItem = {
  id: string;
  numero: string;
  titulo?: string;
  objetivo_preview?: string;
  top1_nombre?: string;
  top1_score?: number;
  n_candidatos_pool?: number;
  tiene_ranking?: boolean;
  tiene_elegibilidad?: boolean;
  puede_postularse?: boolean | null;
  modo_elegibilidad?: string | null;
};

type Summary = {
  n_nlp: number;
  n_con_ranking: number;
  n_sin_ranking: number;
  n_elegibles: number;
  n_cache_embeddings: number;
  convocatorias: ConvItem[];
};

type TerminoClave = {
  term: string;
  peso: number;
  evidencia_docente?: string | null;
  evidencia_convocatoria?: string | null;
};

type RankingPayload = {
  convocatoria: string;
  n: number;
  n_pool: number;
  rows: {
    id: string;
    nombre: string;
    facultad: string;
    score_final: number;
    score_emb: number;
    score_tfidf: number;
    boost: number;
    rank: number;
    caracteristicas: { id: string; label: string; aporte: number; tipo: string }[];
    terminos_clave?: TerminoClave[];
  }[];
};

type ConvDetail = {
  id: string;
  tiene_ranking?: boolean;
  texto_matching: string;
  nlp: {
    objetivo?: string;
    alianza_obligatoria?: boolean;
    actores_elegibles?: unknown[];
    lineas_tematicas?: unknown[];
    requisitos?: unknown[];
    criterios_evaluacion?: unknown[];
    financiacion?: string | Record<string, unknown>;
  };
  elegibilidad_urosario?: {
    puede_postularse?: boolean;
    modo?: string;
    rol_sugerido?: string | null;
    bloqueantes?: unknown[];
    condiciones_a_verificar?: unknown[];
    resumen?: string;
    fuente?: string;
  };
};

function asText(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  if (Array.isArray(v)) return v.map(asText).filter(Boolean).join(" · ");
  if (typeof v === "object") {
    const o = v as Record<string, unknown>;
    return (
      asText(o.texto) ||
      asText(o.nombre) ||
      asText(o.descripcion_corta) ||
      asText(o.descripcion) ||
      asText(o.condicion) ||
      asText(o.tipo) ||
      asText(o.rol) ||
      JSON.stringify(o)
    );
  }
  return String(v);
}

function asTextList(items: unknown[] | undefined, max = 8): string[] {
  if (!items?.length) return [];
  return items.map(asText).filter(Boolean).slice(0, max);
}

function elegibilidadLabel(c: Pick<ConvItem, "puede_postularse" | "tiene_elegibilidad">) {
  if (c.puede_postularse === true) return "Elegible";
  if (c.puede_postularse === false) return "No elegible";
  if (c.tiene_elegibilidad) return "Sin veredicto";
  return "Sin evaluar";
}

type BrowseMode = "matching" | "fuera" | "revisar";

type IngestResult = {
  ok?: boolean;
  numero?: string;
  titulo?: string;
  mensaje?: string;
  error?: string;
  puede_postularse?: boolean | null;
  modo?: string | null;
  resumen_elegibilidad?: string | null;
  fases?: string[];
  matching?: { omitido?: boolean; ok?: boolean; motivo?: string };
  borrados?: string[];
};

function previewTitle(c: ConvItem, max = 90) {
  const t = c.titulo || c.objetivo_preview || "sin título";
  return t.length > max ? `${t.slice(0, max)}…` : t;
}

function ingestSteps(r: IngestResult): { id: string; label: string; done: boolean; muted?: boolean }[] {
  const fases = new Set(r.fases || []);
  const matchDone = fases.has("matching");
  const matchSkip = fases.has("matching_omitido") || !!r.matching?.omitido;
  return [
    { id: "detalle", label: "Detalle", done: fases.has("detalle") || !!r.ok },
    { id: "tdr", label: "TdR", done: fases.has("tdr") || !!r.ok },
    { id: "nlp", label: "NLP", done: fases.has("nlp") || !!r.ok },
    {
      id: "match",
      label: matchSkip ? "Sin ranking" : "Ranking",
      done: matchDone || matchSkip || !!r.ok,
      muted: matchSkip,
    },
    {
      id: "limpieza",
      label: "PDF borrado",
      done: fases.has("limpieza") || (r.borrados?.length || 0) > 0,
    },
  ];
}

export function MatchingPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [browse, setBrowse] = useState<BrowseMode>("matching");
  const [ranking, setRanking] = useState<RankingPayload | null>(null);
  const [detail, setDetail] = useState<ConvDetail | null>(null);
  const [activeProf, setActiveProf] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [jobMsg, setJobMsg] = useState<string | null>(null);
  const [jobProgress, setJobProgress] = useState<{
    fase?: string;
    mensaje?: string;
    hecho?: number;
    total?: number;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [syncResult, setSyncResult] = useState<Record<string, unknown> | null>(null);

  const refreshSummary = useCallback(async (keepSelected = true) => {
    const s = await api<Summary>("/api/matching/summary");
    setSummary(s);
    setSelected((prev) => {
      if (keepSelected && prev && s.convocatorias.some((c) => c.id === prev)) return prev;
      const preferred =
        s.convocatorias.find((c) => c.puede_postularse === true && c.tiene_ranking) ||
        s.convocatorias.find((c) => c.puede_postularse === true) ||
        s.convocatorias[0];
      return preferred?.id || "";
    });
    return s;
  }, []);

  useEffect(() => {
    refreshSummary(false).catch((e) => setErr(String(e.message || e)));
  }, [refreshSummary]);

  const elegibles = useMemo(
    () => (summary?.convocatorias || []).filter((c) => c.puede_postularse === true),
    [summary]
  );
  const noElegibles = useMemo(
    () => (summary?.convocatorias || []).filter((c) => c.puede_postularse === false),
    [summary]
  );
  const sinEvaluar = useMemo(
    () =>
      (summary?.convocatorias || []).filter(
        (c) => c.puede_postularse !== true && c.puede_postularse !== false
      ),
    [summary]
  );

  const selectedMeta =
    summary?.convocatorias.find((c) => c.id === selected) || null;
  const esElegible = selectedMeta?.puede_postularse === true;
  const esNoElegible = selectedMeta?.puede_postularse === false;

  useEffect(() => {
    if (!selectedMeta) return;
    if (selectedMeta.puede_postularse === true) setBrowse("matching");
    else if (selectedMeta.puede_postularse === false) setBrowse("fuera");
    else setBrowse("revisar");
  }, [selectedMeta]);

  const browseList = useMemo(() => {
    if (browse === "fuera") return noElegibles;
    if (browse === "revisar") return sinEvaluar;
    return elegibles;
  }, [browse, elegibles, noElegibles, sinEvaluar]);

  const selectConv = (id: string, mode?: BrowseMode) => {
    if (mode) setBrowse(mode);
    setSelected(id);
  };

  useEffect(() => {
    if (!selected) return;
    setErr(null);
    setRanking(null);
    setActiveProf(null);
    const load = async () => {
      const d = await api<ConvDetail>(`/api/matching/convocatorias/${selected}`);
      setDetail(d);
      const puede = d.elegibilidad_urosario?.puede_postularse === true;
      if (puede && d.tiene_ranking) {
        const r = await api<RankingPayload>(
          `/api/matching/convocatorias/${selected}/ranking?top=12`
        );
        setRanking(r);
        setActiveProf(r.rows[0]?.id ?? null);
      }
    };
    load().catch((e) => setErr(String(e.message || e)));
  }, [selected]);

  const trackJob = async (pollPath: string) => {
    setBusy(true);
    setJobProgress({ fase: "inicio", mensaje: "Arrancando…", hecho: 0, total: 1 });
    try {
      const job = await pollJob(pollPath, (j: JobStatus) => {
        const p = j.progress;
        setJobProgress(p || null);
        const frac =
          p?.total && p.total > 0 ? ` (${p.hecho ?? 0}/${p.total})` : "";
        setJobMsg(`${p?.mensaje || j.status}${frac}`);
      });
      if (job.status === "error") throw new Error(job.error || "Job falló");
      return job;
    } finally {
      setBusy(false);
    }
  };

  const onCalcularFaltantes = async () => {
    setErr(null);
    setSyncResult(null);
    try {
      const start = await apiPost<{ job_id: string; poll: string }>("/api/matching/run", {
        solo_faltantes: true,
        sin_embeddings: false,
        top: 15,
      });
      const job = await trackJob(start.poll);
      setJobMsg(
        `Rankings listos: ${(job.result as { n_procesadas?: number })?.n_procesadas ?? "ok"}`
      );
      await refreshSummary(true);
    } catch (e) {
      setErr(String((e as Error).message || e));
      setJobMsg(null);
    }
  };

  const onCalcularSeleccionada = async () => {
    if (!selected) return;
    setErr(null);
    try {
      const start = await apiPost<{ job_id: string; poll: string }>("/api/matching/run", {
        convocatorias: [selected],
        solo_faltantes: false,
        top: 15,
      });
      await trackJob(start.poll);
      setJobMsg(`Ranking de ${selected} actualizado`);
      await refreshSummary(true);
      const r = await api<RankingPayload>(
        `/api/matching/convocatorias/${selected}/ranking?top=12`
      );
      setRanking(r);
      setActiveProf(r.rows[0]?.id ?? null);
      setDetail((d) => (d ? { ...d, tiene_ranking: true } : d));
    } catch (e) {
      setErr(String((e as Error).message || e));
      setJobMsg(null);
    }
  };

  const onSyncMinciencias = async () => {
    setErr(null);
    setSyncResult(null);
    try {
      const start = await apiPost<{ job_id: string; poll: string }>("/api/minciencias/sync", {
        paginas: 1,
        procesar_nuevas: true,
        matching_si_elegible: true,
        borrar_pdf: true,
        max_nuevas: 3,
        top: 15,
      });
      const job = await trackJob(start.poll);
      const result = (job.result || {}) as Record<string, unknown>;
      setSyncResult(result);
      setJobMsg(String(result.mensaje || "Sync completado"));
      await refreshSummary(true);
    } catch (e) {
      setErr(String((e as Error).message || e));
      setJobMsg(null);
    }
  };

  return (
    <section className="section" style={{ paddingTop: "2rem" }}>
      <p className="section-kicker">Minciencias ↔ Rosario</p>
      <h2>Matching de talento</h2>
      <p className="section-lead">
        Trabaja primero las convocatorias donde Rosario puede postular. Las demás
        quedan aparte, solo con el motivo. Buscar nuevas descarga el TdR, analiza y
        borra el PDF.
      </p>

      <div className="match-toolbar">
        <div className="actions-row" style={{ margin: 0 }}>
          <button className="btn btn-primary" disabled={busy} onClick={onSyncMinciencias}>
            Buscar e ingerir nuevas
          </button>
          <button className="btn btn-ghost" disabled={busy} onClick={onCalcularFaltantes}>
            Rankings faltantes
          </button>
          {esElegible && (
            <button
              className="btn btn-ghost"
              disabled={busy || !selected}
              onClick={onCalcularSeleccionada}
            >
              Recalcular esta
            </button>
          )}
        </div>
        {summary && (
          <p className="match-toolbar-meta note">
            {elegibles.length} para matching · {noElegibles.length} fuera ·{" "}
            {sinEvaluar.length} por revisar
          </p>
        )}
      </div>

      {err && <p className="error">{err}</p>}

      {(busy || jobMsg) && (
        <motion.div
          className={`job-strip ${busy ? "is-busy" : "is-done"}`}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="job-strip-top">
            <span className="job-strip-label">{busy ? "En curso" : "Listo"}</span>
            <span className="job-strip-msg">{jobMsg}</span>
          </div>
          {busy && jobProgress?.total ? (
            <div className="job-strip-bar">
              <i
                style={{
                  width: `${Math.min(
                    100,
                    Math.round(((jobProgress.hecho || 0) / Math.max(jobProgress.total, 1)) * 100)
                  )}%`,
                }}
              />
            </div>
          ) : null}
        </motion.div>
      )}

      {syncResult && (
        <motion.div
          className="sync-report"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="sync-report-head">
            <div>
              <p className="section-kicker" style={{ marginBottom: "0.2rem" }}>
                Búsqueda en Minciencias
              </p>
              <h3>
                {Number(syncResult.n_nuevas || 0) > 0
                  ? `${Number(syncResult.n_nuevas)} nueva${Number(syncResult.n_nuevas) === 1 ? "" : "s"} encontrada${Number(syncResult.n_nuevas) === 1 ? "" : "s"}`
                  : "Sin convocatorias nuevas"}
              </h3>
              <p className="note" style={{ margin: 0 }}>
                {String(syncResult.mensaje || "")}
              </p>
            </div>
            <button type="button" className="tab" onClick={() => setSyncResult(null)}>
              Cerrar
            </button>
          </div>

          <div className="sync-stats">
            <div>
              <strong>{Number(syncResult.n_remotos || 0)}</strong>
              <span>en listado remoto</span>
            </div>
            <div>
              <strong>{Number(syncResult.n_nuevas || 0)}</strong>
              <span>nuevas</span>
            </div>
            <div>
              <strong>{Number(syncResult.n_ya_conocidas || 0)}</strong>
              <span>ya en el sistema</span>
            </div>
            {syncResult.ingest && typeof syncResult.ingest === "object" ? (
              <div>
                <strong>
                  {Number((syncResult.ingest as { n_ok?: number }).n_ok || 0)}/
                  {Number((syncResult.ingest as { n_solicitadas?: number }).n_solicitadas || 0)}
                </strong>
                <span>ingestadas</span>
              </div>
            ) : null}
          </div>

          {Array.isArray((syncResult.ingest as { resultados?: IngestResult[] } | undefined)?.resultados) &&
          ((syncResult.ingest as { resultados: IngestResult[] }).resultados.length > 0) ? (
            <div className="ingest-cards">
              {(syncResult.ingest as { resultados: IngestResult[] }).resultados.map((r, i) => {
                const steps = ingestSteps(r);
                return (
                  <article
                    key={`${r.numero || i}`}
                    className={`ingest-card ${r.ok ? "ok" : "bad"}`}
                  >
                    <div className="ingest-card-head">
                      <div>
                        <h4>
                          #{r.numero || "?"}
                          {r.titulo ? ` · ${String(r.titulo).slice(0, 60)}` : ""}
                        </h4>
                        <p className="note" style={{ margin: 0 }}>
                          {r.puede_postularse === true
                            ? "Elegible · entra a matching"
                            : r.puede_postularse === false
                              ? "No elegible · solo diagnóstico"
                              : r.ok
                                ? "Procesada"
                                : r.error || "Falló la ingesta"}
                        </p>
                      </div>
                      <span className={`ingest-verdict ${r.ok ? "ok" : "bad"}`}>
                        {r.ok ? "Listo" : "Error"}
                      </span>
                    </div>
                    <ol className="ingest-steps">
                      {steps.map((s) => (
                        <li
                          key={s.id}
                          className={`${s.done ? "done" : ""} ${s.muted ? "muted" : ""}`}
                        >
                          {s.label}
                        </li>
                      ))}
                    </ol>
                    {r.resumen_elegibilidad ? (
                      <p className="ingest-summary">{r.resumen_elegibilidad}</p>
                    ) : null}
                    {r.ok && r.numero ? (
                      <button
                        type="button"
                        className="btn btn-ghost"
                        style={{ marginTop: "0.65rem" }}
                        onClick={() =>
                          selectConv(
                            `convocatoria_${r.numero}`,
                            r.puede_postularse === false ? "fuera" : "matching"
                          )
                        }
                      >
                        Abrir convocatoria
                      </button>
                    ) : null}
                  </article>
                );
              })}
            </div>
          ) : Number(syncResult.n_nuevas || 0) > 0 ? (
            <ul className="sync-new-list">
              {(syncResult.nuevas_detalle as { numero: string; titulo: string; url_detalle?: string }[] | undefined)
                ?.slice(0, 8)
                .map((n) => (
                  <li key={n.numero}>
                    <strong>#{n.numero}</strong>
                    <span>{n.titulo}</span>
                    {n.url_detalle ? (
                      <a href={n.url_detalle} target="_blank" rel="noreferrer">
                        Minciencias
                      </a>
                    ) : null}
                  </li>
                ))}
            </ul>
          ) : (
            <p className="note sync-empty">
              El listado remoto no trae números nuevos frente a tu inventario local.
            </p>
          )}
        </motion.div>
      )}

      <div className="browse-shell">
        <div className="browse-segments" role="tablist" aria-label="Tipo de convocatoria">
          {(
            [
              ["matching", "Matching", elegibles.length, "Donde Rosario puede postular"],
              ["fuera", "Fuera de alcance", noElegibles.length, "Solo motivo, sin árbol"],
              ["revisar", "Por revisar", sinEvaluar.length, "Sin veredicto aún"],
            ] as [BrowseMode, string, number, string][]
          ).map(([id, label, count, hint]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={browse === id}
              className={`browse-seg ${browse === id ? "active" : ""} browse-seg-${id}`}
              onClick={() => setBrowse(id)}
            >
              <span className="browse-seg-label">{label}</span>
              <strong>{count}</strong>
              <span className="browse-seg-hint">{hint}</span>
            </button>
          ))}
        </div>

        <div className="browse-panel">
          <div className="browse-panel-head">
            <h3>
              {browse === "matching"
                ? "Convocatorias para matching"
                : browse === "fuera"
                  ? "Fuera de alcance"
                  : "Por revisar"}
            </h3>
            <p className="note" style={{ margin: 0 }}>
              {browse === "matching"
                ? "Elige una del desplegable para ver detalle y el árbol de docentes."
                : browse === "fuera"
                  ? "No generan ranking: solo resumen y por qué no aplican."
                  : "Falta veredicto de elegibilidad o aún no se evaluaron."}
            </p>
          </div>

          {browseList.length === 0 ? (
            <p className="note browse-empty">
              {browse === "matching"
                ? "Todavía no hay elegibles. Busca nuevas o revisa elegibilidad."
                : browse === "fuera"
                  ? "Ninguna marcada como no elegible."
                  : "Nada pendiente de evaluar."}
            </p>
          ) : (
            <div className="select-row browse-select">
              <label htmlFor="conv-browse">
                Convocatoria ({browseList.length})
              </label>
              <select
                id="conv-browse"
                value={browseList.some((c) => c.id === selected) ? selected : ""}
                onChange={(e) => {
                  if (e.target.value) selectConv(e.target.value);
                }}
              >
                <option value="" disabled>
                  Selecciona una convocatoria…
                </option>
                {browseList.map((c) => (
                  <option key={c.id} value={c.id}>
                    #{c.numero}
                    {" — "}
                    {previewTitle(c, 70)}
                    {browse === "matching"
                      ? c.tiene_ranking
                        ? " · ranking listo"
                        : " · ranking pendiente"
                      : ""}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {detail && esNoElegible && (
        <motion.div
          className="panel"
          style={{ marginBottom: "1rem" }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <div className="conv-detail-head">
            <h3>
              #{detail.id.replace("convocatoria_", "")}
              {selectedMeta?.titulo ? ` · ${selectedMeta.titulo.slice(0, 80)}` : ""}
            </h3>
            <span className="status-tag status-no">No elegible</span>
          </div>
          <p className="note">
            {detail.nlp.objetivo
              ? detail.nlp.objetivo.slice(0, 280) +
                (detail.nlp.objetivo.length > 280 ? "…" : "")
              : "Sin objetivo NLP"}
          </p>
          <div
            className={`eleg-box ${
              detail.elegibilidad_urosario?.puede_postularse ? "eleg-ok" : "eleg-no"
            }`}
          >
            <h4>Por qué no es elegible para Rosario</h4>
            <p>
              {detail.elegibilidad_urosario?.resumen ||
                "No hay resumen; revisa los bloqueantes detectados."}
            </p>
            {asTextList(detail.elegibilidad_urosario?.bloqueantes).length > 0 && (
              <>
                <p className="note" style={{ margin: "0.55rem 0 0.35rem" }}>
                  Bloqueantes
                </p>
                <ul className="rosario-list">
                  {asTextList(detail.elegibilidad_urosario?.bloqueantes).map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              </>
            )}
            {asTextList(detail.elegibilidad_urosario?.condiciones_a_verificar).length > 0 && (
              <>
                <p className="note" style={{ margin: "0.55rem 0 0.35rem" }}>
                  Condiciones a verificar
                </p>
                <ul className="rosario-list">
                  {asTextList(detail.elegibilidad_urosario?.condiciones_a_verificar).map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              </>
            )}
          </div>
          <p className="note" style={{ marginTop: "0.75rem", marginBottom: 0 }}>
            No se muestra matching de docentes: la convocatoria no entra en el pool de
            postulación.
          </p>
        </motion.div>
      )}

      {detail && !esNoElegible && (
        <motion.div
          className="panel"
          style={{ marginBottom: "1rem" }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <div className="conv-detail-head">
            <h3>
              Convocatoria {detail.id.replace("convocatoria_", "")}
              {selectedMeta?.titulo ? ` · ${selectedMeta.titulo.slice(0, 80)}` : ""}
            </h3>
            <span
              className={`status-tag ${
                esElegible
                  ? "status-ok"
                  : "status-pending"
              }`}
            >
              {elegibilidadLabel(selectedMeta || {})}
            </span>
          </div>
          <p className="note">
            {detail.nlp.objetivo
              ? detail.nlp.objetivo.slice(0, 420) +
                (detail.nlp.objetivo.length > 420 ? "…" : "")
              : "Sin objetivo NLP"}
          </p>
          <div className="grid-3">
            <div className="kpi">
              <div className="label">Alianza</div>
              <div className="value" style={{ fontSize: "1.3rem" }}>
                {detail.nlp.alianza_obligatoria === true
                  ? "Obligatoria"
                  : detail.nlp.alianza_obligatoria === false
                    ? "No"
                    : "—"}
              </div>
            </div>
            <div className="kpi">
              <div className="label">Elegibilidad Rosario</div>
              <div className="value" style={{ fontSize: "1.3rem" }}>
                {esElegible ? "Puede postular" : elegibilidadLabel(selectedMeta || {})}
              </div>
              <div className="hint">{detail.elegibilidad_urosario?.modo || ""}</div>
            </div>
            <div className="kpi">
              <div className="label">Ranking docentes</div>
              <div className="value" style={{ fontSize: "1.3rem" }}>
                {esElegible
                  ? detail.tiene_ranking
                    ? "Listo"
                    : "Pendiente"
                  : "N/A"}
              </div>
              <div className="hint">
                {esElegible
                  ? ranking
                    ? `pool ${ranking.n_pool}`
                    : "calcular para ver árbol"
                  : "solo tras veredicto elegible"}
              </div>
            </div>
          </div>

          <div className="grid-2" style={{ marginTop: "0.85rem" }}>
            <div>
              <h4 style={{ margin: "0 0 0.35rem", color: "var(--accent)" }}>Quiénes pueden aplicar</h4>
              {asTextList(detail.nlp.actores_elegibles).length > 0 ? (
                <ul className="rosario-list">
                  {asTextList(detail.nlp.actores_elegibles).map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              ) : (
                <p className="note">Sin actores elegibles extraídos.</p>
              )}
              {asTextList(detail.nlp.lineas_tematicas).length > 0 && (
                <>
                  <h4 style={{ margin: "0.75rem 0 0.35rem", color: "var(--accent)" }}>
                    Líneas temáticas
                  </h4>
                  <ul className="rosario-list">
                    {asTextList(detail.nlp.lineas_tematicas, 6).map((l) => (
                      <li key={l}>{l}</li>
                    ))}
                  </ul>
                </>
              )}
            </div>
            <div>
              <h4 style={{ margin: "0 0 0.35rem", color: "var(--accent)" }}>Requisitos clave</h4>
              {asTextList(detail.nlp.requisitos, 6).length > 0 ? (
                <ul className="rosario-list">
                  {asTextList(detail.nlp.requisitos, 6).map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              ) : (
                <p className="note">Sin requisitos listados en NLP.</p>
              )}
            </div>
          </div>

          {detail.elegibilidad_urosario && (
            <div
              className={`eleg-box ${
                detail.elegibilidad_urosario.puede_postularse ? "eleg-ok" : "eleg-no"
              }`}
            >
              <h4>
                {detail.elegibilidad_urosario.puede_postularse
                  ? "Rosario sí encaja como proponente"
                  : "Veredicto de elegibilidad"}
              </h4>
              <p>
                {detail.elegibilidad_urosario.resumen ||
                  (detail.elegibilidad_urosario.puede_postularse
                    ? "El veredicto de elegibilidad es positivo."
                    : "No hay resumen; revisa actores elegibles y bloqueantes.")}
              </p>
              {asTextList(detail.elegibilidad_urosario.bloqueantes).length > 0 && (
                <>
                  <p className="note" style={{ marginBottom: "0.35rem" }}>
                    Bloqueantes detectados
                  </p>
                  <ul className="rosario-list">
                    {asTextList(detail.elegibilidad_urosario.bloqueantes).map((b) => (
                      <li key={b}>{b}</li>
                    ))}
                  </ul>
                </>
              )}
              {asTextList(detail.elegibilidad_urosario.condiciones_a_verificar).length > 0 && (
                <>
                  <p className="note" style={{ margin: "0.55rem 0 0.35rem" }}>
                    Condiciones a verificar
                  </p>
                  <ul className="rosario-list">
                    {asTextList(detail.elegibilidad_urosario.condiciones_a_verificar).map((c) => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                </>
              )}
              {detail.elegibilidad_urosario.rol_sugerido && (
                <p className="note" style={{ marginTop: "0.5rem" }}>
                  Rol sugerido: {asText(detail.elegibilidad_urosario.rol_sugerido)}
                </p>
              )}
            </div>
          )}

          {esElegible && !detail.tiene_ranking && (
            <button
              className="btn btn-primary"
              style={{ marginTop: "0.75rem" }}
              disabled={busy}
              onClick={onCalcularSeleccionada}
            >
              Calcular ranking de esta convocatoria
            </button>
          )}
        </motion.div>
      )}

      {ranking && esElegible && (
        <div style={{ marginBottom: "1rem" }}>
          <MatchTree
            convocatoriaLabel={`Conv. ${detail?.id.replace("convocatoria_", "") || selected.replace("convocatoria_", "")}`}
            objetivo={detail?.nlp.objetivo}
            rows={ranking.rows}
            activeId={activeProf}
            onSelect={setActiveProf}
          />
        </div>
      )}
    </section>
  );
}
