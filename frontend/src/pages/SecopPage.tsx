import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../lib/api";

type Dashboard = {
  meta: Record<string, string>;
  universo: Record<string, number | string>;
  capacidad_1: {
    titulo: string;
    unspsc_mix: { codigo: string; nombre: string; pct: number }[];
    fondos_administrados: { n_procesos: number; pct_valor: number; nota: string };
    estacionalidad: {
      kruskal_h: number;
      kruskal_p: number;
      stl_fuerza_estacional: number;
      spearman_rho_rango: number[];
      lectura: string;
    };
    serie_ilustrativa: {
      periodo: string;
      n_index: number;
      valor_index: number;
      valor_sin_fondos_index: number;
    }[];
    nota_serie: string;
  };
  capacidad_2: {
    titulo: string;
    hhi: { antes_outliers: number; despues_correccion: number; lectura: string };
    pareto: {
      proveedores_80pct_valor: number;
      proveedores_total: number;
      pct_proveedores: number;
    };
    nichos_hhi_ejemplo: { entidad: string; hhi: number }[];
    rotacion: string;
    siguiente_mejora: string;
  };
  capacidad_3: {
    titulo: string;
    adjudicacion_competitivo: Record<string, number | string | boolean>;
    adjudicacion_solo_resueltos: Record<string, number | string | boolean>;
    presupuesto_bins: Record<string, number | string | string[]>;
    segmento_unspsc: Record<string, number | string | string[]>;
    comparativo_modelos: {
      tarea: string;
      metrica: string;
      valor: number;
      baseline: number | null;
    }[];
  };
};

