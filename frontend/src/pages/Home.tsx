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

const COLORS = ["#3dcfb0", "#c4a35a", "#e07a5f"];

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
        <motion.p
          className="section-kicker"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          Contratación pública · talento CTeI
        </motion.p>
        <motion.h1
          className="hero-brand"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.05 }}
        >
          Convoca<em>UR</em>
        </motion.h1>
        <motion.p
          className="hero-lead"
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, delay:.15 }}
        >
          Lee el mercado SECOP filtrado a CTeI y conecta convocatorias Minciencias
          con el cuerpo docente de Rosario — con evidencia, no con intuición.
        </motion.p>
        <motion.div
          className="cta-row"
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.28 }}
        >
          <Link className="btn btn-primary" to="/secop">
            Explorar SECOP
          </Link>
          <Link className="btn btn-ghost" to="/matching">
            Abrir matching
          </Link>
        </motion.div>
      </section>

      <section className="section">
        <p className="section-kicker">Panorama</p>
        <h2>Dos vías, una decisión</h2>
        <p className="section-lead">
          Cap. 1–3 del reto sobre SECOP, y la herramienta de match sobre TdR +
          CvLAC. Todo servido por API Python y visualizado aquí.
        </p>

        {err && <p className="error">API: {err}. Arranca el backend en :8000.</p>}
        {!data && !err && <p className="loading">Cargando overview…</p>}

        {data && (
          <div className="grid-2">
            <motion.div
              className="panel"
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.45 }}
            >
              <h3>SECOP CTeI</h3>
              <p className="note">
                Universo UNSPSC 80/81/86 · IPC DANE · modelos Cap.3 en disco
              </p>
              <div className="grid-3">
                <div className="kpi">
                  <div className="label">Procesos</div>
                  <div className="value">
                    {(data.secop_resumen.universo?.n_procesos_total ?? 0).toLocaleString("es-CO")}
                  </div>
                </div>
                <div className="kpi">
                  <div className="label">AUC adjudicación</div>
                  <div className="value">
                    {((data.secop_resumen.cap3_auc ?? 0) * 100).toFixed(1)}%
                  </div>
                </div>
                <div className="kpi">
                  <div className="label">HHI corregido</div>
                  <div className="value">{data.secop_resumen.hhi_corregido}</div>
                </div>
              </div>
              <div className="chart-wrap" style={{ height: 220 }}>
                <ResponsiveContainer>
                  <PieChart>
                    <Pie
                      data={mix}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={55}
                      outerRadius={85}
                      paddingAngle={3}
                      animationDuration={900}
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
              </div>
              <Link className="btn btn-ghost" to="/secop" style={{ marginTop: "0.5rem" }}>
                Ver capacidades →
              </Link>
            </motion.div>

            <motion.div
              className="panel"
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.45, delay: 0.08 }}
            >
              <h3>Matching Rosario</h3>
              <p className="note">
                Score híbrido embeddings + TF-IDF · piloto sobre convocatorias
                elegibles
              </p>
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
                  <div className="label">Con CvLAC</div>
                  <div className="value">{data.stats.con_cvlac_approx}</div>
                </div>
              </div>
              <div className="kpi" style={{ marginTop: "1rem" }}>
                <div className="label">Embeddings en cache</div>
                <div className="value">
                  {data.matching_resumen.n_cache_embeddings}
                </div>
                <div className="hint">
                  {data.matching_resumen.convocatorias.length} rankings listos
                </div>
              </div>
              <Link className="btn btn-ghost" to="/matching" style={{ marginTop: "0.75rem" }}>
                Explorar grafo →
              </Link>
            </motion.div>
          </div>
        )}
      </section>
    </>
  );
}
