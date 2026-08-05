import { motion } from "framer-motion";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatCop, formatCopShort } from "../lib/format";
import { ChartInView } from "./ChartInView";

export type OutlookMercado = {
  metodo?: string;
  metodo_id?: string;
  honestidad?: string;
  ancla_hasta?: string;
  horizonte_meses?: number;
  lectura?: string;
  mejora_vs_estacional_pct?: number | null;
  para_empresa?: string[];
  comparativo_modelos?: {
    modelo: string;
    mape_pct: number;
    mape_mediana_pct?: number;
    rmse?: number;
    n_ventanas?: number;
  }[];
  nombres_modelos?: Record<string, string>;
  procesos?: {
    modelo_elegido?: string;
    mejor_backtest?: { mape_pct?: number; mape_mediana_pct?: number };
    resumen?: {
      total_horizonte: number;
      promedio_mensual: number;
      mes_pico: { etiqueta: string; valor: number };
      mes_valle: { etiqueta: string; valor: number };
    };
    serie?: {
      periodo: string;
      etiqueta: string;
      tipo: string;
      valor: number;
      lo_80?: number | null;
      hi_80?: number | null;
    }[];
  };
  valor?: {
    modelo_elegido?: string;
    resumen?: {
      total_horizonte: number;
      mes_pico: { etiqueta: string; valor: number };
    };
    serie?: {
      periodo: string;
      etiqueta: string;
      tipo: string;
      valor: number;
      lo_80?: number | null;
      hi_80?: number | null;
    }[];
  };
  por_segmento?: {
    codigo: string;
    nombre: string;
    modelo_elegido?: string;
    modelo_nombre?: string;
    mape_backtest_pct?: number;
    mape_media_pct?: number;
    total_horizonte: number;
    mes_pico?: { etiqueta: string; valor: number };
    proximos_meses?: { etiqueta: string; punto: number }[];
    comparativo_local?: {
      modelo: string;
      mape_mediana_pct?: number;
      mape_pct?: number;
    }[];
  }[];
  segmentacion?: {
    metodo_elegido?: string;
    metodo_nombre?: string;
    lectura?: string;
    comparativo_metodos?: {
      modelo: string;
      mape_mediana_pct: number;
      mape_pct?: number;
    }[];
  };
  serie_combinada?: {
    periodo: string;
    etiqueta?: string;
    n_procesos: number;
    valor_sin_mega_cop?: number | null;
    n_lo?: number | null;
    n_hi?: number | null;
    tipo: string;
  }[];
  proximos_meses?: {
    periodo: string;
    etiqueta: string;
    n_procesos_estimado: number;
    n_lo_80?: number;
    n_hi_80?: number;
    valor_sin_mega_estimado_cop?: number | null;
  }[];
};

type Props = { outlook: OutlookMercado };

function modelLabel(id: string, names?: Record<string, string>) {
  return names?.[id] || id.replace(/_/g, " ");
}

