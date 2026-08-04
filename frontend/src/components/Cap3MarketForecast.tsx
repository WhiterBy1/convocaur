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

  // tabla próximos meses
  const prox = outlook.proximos_meses || [];

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="panel panel-rosario" style={{ marginBottom: "1rem" }}>
        <h3>Futuro del mercado · próximos {outlook.horizonte_meses || 6} meses</h3>
        <p className="note">{outlook.lectura}</p>

        <div className="grid-3" style={{ margin: "0.9rem 0 0.4rem" }}>
          <div className="kpi">
            <div className="label">Modelo elegido</div>
            <div className="value" style={{ fontSize: "1.15rem" }}>
              {outlook.metodo || "—"}
            </div>
            <div className="hint">
              por menor error en backtest
              {mape != null ? ` · MAPE mediana ${mape}%` : ""}
            </div>
          </div>
          <div className="kpi">
            <div className="label">Mes más activo (proyección)</div>
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
            <div className="label">Volumen esperado (6 meses)</div>
            <div className="value" style={{ fontSize: "1.25rem" }}>
              {(resumen?.total_horizonte ?? 0).toLocaleString("es-CO", {
                maximumFractionDigits: 0,
              })}
            </div>
            <div className="hint">
              ~{(resumen?.promedio_mensual ?? 0).toLocaleString("es-CO", {
                maximumFractionDigits: 0,
              })}{" "}
              / mes · ancla {outlook.ancla_hasta}
            </div>
          </div>
        </div>
      </div>

      <div className="panel" style={{ marginBottom: "1rem" }}>
        <h3>Procesos publicados — histórico + proyección</h3>
        <p className="note">
          Línea continua = observado. Punteada = forecast. Área = intervalo ~80%.
        </p>
        <div style={{ width: "100%", height: 320 }}>
          <ResponsiveContainer>
            <ComposedChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(233,238,244,0.14)" />
              <XAxis dataKey="label" tick={{ fill: "#9aada2", fontSize: 11 }} />
              <YAxis
                tick={{ fill: "#9aada2", fontSize: 11 }}
                tickFormatter={(v) => Number(v).toLocaleString("es-CO")}
              />
              <Tooltip
                contentStyle={{
                  background: "#12201a",
                  border: "1px solid rgba(196,163,90,0.3)",
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
                fill="rgba(94, 196, 168, 0.22)"
                isAnimationActive={false}
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="obs"
                name="Observado"
                stroke="#6fd0bc"
                strokeWidth={2.6}
                dot={{ r: 3 }}
                connectNulls={false}
              />
              <Line
                type="monotone"
                dataKey="proy"
                name="Proyección"
                stroke="#e2b86a"
                strokeWidth={2.6}
                strokeDasharray="7 4"
                dot={{ r: 3 }}
                connectNulls={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {prox.length > 0 && (
          <div className="forecast-table-wrap">
            <table className="forecast-table">
              <thead>
                <tr>
                  <th>Mes</th>
                  <th>Procesos (punto)</th>
                  <th>Rango ~80%</th>
                  <th>Valor s/ mega</th>
                </tr>
              </thead>
              <tbody>
                {prox.map((p) => (
                  <tr key={p.periodo}>
                    <td>{p.etiqueta}</td>
                    <td>
                      {Math.round(p.n_procesos_estimado).toLocaleString("es-CO")}
                    </td>
                    <td>
                      {p.n_lo_80 != null && p.n_hi_80 != null
                        ? `${Math.round(p.n_lo_80).toLocaleString("es-CO")} – ${Math.round(p.n_hi_80).toLocaleString("es-CO")}`
                        : "—"}
                    </td>
                    <td>
                      {p.valor_sin_mega_estimado_cop != null
                        ? formatCopShort(p.valor_sin_mega_estimado_cop)
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="grid-2" style={{ marginBottom: "1rem" }}>
        <div className="panel">
          <h3>¿Qué modelo ganó el backtest?</h3>
          <p className="note">
            Error mediano (MAPE) en varias ventanas de {outlook.horizonte_meses || 6} meses.
            Menor = mejor.
          </p>
          <div style={{ width: "100%", height: 240 }}>
            <ResponsiveContainer>
              <BarChart data={modelos} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(233,238,244,0.14)" />
                <XAxis
                  type="number"
                  tick={{ fill: "#9aada2", fontSize: 11 }}
                  unit="%"
                />
                <YAxis
                  type="category"
                  dataKey="nombre"
                  width={150}
                  tick={{ fill: "#9aada2", fontSize: 10 }}
                />
                <Tooltip
                  contentStyle={{
                    background: "#12201a",
                    border: "1px solid rgba(196,163,90,0.3)",
                    borderRadius: 10,
                  }}
                  formatter={(v: number) => [`${v}%`, "MAPE"]}
                />
                <Bar
                  dataKey="mape"
                  name="MAPE %"
                  fill="#6fd0bc"
                  radius={[0, 6, 6, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel">
          <h3>Por segmento UNSPSC (6 meses)</h3>
          <p className="note">
            {outlook.segmentacion?.metodo_nombre ||
              "Top-down: se proyecta el total y se reparte por participación."}
            {outlook.segmentacion?.lectura ? ` ${outlook.segmentacion.lectura}` : ""}
          </p>
          {segBars.length === 0 ? (
            <p className="note">Sin desglose de segmentos en este build.</p>
          ) : (
            <div style={{ width: "100%", height: 240 }}>
              <ResponsiveContainer>
                <BarChart data={segBars}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(233,238,244,0.14)" />
                  <XAxis dataKey="nombre" tick={{ fill: "#9aada2", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#9aada2", fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      background: "#12201a",
                      border: "1px solid rgba(196,163,90,0.3)",
                      borderRadius: 10,
                    }}
                    formatter={(v: number, _n, ctx) => [
                      Number(v).toLocaleString("es-CO"),
                      ctx?.payload?.nombreFull || "Procesos",
                    ]}
                  />
                  <Bar dataKey="total" name="Procesos 6m" fill="#e2b86a" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          {segs.length > 0 && (
            <ul className="rosario-list" style={{ marginTop: "0.5rem" }}>
              {segs.map((s) => (
                <li key={s.codigo}>
                  <strong>{s.nombre}</strong>: pico {s.mes_pico?.etiqueta || "—"} (~
                  {Math.round(s.mes_pico?.valor || 0).toLocaleString("es-CO")})
                  {s.mape_backtest_pct != null
                    ? ` · MAPE mediana ${s.mape_backtest_pct}%`
                    : ""}
                </li>
              ))}
            </ul>
          )}
          {(outlook.segmentacion?.comparativo_metodos?.length || 0) > 0 && (
            <p className="note" style={{ marginTop: "0.65rem" }}>
              Comparativo enfoques:{" "}
              {outlook.segmentacion!.comparativo_metodos!.map((m, i) => (
                <span key={m.modelo}>
                  {i > 0 ? " · " : ""}
                  {m.modelo.replace("topdown_", "TD ")} {m.mape_mediana_pct}%
                </span>
              ))}
            </p>
          )}
        </div>
      </div>

      {serieValor.length > 0 && (
        <div className="panel" style={{ marginBottom: "1rem" }}>
          <h3>Valor del mercado (sin megacontratos)</h3>
          <p className="note">
            Más volátil que el conteo. Modelo:{" "}
            {modelLabel(outlook.valor?.modelo_elegido || "", names)}. Total 6m ≈{" "}
            {formatCop(outlook.valor?.resumen?.total_horizonte || 0)}.
            {" "}
            El forecast de valor se ancla al último mes observado para no “saltar” al
            mismo mes del año pasado cuando el nivel reciente cambió (p. ej. Jul 2026
            muy por debajo de Ago 2025).
          </p>
          <div style={{ width: "100%", height: 260 }}>
            <ResponsiveContainer>
              <ComposedChart data={serieValor}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(233,238,244,0.14)" />
                <XAxis dataKey="label" tick={{ fill: "#9aada2", fontSize: 11 }} />
                <YAxis
                  tick={{ fill: "#9aada2", fontSize: 11 }}
                  tickFormatter={(v) => formatCopShort(Number(v))}
                />
                <Tooltip
                  contentStyle={{
                    background: "#12201a",
                    border: "1px solid rgba(196,163,90,0.3)",
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
                  fill="rgba(196, 163, 90, 0.18)"
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="obs"
                  name="Observado"
                  stroke="#6fd0bc"
                  strokeWidth={2.4}
                  dot={{ r: 2 }}
                />
                <Line
                  type="monotone"
                  dataKey="proy"
                  name="Proyección"
                  stroke="#c5d0da"
                  strokeWidth={2.4}
                  strokeDasharray="7 4"
                  dot={{ r: 2 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {outlook.para_empresa && (
        <div className="panel" style={{ marginBottom: "1rem" }}>
          <h3>Cómo usa esto una empresa</h3>
          <ul className="rosario-list">
            {outlook.para_empresa.map((it) => (
              <li key={it}>{it}</li>
            ))}
          </ul>
          {outlook.honestidad && <p className="note">{outlook.honestidad}</p>}
        </div>
      )}
    </motion.div>
  );
}
