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
import { ChartInView } from "./ChartInView";

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
    top1_nombre?: string;
    top1_valor_cop?: number;
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

function shortLabel(s: string, n = 28) {
  const t = (s || "").trim().replace(/\s+/g, " ");
  if (t.length <= n) return t;
  return `${t.slice(0, Math.max(1, n - 1)).trimEnd()}…`;
}

function CatTick(props: {
  x?: number;
  y?: number;
  payload?: { value?: string | number };
}) {
  const { x = 0, y = 0, payload } = props;
  const raw = String(payload?.value ?? "");
  // Recorta al inicio visible: evita que el SVG recorte el comienzo del nombre.
  const max = 26;
  const label = raw.length > max ? `${raw.slice(0, max - 1)}…` : raw;
  return (
    <text
      x={x}
      y={y}
      dy={4}
      textAnchor="end"
      fill="#3d1534"
      fontSize={11}
      fontFamily='"Source Sans 3", "Segoe UI", sans-serif'
    >
      <title>{raw}</title>
      {label}
    </text>
  );
}

export function Cap2Panel({ data }: Props) {
  const k = data.kpis;
  const hhi = data.hhi;
  const pareto = data.pareto;
  const hhiBars = hhi
    ? [
        { etapa: "Sin limpiar datos", hhi: hhi.antes_outliers, fill: "#8b3a4a" },
        { etapa: "Datos corregidos", hhi: hhi.despues_correccion, fill: "#a6bcc9" },
      ]
    : [];
  const curva = pareto?.curva || [];
  const top = (data.top_proveedores || []).slice(0, 10).map((p) => ({
    label: shortLabel(p.nombre, 28),
    full: p.nombre,
    valor: p.valor_cop,
    pct: p.participacion_pct,
  }));
  const nichos = (data.nichos_concentrados || data.nichos_hhi_ejemplo || [])
    .slice(0, 10)
    .map((n) => ({
      label: shortLabel(n.entidad, 28),
      full: n.entidad,
      hhi: n.hhi,
    }));
  const pairChartH = Math.max(400, 10 * 38 + 48);
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
            <ChartInView className="chart-wrap">
              <ResponsiveContainer>
                <BarChart data={hhiBars} layout="vertical" margin={{ left: 8, right: 12 }}>
                  <CartesianGrid stroke="rgba(61,21,52,0.1)" />
                  <XAxis type="number" stroke="#6a5a68" domain={[0, 10000]} />
                  <YAxis
                    type="category"
                    dataKey="etapa"
                    width={120}
                    stroke="#6a5a68"
                    tick={{ fontSize: 12 }}
                  />
                  <Tooltip
                    formatter={(v: number) => [
                      Number(v).toLocaleString("es-CO"),
                      "Concentración",
                    ]}
                  />
                  <Bar dataKey="hhi" fill="#3e4b8e" radius={[0, 8, 8, 0]} animationDuration={1100} />
                </BarChart>
              </ResponsiveContainer>
            </ChartInView>
          </div>

          <div className="panel">
            <h3>¿Cuántos se necesitan para el 80% del valor?</h3>
            <p className="note">
              {pareto?.lectura ||
                "Curva de Pareto: qué porcentaje de proveedores acumula qué porcentaje del dinero."}
            </p>
            <ChartInView className="chart-wrap">
              <ResponsiveContainer>
                <LineChart data={curva}>
                  <CartesianGrid stroke="rgba(61,21,52,0.1)" />
                  <XAxis
                    dataKey="pct_proveedores"
                    stroke="#6a5a68"
                    unit="%"
                    label={{
                      value: "% proveedores",
                      position: "insideBottom",
                      offset: -2,
                      fill: "#8fa89a",
                      fontSize: 11,
                    }}
                  />
                  <YAxis stroke="#6a5a68" unit="%" domain={[0, 100]} />
                  <Tooltip
                    formatter={(v: number) => [`${v}%`, "% del valor"]}
                    labelFormatter={(l) => `${l}% de proveedores`}
                  />
                  <Line
                    type="monotone"
                    dataKey="pct_valor"
                    name="% del valor adjudicado"
                    stroke="#a6bcc9"
                    strokeWidth={2.4}
                    dot={false}
                    animationDuration={1200}
                  />
                </LineChart>
              </ResponsiveContainer>
            </ChartInView>
          </div>
        </div>
      )}

      <div className="grid-2" style={{ marginTop: "1rem", alignItems: "stretch" }}>
        <div className="panel" style={{ display: "flex", flexDirection: "column" }}>
          <h3>Quiénes concentran más valor (top 10)</h3>
          <p className="note">Proveedores con mayor valor adjudicado ya corregido.</p>
          <ChartInView className="chart-wrap tall" style={{ height: pairChartH, marginTop: "auto", overflow: "visible" }}>
            <ResponsiveContainer>
              <BarChart
                data={top}
                layout="vertical"
                margin={{ left: 12, right: 20, top: 8, bottom: 8 }}
                barCategoryGap="18%"
              >
                <CartesianGrid stroke="rgba(61,21,52,0.1)" horizontal={false} />
                <XAxis
                  type="number"
                  stroke="#6a5a68"
                  tickFormatter={(v) => formatCopShort(Number(v))}
                />
                <YAxis
                  type="category"
                  dataKey="label"
                  width={178}
                  interval={0}
                  tick={<CatTick />}
                  tickMargin={6}
                />
                <Tooltip
                  formatter={(v: number, _n, p) => [
                    `${formatCop(Number(v))} (${(p?.payload as { pct?: number })?.pct ?? ""}%)`,
                    "Valor",
                  ]}
                  labelFormatter={(_l, payload) => {
                    const row = payload?.[0]?.payload as { full?: string } | undefined;
                    return row?.full || String(_l);
                  }}
                />
                <Bar dataKey="valor" fill="#7a8dbd" radius={[0, 8, 8, 0]} animationDuration={1100} />
              </BarChart>
            </ResponsiveContainer>
          </ChartInView>
        </div>

        <div className="panel" style={{ display: "flex", flexDirection: "column" }}>
          <h3>Nichos: entidades muy concentradas</h3>
          <p className="note">
            Compradores que casi siempre contratan a los mismos. (Mín. 20 procesos.)
          </p>
          <ChartInView className="chart-wrap tall" style={{ height: pairChartH, marginTop: "auto", overflow: "visible" }}>
            <ResponsiveContainer>
              <BarChart
                data={nichos}
                layout="vertical"
                margin={{ left: 12, right: 20, top: 8, bottom: 8 }}
                barCategoryGap="18%"
              >
                <CartesianGrid stroke="rgba(61,21,52,0.1)" horizontal={false} />
                <XAxis type="number" stroke="#6a5a68" domain={[0, 10000]} />
                <YAxis
                  type="category"
                  dataKey="label"
                  width={178}
                  interval={0}
                  tick={<CatTick />}
                  tickMargin={6}
                />
                <Tooltip
                  formatter={(v: number) => [Number(v).toLocaleString("es-CO"), "HHI"]}
                  labelFormatter={(_l, payload) => {
                    const row = payload?.[0]?.payload as { full?: string } | undefined;
                    return row?.full || String(_l);
                  }}
                />
                <Bar
                  dataKey="hhi"
                  name="Concentración"
                  fill="#8b3a4a"
                  radius={[0, 8, 8, 0]}
                  animationDuration={1100}
                />
              </BarChart>
            </ResponsiveContainer>
          </ChartInView>
        </div>
      </div>

      {rotacion.length > 0 && (
        <div className="panel" style={{ marginTop: "1rem" }}>
          <h3>¿Se repiten los mismos ganadores cada año?</h3>
          <p className="note">
            {rotLectura} La línea oscura es el % del valor CTeI del año que se llevó el #1.
          </p>
          <ChartInView className="chart-wrap" style={{ overflow: "visible" }}>
            <ResponsiveContainer>
              <LineChart data={rotacion} margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
                <CartesianGrid stroke="rgba(61,21,52,0.1)" />
                <XAxis dataKey="anio" stroke="#6a5a68" />
                <YAxis stroke="#6a5a68" unit="%" domain={[0, 100]} />
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (!active || !payload?.length) return null;
                    const row = payload[0]?.payload as {
                      top1_nombre?: string;
                      top1_participacion_pct?: number;
                      top1_valor_cop?: number;
                      jaccard_top50_vs_anio_prev_pct?: number | null;
                    };
                    return (
                      <div
                        style={{
                          background: "#fffaf5",
                          border: "1px solid rgba(61,21,52,0.16)",
                          borderRadius: 6,
                          padding: "0.55rem 0.7rem",
                          maxWidth: 300,
                        }}
                      >
                        <div style={{ color: "#3e4b8e", fontWeight: 700, marginBottom: 4 }}>
                          {label}
                        </div>
                        {row.top1_nombre ? (
                          <div style={{ color: "#3d1534", fontSize: 12, marginBottom: 4 }}>
                            #1: {row.top1_nombre}
                          </div>
                        ) : null}
                        {payload.map((p) => (
                          <div key={String(p.dataKey)} style={{ color: "#3d1534", fontSize: 12 }}>
                            {p.name}:{" "}
                            {p.value == null ? "—" : `${Number(p.value).toLocaleString("es-CO")}%`}
                          </div>
                        ))}
                        {row.top1_valor_cop != null ? (
                          <div style={{ color: "#6a5a68", fontSize: 11, marginTop: 4 }}>
                            Valor del #1: {formatCop(row.top1_valor_cop)}
                          </div>
                        ) : null}
                      </div>
                    );
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line
                  type="monotone"
                  dataKey="jaccard_top50_vs_anio_prev_pct"
                  name="Similitud top-50 vs año anterior"
                  stroke="#a6bcc9"
                  strokeWidth={2.4}
                  connectNulls={false}
                  dot={{ r: 3 }}
                  animationDuration={1200}
                />
                <Line
                  type="monotone"
                  dataKey="top1_participacion_pct"
                  name="% del CTeI total que aportó el #1"
                  stroke="#7a8dbd"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  animationDuration={1100}
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartInView>
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