export function Cap3MarketForecast({ outlook }: Props) {
  const proc = outlook.procesos;
  const resumen = proc?.resumen;
  const names = outlook.nombres_modelos;
  const mape =
    proc?.mejor_backtest?.mape_mediana_pct ?? proc?.mejor_backtest?.mape_pct ?? null;

  const serieProc = (proc?.serie || outlook.serie_combinada || []).map((r) => {
    const valor = "valor" in r ? (r as { valor: number }).valor : (r as { n_procesos: number }).n_procesos;
    const lo =
      "lo_80" in r
        ? (r as { lo_80?: number | null }).lo_80
        : (r as { n_lo?: number | null }).n_lo;
    const hi =
      "hi_80" in r
        ? (r as { hi_80?: number | null }).hi_80
        : (r as { n_hi?: number | null }).n_hi;
    const tipo = r.tipo;
    const loSafe = lo ?? valor;
    const hiSafe = hi ?? valor;
    return {
      label: r.etiqueta || r.periodo,
      obs: tipo === "observado" ? valor : null,
      proy: tipo === "proyeccion" ? valor : null,
      bridge: valor,
      lo: tipo === "proyeccion" ? loSafe : null,
      band: tipo === "proyeccion" ? Math.max(hiSafe - loSafe, 0) : null,
      hi: hiSafe,
    };
  });

  // conectar última observación con primera proyección en la línea bridge
  const chartData = serieProc.map((row, i) => {
    const prev = serieProc[i - 1];
    const next = serieProc[i + 1];
    let bridge: number | null = row.bridge;
    // solo dibujar bridge en el empalme obs→proy
    if (row.obs != null && next?.proy != null) bridge = row.obs;
    else if (row.proy != null && prev?.obs != null) bridge = row.proy;
    else if (row.obs != null) bridge = null;
    else bridge = row.proy;
    return { ...row, bridge };
  });

  const serieValor = (outlook.valor?.serie || []).map((r) => ({
    label: r.etiqueta,
    obs: r.tipo === "observado" ? r.valor : null,
    proy: r.tipo === "proyeccion" ? r.valor : null,
    lo: r.tipo === "proyeccion" ? r.lo_80 ?? r.valor : null,
    band:
      r.tipo === "proyeccion"
        ? Math.max((r.hi_80 ?? r.valor) - (r.lo_80 ?? r.valor), 0)
        : null,
  }));

  const modelos = (outlook.comparativo_modelos || []).map((m) => ({
    nombre: modelLabel(m.modelo, names),
    mape: m.mape_mediana_pct ?? m.mape_pct,
    elegido: m.modelo === outlook.metodo_id,
  }));

  const segs = outlook.por_segmento || [];
  const segBars = segs.map((s) => ({
    nombre: s.nombre.split(",")[0].split(" y ")[0],
    nombreFull: s.nombre,
    total: Math.round(s.total_horizonte),
    pico: s.mes_pico?.etiqueta || "—",
  }));

  const hallazgos = [
    resumen?.mes_pico
      ? `Pico de procesos: ${resumen.mes_pico.etiqueta} (~${Math.round(resumen.mes_pico.valor).toLocaleString("es-CO")})`
      : null,
    resumen?.mes_valle
      ? `Valle: ${resumen.mes_valle.etiqueta} (~${Math.round(resumen.mes_valle.valor).toLocaleString("es-CO")})`
      : null,
    resumen
      ? `Volumen 6m ≈ ${Math.round(resumen.total_horizonte).toLocaleString("es-CO")} procesos`
      : null,
    outlook.valor?.resumen
      ? `Valor 6m ≈ ${formatCop(outlook.valor.resumen.total_horizonte)} · pico ${outlook.valor.resumen.mes_pico?.etiqueta || "—"}`
      : null,
    mape != null
      ? `Modelo volumen: ${outlook.metodo || "—"} (MAPE ${mape}%)`
      : outlook.metodo
        ? `Modelo volumen: ${outlook.metodo}`
        : null,
    outlook.valor?.modelo_elegido
      ? `Modelo valor: ${modelLabel(outlook.valor.modelo_elegido, names)}`
      : null,
  ].filter(Boolean) as string[];

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="panel panel-rosario" style={{ marginBottom: "1rem" }}>
        <h3>Futuro del mercado · {outlook.horizonte_meses || 6} meses</h3>
        <ul className="rosario-list hallazgos">
          {hallazgos.map((h) => (
            <li key={h}>{h}</li>
          ))}
        </ul>
        <div className="grid-3" style={{ margin: "0.85rem 0 0" }}>
          <div className="kpi">
            <div className="label">Mes pico</div>
            <div className="value" style={{ fontSize: "1.25rem" }}>
              {resumen?.mes_pico?.etiqueta || "—"}
            </div>
            <div className="hint">
              ~
              {(resumen?.mes_pico?.valor ?? 0).toLocaleString("es-CO", {
                maximumFractionDigits: 0,
              })}{" "}
              procesos
            </div>
          </div>
          <div className="kpi">
            <div className="label">Procesos (6m)</div>
            <div className="value" style={{ fontSize: "1.25rem" }}>
              {(resumen?.total_horizonte ?? 0).toLocaleString("es-CO", {
                maximumFractionDigits: 0,
              })}
            </div>
            <div className="hint">ancla {outlook.ancla_hasta}</div>
          </div>
          <div className="kpi">
            <div className="label">Valor (6m)</div>
            <div className="value" style={{ fontSize: "1.15rem" }}>
              {formatCopShort(outlook.valor?.resumen?.total_horizonte || 0)}
            </div>
            <div className="hint">sin megacontratos</div>
          </div>
        </div>
      </div>

      <div className="panel" style={{ marginBottom: "1rem" }}>
        <h3>Procesos</h3>
        <ChartInView style={{ width: "100%", height: 320 }}>
          <ResponsiveContainer>
            <ComposedChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(61,21,52,0.1)" />
              <XAxis dataKey="label" tick={{ fill: "#6a5a68", fontSize: 11 }} />
              <YAxis
                tick={{ fill: "#6a5a68", fontSize: 11 }}
                tickFormatter={(v) => Number(v).toLocaleString("es-CO")}
              />
              <Tooltip
                contentStyle={{
                  background: "#fffaf5",
                  border: "1px solid rgba(61,21,52,0.16)",
                  borderRadius: 10,
                }}
                formatter={(value: number, name: string) => {
                  if (name === "lo" || name === "band") return [null, null];
                  return [Number(value).toLocaleString("es-CO"), name];
                }}
              />
              <Legend />
              <Area
                type="monotone"
                dataKey="lo"
                stackId="band"
                stroke="none"
                fill="transparent"
                legendType="none"
                isAnimationActive={false}
              />
              <Area
                type="monotone"
                dataKey="band"
                stackId="band"
                name="Banda ~80%"
                stroke="none"
                fill="rgba(62,75,142,0.18)"
                isAnimationActive={false}
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="obs"
                name="Observado"
                stroke="#3e4b8e"
                strokeWidth={2.6}
                dot={{ r: 3 }}
                connectNulls={false}
              />
              <Line
                type="monotone"
                dataKey="proy"
                name="Proyección"
                stroke="#a6bcc9"
                strokeWidth={2.6}
                strokeDasharray="7 4"
                dot={{ r: 3 }}
                connectNulls={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartInView>
      </div>

      <div className="grid-2" style={{ marginBottom: "1rem" }}>
        <div className="panel">
          <h3>Error por modelo (MAPE)</h3>
          <ChartInView style={{ width: "100%", height: 240 }}>
            <ResponsiveContainer>
              <BarChart data={modelos} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(61,21,52,0.1)" />
                <XAxis type="number" tick={{ fill: "#6a5a68", fontSize: 11 }} unit="%" />
                <YAxis
                  type="category"
                  dataKey="nombre"
                  width={140}
                  tick={{ fill: "#6a5a68", fontSize: 10 }}
                />
                <Tooltip
                  contentStyle={{
                    background: "#fffaf5",
                    border: "1px solid rgba(61,21,52,0.16)",
                    borderRadius: 10,
                  }}
                  formatter={(v: number) => [`${v}%`, "MAPE"]}
                />
                <Bar dataKey="mape" name="MAPE %" fill="#3e4b8e" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartInView>
        </div>

        <div className="panel">
          <h3>Por segmento (6m)</h3>
          {segBars.length === 0 ? (
            <p className="note">Sin desglose.</p>
          ) : (
            <ChartInView style={{ width: "100%", height: 240 }}>
              <ResponsiveContainer>
                <BarChart data={segBars}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(61,21,52,0.1)" />
                  <XAxis dataKey="nombre" tick={{ fill: "#6a5a68", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#6a5a68", fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      background: "#fffaf5",
                      border: "1px solid rgba(61,21,52,0.16)",
                      borderRadius: 10,
                    }}
                    formatter={(v: number, _n, ctx) => [
                      Number(v).toLocaleString("es-CO"),
                      ctx?.payload?.nombreFull || "Procesos",
                    ]}
                  />
                  <Bar dataKey="total" name="Procesos 6m" fill="#a6bcc9" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartInView>
          )}
          {segs.length > 0 && (() => {
            const picos = [...new Set(segs.map((s) => s.mes_pico?.etiqueta).filter(Boolean))];
            if (picos.length === 1) {
              return (
                <p className="note" style={{ marginTop: "0.55rem" }}>
                  Pico general en los tres segmentos: <strong>{picos[0]}</strong>
                </p>
              );
            }
            return (
              <ul className="rosario-list hallazgos" style={{ marginTop: "0.5rem" }}>
                {segs.map((s) => (
                  <li key={s.codigo}>
                    {s.nombre.split(",")[0]}: pico {s.mes_pico?.etiqueta || "—"}
                  </li>
                ))}
              </ul>
            );
          })()}
        </div>
      </div>

      {serieValor.length > 0 && (
        <div className="panel" style={{ marginBottom: "1rem" }}>
          <h3>Valor (sin megacontratos)</h3>
          <ul className="rosario-list hallazgos">
            <li>
              {modelLabel(outlook.valor?.modelo_elegido || "", names)} · 6m ≈{" "}
              {formatCop(outlook.valor?.resumen?.total_horizonte || 0)}
            </li>
            {outlook.valor?.resumen?.mes_pico ? (
              <li>
                Pico de valor: {outlook.valor.resumen.mes_pico.etiqueta} (
                {formatCopShort(outlook.valor.resumen.mes_pico.valor)})
              </li>
            ) : null}
          </ul>
          <ChartInView style={{ width: "100%", height: 260 }}>
            <ResponsiveContainer>
              <ComposedChart data={serieValor}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(61,21,52,0.1)" />
                <XAxis dataKey="label" tick={{ fill: "#6a5a68", fontSize: 11 }} />
                <YAxis
                  tick={{ fill: "#6a5a68", fontSize: 11 }}
                  tickFormatter={(v) => formatCopShort(Number(v))}
                />
                <Tooltip
                  contentStyle={{
                    background: "#fffaf5",
                    border: "1px solid rgba(61,21,52,0.16)",
                    borderRadius: 10,
                  }}
                  formatter={(value: number, name: string) => {
                    if (name === "lo" || name === "band") return [null, null];
                    return [formatCop(Number(value)), name];
                  }}
                />
                <Legend />
                <Area
                  type="monotone"
                  dataKey="lo"
                  stackId="vb"
                  stroke="none"
                  fill="transparent"
                  legendType="none"
                />
                <Area
                  type="monotone"
                  dataKey="band"
                  stackId="vb"
                  name="Banda ~80%"
                  stroke="none"
                  fill="rgba(166,188,201,0.35)"
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="obs"
                  name="Observado"
                  stroke="#3e4b8e"
                  strokeWidth={2.4}
                  dot={{ r: 2 }}
                />
                <Line
                  type="monotone"
                  dataKey="proy"
                  name="Proyección"
                  stroke="#6a5a68"
                  strokeWidth={2.4}
                  strokeDasharray="7 4"
                  dot={{ r: 2 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </ChartInView>
        </div>
      )}
    </motion.div>
  );
}

