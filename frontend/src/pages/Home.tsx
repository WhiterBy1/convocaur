import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { ChartInView } from "../components/ChartInView";
import { api } from "../lib/api";

type Overview = {
  brand: string;
  tagline: string;
  stats: {
    nlp_convocatorias: number;
    elegibilidad: number;
    docentes_json: number;
    sin_cvlac: number;
    con_cvlac_approx: number;
  };
  secop_resumen: {
    universo: { n_procesos_total: number; n_competitivos: number };
    cap3_auc: number;
    hhi_corregido: number;
    unspsc_mix: { codigo: string; nombre: string; pct: number }[];
  };
  matching_resumen: {
    n_cache_embeddings: number;
    convocatorias: { id: string }[];
  };
};

const COLORS = ["#3e4b8e", "#a6bcc9", "#6b7dbd"];

export function Home() {
  const [data, setData] = useState<Overview | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api<Overview>("/api/overview")
      .then(setData)
      .catch((e) => setErr(String(e.message || e)));
  }, []);

  const mix =
    data?.secop_resumen?.unspsc_mix?.map((u) => ({
      name: u.codigo,
      value: Math.round(u.pct * 1000) / 10,
      full: u.nombre,
    })) ?? [];

  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <motion.p
            className="hero-kicker"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            SECOP · Minciencias · Rosario
          </motion.p>
          <motion.h1
            className="hero-brand"
            initial={{ opacity: 0, y: 22 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          >
            Convoca<em>UR</em>
          </motion.h1>
          <motion.p
            className="hero-lead"
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            Mercado SECOP–CTeI y matching docente: evidencia clara para decidir
            qué conviene seguir.
          </motion.p>
          <motion.div
            className="cta-row"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, delay: 0.18 }}
          >
            <Link className="btn btn-primary" to="/secop">
              Abrir SECOP
            </Link>
            <Link className="btn btn-ghost" to="/matching">
              Abrir matching
            </Link>
          </motion.div>
        </div>
        <motion.div
          className="hero-stage"
          initial={{ opacity: 0, x: 28 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.75, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          aria-hidden="true"
        >
          <div className="hero-blob" />
          <div className="hero-dots" />
          <div className="hero-plane" />
          <div className="hero-ring" />
          <img
            className="hero-figure"
            src="/brand/hero-figure.png"
            alt=""
          />
        </motion.div>
      </section>

      <section className="section">
        <h2>Estado del expediente</h2>
        <p className="section-lead">
          Lectura rápida del universo cargado. Entrá a SECOP o Matching para
          trabajar.
        </p>

        {err && <p className="error">API: {err}. Arranca el backend en :8000.</p>}
        {!data && !err && <p className="loading">Cargando overview…</p>}

        {data && (
          <div className="grid-2">
            <div className="panel panel-rosario">
              <h3>SECOP CTeI</h3>
              <div className="grid-3">
                <div className="kpi">
                  <div className="label">Procesos</div>
                  <div className="value">
                    {(data.secop_resumen.universo?.n_procesos_total ?? 0).toLocaleString("es-CO")}
                  </div>
                </div>
                <div className="kpi">
                  <div className="label">AUC adj.</div>
                  <div className="value">
                    {((data.secop_resumen.cap3_auc ?? 0) * 100).toFixed(1)}%
                  </div>
                </div>
                <div className="kpi">
                  <div className="label">HHI</div>
                  <div className="value">{data.secop_resumen.hhi_corregido}</div>
                </div>
              </div>
              <ChartInView className="chart-wrap" style={{ height: 200 }}>
                <ResponsiveContainer>
                  <PieChart>
                    <Pie
                      data={mix}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={48}
                      outerRadius={76}
                      paddingAngle={2}
                      animationBegin={80}
                      animationDuration={1100}
                    >
                      {mix.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(v: number, _n, p) => [
                        `${v}%`,
                        (p?.payload as { full?: string })?.full || "UNSPSC",
                      ]}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </ChartInView>
              <Link className="btn btn-ghost" to="/secop" style={{ marginTop: "0.5rem" }}>
                Capacidades →
              </Link>
            </div>

            <div className="panel panel-rosario">
              <h3>Matching Rosario</h3>
              <div className="grid-3">
                <div className="kpi">
                  <div className="label">NLP</div>
                  <div className="value">{data.stats.nlp_convocatorias}</div>
                </div>
                <div className="kpi">
                  <div className="label">Docentes</div>
                  <div className="value">{data.stats.docentes_json}</div>
                </div>
                <div className="kpi">
                  <div className="label">CvLAC</div>
                  <div className="value">{data.stats.con_cvlac_approx}</div>
                </div>
              </div>
              <ul className="rosario-list hallazgos" style={{ marginTop: "1rem" }}>
                <li>
                  {data.matching_resumen.n_cache_embeddings} embeddings ·{" "}
                  {data.matching_resumen.convocatorias?.length ?? 0} convocatorias en matching
                </li>
                <li>
                  Elegibilidad evaluada en {data.stats.elegibilidad} convocatorias
                </li>
              </ul>
              <Link className="btn btn-ghost" to="/matching" style={{ marginTop: "0.5rem" }}>
                Ir a matching →
              </Link>
            </div>
          </div>
        )}
      </section>
    </>
  );
}
