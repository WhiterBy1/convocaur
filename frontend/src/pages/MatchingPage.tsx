import { motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { MatchGraph } from "../components/MatchGraph";
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
  }[];
  grafo: {
    nodes: {
      id: string;
      kind: string;
      label: string;
      score?: number;
      rank?: number;
      aporte?: number;
    }[];
    links: { source: string; target: string; score?: number; kind?: string }[];
  };
};

type ConvDetail = {
  id: string;
  tiene_ranking?: boolean;
  texto_matching: string;
  nlp: { objetivo?: string; alianza_obligatoria?: boolean };
  elegibilidad_urosario?: { puede_postularse?: boolean; modo?: string };
};

type FilterMode = "todas" | "con_ranking" | "sin_ranking" | "elegibles";

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

  const activeRow = useMemo(
    () => ranking?.rows.find((r) => r.id === activeProf) ?? ranking?.rows[0],
    [ranking, activeProf]
  );

  const scoreBars = useMemo(() => {
    if (!activeRow) return [];
    return [
      { name: "Emb ×0.7", aporte: +(0.7 * activeRow.score_emb).toFixed(3) },
      { name: "TF-IDF ×0.3", aporte: +(0.3 * activeRow.score_tfidf).toFixed(3) },
      { name: "Boost", aporte: +activeRow.boost.toFixed(3) },
    ];
  }, [activeRow]);

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
              ? detail.nlp.objetivo.slice(0, 280) +
                (detail.nlp.objetivo.length > 280 ? "…" : "")
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
              <div className="label">Elegibilidad</div>
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
              <div className="label">Ranking</div>
              <div className="value" style={{ fontSize: "1.3rem" }}>
                {detail.tiene_ranking ? "Listo" : "Pendiente"}
              </div>
              <div className="hint">
                {ranking ? `pool ${ranking.n_pool}` : "calcular para ver grafo"}
              </div>
            </div>
          </div>
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
        <div className="grid-2">
          <div>
            <MatchGraph
              grafo={ranking.grafo}
              activeId={activeProf}
              onSelect={(id) => {
                if (ranking.rows.some((r) => r.id === id)) setActiveProf(id);
              }}
            />
          </div>
          <div className="panel">
            <h3>{activeRow?.nombre || activeRow?.id || "Docente"}</h3>
            <p className="note">{activeRow?.facultad}</p>
            <div className="kpi">
              <div className="label">Score final</div>
              <div className="value">{activeRow?.score_final.toFixed(3)}</div>
              <div className="hint">rank #{activeRow?.rank}</div>
            </div>
            <div className="chart-wrap" style={{ height: 200 }}>
              <ResponsiveContainer>
                <BarChart data={scoreBars}>
                  <CartesianGrid stroke="rgba(238,245,240,0.06)" />
                  <XAxis dataKey="name" stroke="#8fa89a" />
                  <YAxis stroke="#8fa89a" />
                  <Tooltip />
                  <Bar dataKey="aporte" fill="#c4a35a" radius={[8, 8, 0, 0]} animationDuration={700} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <ul className="detail-list" style={{ marginTop: "0.75rem" }}>
              {(activeRow?.caracteristicas || [])
                .filter((c) => c.aporte > 0 || c.tipo === "contexto")
                .slice(0, 6)
                .map((c) => (
                  <li key={c.id}>
                    <span>{c.label}</span>
                    <strong>{c.aporte > 0 ? `+${c.aporte.toFixed(3)}` : "—"}</strong>
                  </li>
                ))}
            </ul>
          </div>
        </div>
      )}

      {ranking && (
        <div className="panel" style={{ marginTop: "1rem" }}>
          <h3>Top ranking</h3>
          <ul className="detail-list">
            {ranking.rows.map((r) => (
              <li
                key={r.id}
                style={{
                  cursor: "pointer",
                  outline: r.id === activeProf ? "1px solid #c4a35a" : undefined,
                }}
                onClick={() => setActiveProf(r.id)}
              >
                <span>
                  #{r.rank} {r.nombre || r.id}
                </span>
                <strong>{r.score_final.toFixed(3)}</strong>
                <span className="sub">{r.facultad}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
