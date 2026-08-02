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

type FilterMode = "todas" | "con_ranking" | "sin_ranking" | "elegibles";

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

export function MatchingPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [filter, setFilter] = useState<FilterMode>("todas");
  const [selected, setSelected] = useState<string>("");
  const [ranking, setRanking] = useState<RankingPayload | null>(null);
  const [detail, setDetail] = useState<ConvDetail | null>(null);
  const [activeProf, setActiveProf] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [jobMsg, setJobMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [syncResult, setSyncResult] = useState<Record<string, unknown> | null>(null);

  const refreshSummary = useCallback(async (keepSelected = true) => {
    const s = await api<Summary>("/api/matching/summary");
    setSummary(s);
    setSelected((prev) => {
      if (keepSelected && prev && s.convocatorias.some((c) => c.id === prev)) return prev;
      const preferred =
        s.convocatorias.find((c) => c.tiene_ranking) || s.convocatorias[0];
      return preferred?.id || "";
    });
    return s;
  }, []);

  useEffect(() => {
    refreshSummary(false).catch((e) => setErr(String(e.message || e)));
  }, [refreshSummary]);

  const filtered = useMemo(() => {
    const list = summary?.convocatorias || [];
    if (filter === "con_ranking") return list.filter((c) => c.tiene_ranking);
    if (filter === "sin_ranking") return list.filter((c) => !c.tiene_ranking);
    if (filter === "elegibles") return list.filter((c) => c.puede_postularse === true);
    return list;
  }, [summary, filter]);

  useEffect(() => {
    if (!selected) return;
    setErr(null);
    setRanking(null);
    const load = async () => {
      const d = await api<ConvDetail>(`/api/matching/convocatorias/${selected}`);
      setDetail(d);
      if (d.tiene_ranking) {
        const r = await api<RankingPayload>(
          `/api/matching/convocatorias/${selected}/ranking?top=12`
        );
        setRanking(r);
        setActiveProf(r.rows[0]?.id ?? null);
      } else {
        setRanking(null);
        setActiveProf(null);
      }
    };
    load().catch((e) => setErr(String(e.message || e)));
  }, [selected]);

  const trackJob = async (pollPath: string) => {
    setBusy(true);
    try {
      const job = await pollJob(pollPath, (j: JobStatus) => {
        const p = j.progress;
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
        paginas: 8,
      });
      const job = await trackJob(start.poll);
      const result = (job.result || {}) as Record<string, unknown>;
      setSyncResult(result);
      setJobMsg(String(result.mensaje || "Sync completado"));
    } catch (e) {
      setErr(String((e as Error).message || e));
      setJobMsg(null);
    }
  };

  const selectedMeta = filtered.find((c) => c.id === selected) ||
    summary?.convocatorias.find((c) => c.id === selected);

  return (
    <section className="section" style={{ paddingTop: "2rem" }}>
      <p className="section-kicker">Minciencias ↔ Rosario</p>
      <h2>Matching de talento</h2>
      <p className="section-lead">
        Todas las convocatorias con NLP ({summary?.n_nlp ?? "…"}). Calcula rankings
        faltantes y busca nuevas publicaciones en Minciencias.
      </p>

      {summary && (
        <div className="grid-3" style={{ marginBottom: "1.25rem" }}>
          <div className="kpi">
            <div className="label">Con NLP</div>
            <div className="value">{summary.n_nlp}</div>
          </div>
          <div className="kpi">
            <div className="label">Con ranking</div>
            <div className="value">{summary.n_con_ranking}</div>
            <div className="hint">{summary.n_sin_ranking} pendientes</div>
          </div>
          <div className="kpi">
            <div className="label">Elegibles Rosario</div>
            <div className="value">{summary.n_elegibles}</div>
          </div>
        </div>
      )}

      <div className="actions-row">
        <button className="btn btn-primary" disabled={busy} onClick={onSyncMinciencias}>
          Buscar nuevas en Minciencias
        </button>
        <button className="btn btn-ghost" disabled={busy} onClick={onCalcularFaltantes}>
          Calcular rankings faltantes
        </button>
        <button
          className="btn btn-ghost"
          disabled={busy || !selected}
          onClick={onCalcularSeleccionada}
        >
          Recalcular seleccionada
        </button>
      </div>

      {jobMsg && <p className="job-msg">{busy ? `⏳ ${jobMsg}` : `✓ ${jobMsg}`}</p>}
      {err && <p className="error">{err}</p>}

      {syncResult && (
        <motion.div className="panel" style={{ marginBottom: "1rem" }} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <h3>Resultado del sync</h3>
          <p className="note">{String(syncResult.mensaje || "")}</p>
          <div className="grid-3">
            <div className="kpi">
              <div className="label">En Minciencias</div>
              <div className="value">{Number(syncResult.n_remotos || 0)}</div>
            </div>
            <div className="kpi">
              <div className="label">Nuevas</div>
              <div className="value">{Number(syncResult.n_nuevas || 0)}</div>
            </div>
            <div className="kpi">
              <div className="label">Ya conocidas</div>
              <div className="value">{Number(syncResult.n_ya_conocidas || 0)}</div>
            </div>
          </div>
          {Array.isArray(syncResult.nuevas_detalle) && syncResult.nuevas_detalle.length > 0 && (
            <ul className="detail-list" style={{ marginTop: "0.75rem" }}>
              {(syncResult.nuevas_detalle as { numero: string; titulo: string; url_detalle?: string }[])
                .slice(0, 12)
                .map((n) => (
                  <li key={n.numero}>
                    <span>
                      #{n.numero} {n.titulo}
                    </span>
                    {n.url_detalle ? (
                      <a href={n.url_detalle} target="_blank" rel="noreferrer">
                        ver
                      </a>
                    ) : (
                      <strong>nueva</strong>
                    )}
                  </li>
                ))}
            </ul>
          )}
        </motion.div>
      )}

      <div className="tabs">
        {(
          [
            ["todas", "Todas"],
            ["con_ranking", "Con ranking"],
            ["sin_ranking", "Sin ranking"],
            ["elegibles", "Elegibles"],
          ] as [FilterMode, string][]
        ).map(([id, label]) => (
          <button
            key={id}
            className={`tab ${filter === id ? "active" : ""}`}
            onClick={() => setFilter(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="select-row">
        <label htmlFor="conv">Convocatoria ({filtered.length})</label>
        <select
          id="conv"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          style={{ minWidth: "min(100%, 420px)", maxWidth: "100%" }}
        >
          {filtered.map((c) => (
            <option key={c.id} value={c.id}>
              {c.numero}
              {c.tiene_ranking ? " ●" : " ○"}
              {c.puede_postularse === true ? " ✓" : ""}
              {" — "}
              {(c.titulo || c.objetivo_preview || "sin título").slice(0, 70)}
            </option>
          ))}
        </select>
      </div>

      {detail && (
        <motion.div
          className="panel"
          style={{ marginBottom: "1rem" }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <h3>
            Convocatoria {detail.id.replace("convocatoria_", "")}
            {selectedMeta?.titulo ? ` · ${selectedMeta.titulo.slice(0, 80)}` : ""}
          </h3>
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
              <div className="label">¿Rosario puede postular?</div>
              <div className="value" style={{ fontSize: "1.3rem" }}>
                {detail.elegibilidad_urosario?.puede_postularse === true
                  ? "Sí"
                  : detail.elegibilidad_urosario
                    ? "No"
                    : "N/D"}
              </div>
              <div className="hint">{detail.elegibilidad_urosario?.modo || ""}</div>
            </div>
            <div className="kpi">
              <div className="label">Ranking docentes</div>
              <div className="value" style={{ fontSize: "1.3rem" }}>
                {detail.tiene_ranking ? "Listo" : "Pendiente"}
              </div>
              <div className="hint">
                {ranking ? `pool ${ranking.n_pool}` : "calcular para ver árbol"}
              </div>
            </div>
          </div>

          <div className="grid-2" style={{ marginTop: "0.85rem" }}>
            <div>
              <h4 style={{ margin: "0 0 0.35rem", color: "var(--gold)" }}>Quiénes pueden aplicar</h4>
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
                  <h4 style={{ margin: "0.75rem 0 0.35rem", color: "var(--gold)" }}>
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
              <h4 style={{ margin: "0 0 0.35rem", color: "var(--gold)" }}>Requisitos clave</h4>
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
                  : "Por qué Rosario no podría postularse"}
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

          {!detail.tiene_ranking && (
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

      {ranking && (
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
