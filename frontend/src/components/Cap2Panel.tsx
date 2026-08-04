import { Component, type ReactNode, lazy, Suspense } from "react";
import { motion } from "framer-motion";
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
import { formatCop, formatCopShort } from "../lib/format";
import type { RedMercado } from "./Cap2NetworkGraph";
import { Cap2RosarioInsights, type AnalisisRosario } from "./Cap2RosarioInsights";

const Cap2NetworkGraph = lazy(() =>
  import("./Cap2NetworkGraph").then((m) => ({ default: m.Cap2NetworkGraph }))
);

export type Capacidad2 = {
  titulo: string;
  subtitulo?: string;
  kpis?: {
    hhi_antes: number;
    hhi_despues: number;
    nivel_concentracion: string;
    proveedores_80pct_valor: number;
    proveedores_total: number;
    pct_proveedores_80: number;
  };
  hhi?: {
    antes_outliers: number;
    despues_correccion: number;
    lectura: string;
    guia?: { rango: string; significado: string }[];
  };
  pareto?: {
    proveedores_80pct_valor: number;
    proveedores_total: number;
    pct_proveedores: number;
    lectura?: string;
    curva?: { pct_proveedores: number; pct_valor: number }[];
  };
  top_proveedores?: {
    nombre: string;
    valor_cop: number;
    participacion_pct: number;
  }[];
  nichos_concentrados?: {
    entidad: string;
    hhi: number;
    proveedores: number;
    procesos: number;
    valor_total_cop?: number;
  }[];
  nichos_hhi_ejemplo?: { entidad: string; hhi: number }[];
  rotacion_anual?: {
    anio: number;
    n_proveedores: number;
    top1_participacion_pct: number;
    jaccard_top50_vs_anio_prev_pct: number | null;
  }[];
  rotacion?: string;
  rotacion_lectura?: string;
  siguiente_mejora?: string;
  cierre_rosario?: { titulo: string; puntos: string[] };
  nota_metodologica?: string;
  red_mercado?: RedMercado;
  red_ego_rosario?: RedMercado;
  analisis_rosario?: AnalisisRosario;
};

class GraphErrorBoundary extends Component<
  { children: ReactNode },
  { error: string | null }
> {
  state = { error: null as string | null };
  static getDerivedStateFromError(err: Error) {
    return { error: err?.message || "Error en el grafo" };
  }
  render() {
    if (this.state.error) {
      return (
        <div className="panel" style={{ marginBottom: "1rem" }}>
          <h3>Red del mercado</h3>
          <p className="error">No se pudo renderizar el grafo: {this.state.error}</p>
          <p className="note">El resto de Cap.2 sigue disponible abajo.</p>
        </div>
      );
    }
    return this.props.children;
  }
}

type Props = { data: Capacidad2 };