export function SecopPage() {
  const [tab, setTab] = useState<1 | 2 | 3>(1);
  const [data, setData] = useState<Dashboard | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api<Dashboard>("/api/secop/dashboard")
      .then(setData)
      .catch((e) => setErr(String(e.message || e)));
  }, []);

  if (err) return <p className="error">{err}</p>;
  if (!data) return <p className="loading">Cargando análisis SECOP…</p>;

  const mix = data.capacidad_1.unspsc_mix.map((u) => ({
    codigo: u.codigo,
    pct: Math.round(u.pct * 1000) / 10,
    nombre: u.nombre,
  }));

  const hhiBars = [
    { etapa: "Con outliers", hhi: data.capacidad_2.hhi.antes_outliers },
    { etapa: "Corregido", hhi: data.capacidad_2.hhi.despues_correccion },
  ];

  const modelBars = data.capacidad_3.comparativo_modelos.map((m) => ({
    tarea: m.tarea.replace("Adjudicación ", "Adj. "),
    valor: Math.round(m.valor * 1000) / 10,
    baseline: m.baseline != null ? Math.round(m.baseline * 1000) / 10 : null,
    metrica: m.metrica,
  }));

  return (
    <section className="section" style={{ paddingTop: "2rem" }}>
      <p className="section-kicker">SECOP II · proxy CTeI</p>
      <h2>Tres capacidades del reto</h2>
      <p className="section-lead">
        {data.meta.universo} · {data.meta.fuente}. Cortes y cifras alineados a
        notebooks y bitácora Cap.3.
      </p>

      <div className="grid-3" style={{ marginBottom: "1.25rem" }}>
        <div className="kpi">
          <div className="label">Procesos filtrados</div>
          <div className="value">
            {Number(data.universo.n_procesos_total).toLocaleString("es-CO")}
          </div>
        </div>
        <div className="kpi">
          <div className="label">Competitivos</div>
          <div className="value">
            {Number(data.universo.n_competitivos).toLocaleString("es-CO")}
          </div>
          <div className="hint">
            ~{Math.round(Number(data.universo.pct_competitivos) * 100)}% del
            universo
          </div>
        </div>
        <div className="kpi">
          <div className="label">Tasa adj. competitivos</div>
          <div className="value">
            {(Number(data.universo.tasa_adjudicacion_competitivos) * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      <div className="tabs">
        {([1, 2, 3] as const).map((n) => (
          <button
            key={n}
            className={`tab ${tab === n ? "active" : ""}`}
            onClick={() => setTab(n)}
          >
            Capacidad {n}
          </button>
        ))}
      </div>

      {tab === 1 && (
        <motion.div
          className="grid-2"
          key="c1"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="panel">
            <h3>{data.capacidad_1.titulo}</h3>
            <p className="note">{data.capacidad_1.nota_serie}</p>
            <div className="chart-wrap tall">
              <ResponsiveContainer>
                <LineChart data={data.capacidad_1.serie_ilustrativa}>
                  <CartesianGrid stroke="rgba(238,245,240,0.06)" />
                  <XAxis dataKey="periodo" stroke="#8fa89a" />
                  <YAxis stroke="#8fa89a" />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="n_index"
                    name="Volumen"
                    stroke="#3dcfb0"
                    strokeWidth={2.5}
                    dot={{ r: 3 }}
                    animationDuration={1000}
                  />
                  <Line
                    type="monotone"
                    dataKey="valor_index"
                    name="Valor real"
                    stroke="#c4a35a"
                    strokeWidth={2.5}
                    animationDuration={1100}
                  />
                  <Line
                    type="monotone"
                    dataKey="valor_sin_fondos_index"
                    name="Valor s/ fondos"
                    stroke="#e07a5f"
                    strokeWidth={2}
                    strokeDasharray="5 4"
                    animationDuration={1200}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="panel">
            <h3>Mix UNSPSC y estacionalidad</h3>
            <div className="chart-wrap">
              <ResponsiveContainer>
                <BarChart data={mix}>
                  <CartesianGrid stroke="rgba(238,245,240,0.06)" />
                  <XAxis dataKey="codigo" stroke="#8fa89a" />
                  <YAxis stroke="#8fa89a" unit="%" />
                  <Tooltip
                    formatter={(v: number, _n, p) => [
                      `${v}%`,
                      (p?.payload as { nombre?: string })?.nombre || "Share",
                    ]}
                  />
                  <Bar dataKey="pct" fill="#3dcfb0" radius={[8, 8, 0, 0]} animationDuration={900} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <ul className="detail-list" style={{ marginTop: "1rem" }}>
              <li>
                <span>Fondos administrados</span>
                <strong>
                  {(data.capacidad_1.fondos_administrados.pct_valor * 100).toFixed(1)}%
                  valor
                </strong>
                <span className="sub">
                  {data.capacidad_1.fondos_administrados.n_procesos} megacontratos ·{" "}
                  {data.capacidad_1.fondos_administrados.nota}
                </span>
              </li>
              <li>
                <span>Kruskal-Wallis</span>
                <strong>H={data.capacidad_1.estacionalidad.kruskal_h}</strong>
                <span className="sub">{data.capacidad_1.estacionalidad.lectura}</span>
              </li>
              <li>
                <span>STL fuerza estacional</span>
                <strong>{data.capacidad_1.estacionalidad.stl_fuerza_estacional}</strong>
              </li>
              <li>
                <span>Spearman entre años</span>
                <strong>
                  ρ {data.capacidad_1.estacionalidad.spearman_rho_rango.join("–")}
                </strong>
              </li>
            </ul>
          </div>
        </motion.div>
      )}

      {tab === 2 && (
        <motion.div
          className="grid-2"
          key="c2"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="panel">
            <h3>{data.capacidad_2.titulo}</h3>
            <p className="note">{data.capacidad_2.hhi.lectura}</p>
            <div className="chart-wrap">
              <ResponsiveContainer>
                <BarChart data={hhiBars} layout="vertical" margin={{ left: 20 }}>
                  <CartesianGrid stroke="rgba(238,245,240,0.06)" />
                  <XAxis type="number" stroke="#8fa89a" />
                  <YAxis type="category" dataKey="etapa" stroke="#8fa89a" width={100} />
                  <Tooltip />
                  <Bar dataKey="hhi" fill="#c4a35a" radius={[0, 8, 8, 0]} animationDuration={1000} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="grid-2" style={{ marginTop: "1rem" }}>
              <div className="kpi">
                <div className="label">Pareto 80% valor</div>
                <div className="value">
                  {data.capacidad_2.pareto.proveedores_80pct_valor.toLocaleString("es-CO")}
                </div>
                <div className="hint">
                  de {data.capacidad_2.pareto.proveedores_total.toLocaleString("es-CO")} (
                  {(data.capacidad_2.pareto.pct_proveedores * 100).toFixed(1)}%)
                </div>
              </div>
              <div className="kpi">
                <div className="label">HHI de mercado</div>
                <div className="value">{data.capacidad_2.hhi.despues_correccion}</div>
                <div className="hint">poco concentrado a nivel agregado</div>
              </div>
            </div>
          </div>
          <div className="panel">
            <h3>Nichos vs agregado</h3>
            <p className="note">{data.capacidad_2.rotacion}</p>
            <div className="chart-wrap">
              <ResponsiveContainer>
                <BarChart data={data.capacidad_2.nichos_hhi_ejemplo}>
                  <CartesianGrid stroke="rgba(238,245,240,0.06)" />
                  <XAxis dataKey="entidad" stroke="#8fa89a" tick={{ fontSize: 11 }} interval={0} angle={-12} textAnchor="end" height={70} />
                  <YAxis stroke="#8fa89a" />
                  <Tooltip />
                  <Bar dataKey="hhi" fill="#e07a5f" radius={[8, 8, 0, 0]} animationDuration={900} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="note" style={{ marginTop: "1rem" }}>
              {data.capacidad_2.siguiente_mejora}
            </p>
          </div>
        </motion.div>
      )}

      {tab === 3 && (
        <motion.div
          className="grid-2"
          key="c3"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="panel">
            <h3>{data.capacidad_3.titulo}</h3>
            <p className="note">
              Split temporal {String(data.meta.fecha_corte_modelo)}. Usar en vivo
              solo el modelo competitivo (AUC{" "}
              {(Number(data.capacidad_3.adjudicacion_competitivo.auc_roc) * 100).toFixed(1)}
              %).
            </p>
            <div className="chart-wrap tall">
              <ResponsiveContainer>
                <BarChart data={modelBars} margin={{ bottom: 40 }}>
                  <CartesianGrid stroke="rgba(238,245,240,0.06)" />
                  <XAxis dataKey="tarea" stroke="#8fa89a" tick={{ fontSize: 11 }} interval={0} angle={-18} textAnchor="end" />
                  <YAxis stroke="#8fa89a" unit="%" />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="valor" name="Modelo" fill="#3dcfb0" radius={[8, 8, 0, 0]} animationDuration={1000} />
                  <Bar dataKey="baseline" name="Trivial" fill="#8fa89a" radius={[8, 8, 0, 0]} animationDuration={1100} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="panel">
            <h3>Lectura operativa</h3>
            <ul className="detail-list">
              <li>
                <span>LightGBM competitivo</span>
                <strong>
                  AUC {(Number(data.capacidad_3.adjudicacion_competitivo.auc_roc) * 100).toFixed(1)}%
                </strong>
                <span className="sub">
                  {String(data.capacidad_3.adjudicacion_competitivo.lectura)} · train{" "}
                  {Number(data.capacidad_3.adjudicacion_competitivo.n_train).toLocaleString("es-CO")}
                </span>
              </li>
              <li>
                <span>Solo resueltos</span>
                <strong>
                  AUC {(Number(data.capacidad_3.adjudicacion_solo_resueltos.auc_roc) * 100).toFixed(1)}%
                </strong>
                <span className="sub">
                  {String(data.capacidad_3.adjudicacion_solo_resueltos.lectura)}
                </span>
              </li>
              <li>
                <span>Presupuesto Q1–Q4</span>
                <strong>
                  {(Number(data.capacidad_3.presupuesto_bins.acc_modelo) * 100).toFixed(1)}%
                  vs trivial{" "}
                  {(Number(data.capacidad_3.presupuesto_bins.acc_trivial) * 100).toFixed(1)}%
                </strong>
              </li>
              <li>
                <span>Segmento 80/81/86</span>
                <strong>
                  {(Number(data.capacidad_3.segmento_unspsc.acc_modelo) * 100).toFixed(1)}%
                  vs trivial{" "}
                  {(Number(data.capacidad_3.segmento_unspsc.acc_trivial) * 100).toFixed(1)}%
                </strong>
                <span className="sub">{String(data.capacidad_3.segmento_unspsc.lectura)}</span>
              </li>
            </ul>
          </div>
        </motion.div>
      )}
    </section>
  );
}