export function Cap2Panel({ data }: Props) {
  const k = data.kpis;
  const hhi = data.hhi;
  const pareto = data.pareto;
  const hhiBars = hhi
    ? [
        { etapa: "Sin limpiar datos", hhi: hhi.antes_outliers, fill: "#e8917a" },
        { etapa: "Datos corregidos", hhi: hhi.despues_correccion, fill: "#e2b86a" },
      ]
    : [];
  const curva = pareto?.curva || [];
  const top = (data.top_proveedores || []).slice(0, 10).map((p) => ({
    nombre: p.nombre.length > 36 ? p.nombre.slice(0, 34) + "…" : p.nombre,
    valor: p.valor_cop,
    pct: p.participacion_pct,
  }));
  const nichos = (data.nichos_concentrados || data.nichos_hhi_ejemplo || []).slice(0, 6);
  const rotacion = data.rotacion_anual || [];
  const rotLectura = data.rotacion_lectura || data.rotacion || "";

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
      <div className="panel" style={{ marginBottom: "1rem" }}>
        <h3>{data.titulo || "Mercado"}</h3>
        <p className="note">{data.subtitulo}</p>
        {k && (
          <div className="grid-3">
            <div className="kpi">
              <div className="label">¿Qué tan concentrado está?</div>
              <div className="value">{k.hhi_despues.toLocaleString("es-CO")}</div>
              <div className="hint">
                índice de concentración ({k.nivel_concentracion}) · escala hasta 10.000
              </div>
            </div>
            <div className="kpi">
              <div className="label">Para el 80% del dinero</div>
              <div className="value">{k.proveedores_80pct_valor.toLocaleString("es-CO")}</div>
              <div className="hint">
                proveedores de {k.proveedores_total.toLocaleString("es-CO")} (
                {k.pct_proveedores_80}%)
              </div>
            </div>
            <div className="kpi">
              <div className="label">Si no se limpian errores</div>
              <div className="value">{k.hhi_antes.toLocaleString("es-CO")}</div>
              <div className="hint">parece monopolio — es un artefacto de datos</div>
            </div>
          </div>
        )}
      </div>

      {hhi && (
        <div className="grid-2">
          <div className="panel">
            <h3>¿El mercado es de pocos o de muchos?</h3>
            <p className="note">{hhi.lectura}</p>
            <div className="chart-wrap">
              <ResponsiveContainer>
                <BarChart data={hhiBars} layout="vertical" margin={{ left: 8, right: 12 }}>
                  <CartesianGrid stroke="rgba(233,238,244,0.14)" />
                  <XAxis type="number" stroke="#a8b6c4" domain={[0, 10000]} />
                  <YAxis
                    type="category"
                    dataKey="etapa"
                    width={120}
                    stroke="#a8b6c4"
                    tick={{ fontSize: 12 }}
                  />
                  <Tooltip
                    formatter={(v: number) => [
                      Number(v).toLocaleString("es-CO"),
                      "Concentración",
                    ]}
                  />
                  <Bar dataKey="hhi" fill="#6fd0bc" radius={[0, 8, 8, 0]} animationDuration={900} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            {hhi.guia && (
              <ul className="detail-list" style={{ marginTop: "0.75rem" }}>
                {hhi.guia.map((g) => (
                  <li key={g.rango}>
                    <span>{g.rango}</span>
                    <strong style={{ fontWeight: 500, fontSize: "0.85rem" }}>
                      {g.significado}
                    </strong>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="panel">
            <h3>¿Cuántos se necesitan para el 80% del valor?</h3>
            <p className="note">
              {pareto?.lectura ||
                "Curva de Pareto: qué porcentaje de proveedores acumula qué porcentaje del dinero."}
            </p>
            <div className="chart-wrap">
              <ResponsiveContainer>
                <LineChart data={curva}>
                  <CartesianGrid stroke="rgba(233,238,244,0.14)" />
                  <XAxis
                    dataKey="pct_proveedores"
                    stroke="#a8b6c4"
                    unit="%"
                    label={{
                      value: "% proveedores",
                      position: "insideBottom",
                      offset: -2,
                      fill: "#8fa89a",
                      fontSize: 11,
                    }}
                  />
                  <YAxis stroke="#a8b6c4" unit="%" domain={[0, 100]} />
                  <Tooltip
                    formatter={(v: number) => [`${v}%`, "% del valor"]}
                    labelFormatter={(l) => `${l}% de proveedores`}
                  />
                  <Line
                    type="monotone"
                    dataKey="pct_valor"
                    name="% del valor adjudicado"
                    stroke="#e2b86a"
                    strokeWidth={2.4}
                    dot={false}
                    animationDuration={1000}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      <div className="grid-2" style={{ marginTop: "1rem" }}>
        <div className="panel">
          <h3>Quiénes concentran más valor (top 10)</h3>
          <p className="note">Proveedores con mayor valor adjudicado ya corregido.</p>
          <div className="chart-wrap tall">
            <ResponsiveContainer>
              <BarChart data={top} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid stroke="rgba(233,238,244,0.14)" />
                <XAxis
                  type="number"
                  stroke="#a8b6c4"
                  tickFormatter={(v) => formatCopShort(Number(v))}
                />
                <YAxis
                  type="category"
                  dataKey="nombre"
                  width={140}
                  stroke="#a8b6c4"
                  tick={{ fontSize: 10 }}
                />
                <Tooltip
                  formatter={(v: number, _n, p) => [
                    `${formatCop(Number(v))} (${(p?.payload as { pct?: number })?.pct ?? ""}%)`,
                    "Valor",
                  ]}
                />
                <Bar dataKey="valor" fill="#6fd0bc" radius={[0, 8, 8, 0]} animationDuration={900} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel">
          <h3>Nichos: entidades muy concentradas</h3>
          <p className="note">
            Aunque el país se ve competitivo, algunos compradores casi siempre contratan a
            los mismos. (Mín. 20 procesos.)
          </p>
          <div className="chart-wrap tall">
            <ResponsiveContainer>
              <BarChart
                data={nichos.map((n) => ({
                  entidad: n.entidad.length > 40 ? n.entidad.slice(0, 38) + "…" : n.entidad,
                  hhi: n.hhi,
                }))}
              >
                <CartesianGrid stroke="rgba(233,238,244,0.14)" />
                <XAxis
                  dataKey="entidad"
                  stroke="#a8b6c4"
                  tick={{ fontSize: 10 }}
                  interval={0}
                  angle={-18}
                  textAnchor="end"
                  height={80}
                />
                <YAxis stroke="#a8b6c4" domain={[0, 10000]} />
                <Tooltip />
                <Bar
                  dataKey="hhi"
                  name="Concentración"
                  fill="#e8917a"
                  radius={[8, 8, 0, 0]}
                  animationDuration={900}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {rotacion.length > 0 && (
        <div className="panel" style={{ marginTop: "1rem" }}>
          <h3>¿Se repiten los mismos ganadores cada año?</h3>
          <p className="note">{rotLectura}</p>
          <div className="chart-wrap">
            <ResponsiveContainer>
              <LineChart data={rotacion}>
                <CartesianGrid stroke="rgba(233,238,244,0.14)" />
                <XAxis dataKey="anio" stroke="#a8b6c4" />
                <YAxis stroke="#a8b6c4" unit="%" domain={[0, 100]} />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="jaccard_top50_vs_anio_prev_pct"
                  name="Similitud top-50 vs año anterior"
                  stroke="#e2b86a"
                  strokeWidth={2.4}
                  connectNulls={false}
                  animationDuration={1000}
                />
                <Line
                  type="monotone"
                  dataKey="top1_participacion_pct"
                  name="Peso del #1 ese año"
                  stroke="#6fd0bc"
                  strokeWidth={2}
                  animationDuration={1100}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {data.analisis_rosario?.perfil ? (
        <Cap2RosarioInsights data={data.analisis_rosario} />
      ) : null}

      {/* Grafo al final + lazy + boundary: si falla, Cap.2 no queda en blanco */}
      {data.red_mercado?.nodes?.length || data.red_ego_rosario?.nodes?.length ? (
        <div style={{ marginTop: "1rem" }}>
          <GraphErrorBoundary>
            <Suspense
              fallback={
                <div className="panel">
                  <p className="loading">Cargando red del mercado…</p>
                </div>
              }
            >
              <Cap2NetworkGraph
                red={data.red_ego_rosario || data.red_mercado!}
                vistas={[
                  ...(data.red_ego_rosario?.nodes?.length
                    ? [
                        {
                          id: "ego",
                          label: "Ego Rosario (completo)",
                          red: data.red_ego_rosario,
                        },
                      ]
                    : []),
                  ...(data.red_mercado?.nodes?.length
                    ? [
                        {
                          id: "mercado",
                          label: "Mercado (muestra amplia)",
                          red: data.red_mercado,
                        },
                      ]
                    : []),
                ]}
              />
            </Suspense>
          </GraphErrorBoundary>
        </div>
      ) : null}

      {data.cierre_rosario && !data.analisis_rosario?.lecturas?.length && (
        <div className="panel panel-rosario" style={{ marginTop: "1rem" }}>
          <h3>{data.cierre_rosario.titulo}</h3>
          <ul className="rosario-list">
            {data.cierre_rosario.puntos.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
          {data.nota_metodologica && (
            <details className="method-note">
              <summary>¿Cómo se calculó? (detalle técnico)</summary>
              <p>{data.nota_metodologica}</p>
            </details>
          )}
        </div>
      )}
    </motion.div>
  );
}
