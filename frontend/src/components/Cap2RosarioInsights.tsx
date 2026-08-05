import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { formatCop, formatCopShort } from "../lib/format";
import { ChartInView } from "./ChartInView";

export type AnalisisRosario = {
  titulo?: string;
  subtitulo?: string;
  perfil?: {
    nombre?: string;
    nit?: string;
    valor_adjudicado_cop?: number;
    n_entidades_compradoras?: number;
    n_procesos?: number;
    n_competidores_con_overlap?: number;
    ranking_entre_ies?: number;
    n_ies_en_universo?: number;
  };
  compradores?: {
    entidad: string;
    valor_con_rosario_cop: number;
    n_procesos: number;
    pct_ingresos_rosario: number;
    share_of_wallet_pct: number;
    gasto_entidad_ctei_cop?: number;
    segmento?: string;
    depto?: string;
  }[];
  competidores_frecuentes?: {
    nombre: string;
    nit: string;
    n_entidades_compartidas: number;
    entidades_ejemplo?: string[];
    valor_rival_en_compartidas_cop: number;
    valor_rosario_en_compartidas_cop: number;
    ratio_rival_vs_rosario: number;
    valor_total_proveedor_cop?: number;
    es_ies?: boolean;
  }[];
  peers_ies?: {
    nombre: string;
    nit: string;
    valor_total_cop: number;
    n_entidades: number;
    vs_rosario_pct: number;
  }[];
  lecturas?: string[];
  nota?: string;
};

type Props = { data: AnalisisRosario };

const C = {
  teal: "#7a8dbd",
  gold: "#a6bcc9",
  coral: "#8b3a4a",
  wheat: "#f6e0b6",
  cream: "#f6e0b6",
  ink: "#3d1534",
  muted: "#6a5a68",
  grid: "rgba(61,21,52,0.1)",
};

function shortName(s: string, n = 28) {
  const t = (s || "").trim();
  return t.length <= n ? t : t.slice(0, n - 1) + "…";
}

/** Tick de categoría en 1 línea (evita wrap que se monta entre barras). */
function CatTick(props: {
  x?: number;
  y?: number;
  payload?: { value?: string | number };
}) {
  const { x = 0, y = 0, payload } = props;
  return (
    <text
      x={x}
      y={y}
      dy={4}
      textAnchor="end"
      fill={C.ink}
      fontSize={11}
      fontFamily='"Source Sans 3", "Segoe UI", sans-serif'
    >
      {payload?.value ?? ""}
    </text>
  );
}

function barsHeight(n: number, row = 40) {
  return Math.max(280, n * row + 36);
}

function tipStyle(label: string, rows: string[]) {
  return (
    <div
      style={{
        background: "#fffaf5",
        border: "1px solid rgba(61,21,52,0.16)",
        borderRadius: 6,
        padding: "0.55rem 0.7rem",
        maxWidth: 280,
      }}
    >
      <div style={{ color: "#3e4b8e", fontWeight: 700, marginBottom: 4 }}>{label}</div>
      {rows.map((r) => (
        <div key={r} style={{ color: "#3d1534", fontSize: 12, lineHeight: 1.35 }}>
          {r}
        </div>
      ))}
    </div>
  );
}

export function Cap2RosarioInsights({ data }: Props) {
  const p = data.perfil || {};
  const rosValor = p.valor_adjudicado_cop || 0;

  const compradores = useMemo(() => {
    return (data.compradores || []).slice(0, 10).map((c) => ({
      ...c,
      label: shortName(c.entidad, 22),
      full: c.entidad,
    }));
  }, [data.compradores]);

  const walletBars = useMemo(() => {
    return [...(data.compradores || [])]
      .filter((c) => c.share_of_wallet_pct > 0)
      .sort((a, b) => b.share_of_wallet_pct - a.share_of_wallet_pct)
      .slice(0, 10)
      .map((c) => ({
        ...c,
        label: shortName(c.entidad, 22),
        full: c.entidad,
      }));
  }, [data.compradores]);

  const comps = useMemo(() => {
    return (data.competidores_frecuentes || []).slice(0, 8).map((c) => ({
      label: shortName(c.nombre, 20),
      full: c.nombre,
      rival: c.valor_rival_en_compartidas_cop / 1e9,
      rosario: c.valor_rosario_en_compartidas_cop / 1e9,
      comunes: c.n_entidades_compartidas,
      ratio: c.ratio_rival_vs_rosario,
      es_ies: !!c.es_ies,
    }));
  }, [data.competidores_frecuentes]);

  const compsBubble = useMemo(() => {
    return (data.competidores_frecuentes || []).slice(0, 14).map((c) => ({
      x: c.n_entidades_compartidas,
      y: Math.min(c.ratio_rival_vs_rosario, 12),
      yRaw: c.ratio_rival_vs_rosario,
      z: Math.max(c.valor_rival_en_compartidas_cop / 1e9, 1),
      nombre: c.nombre,
      es_ies: !!c.es_ies,
      rival: c.valor_rival_en_compartidas_cop,
      rosario: c.valor_rosario_en_compartidas_cop,
    }));
  }, [data.competidores_frecuentes]);

  const peersChart = useMemo(() => {
    const peers = (data.peers_ies || []).slice(0, 9);
    const rows = [
      ...peers.map((x) => ({
        label: shortName(x.nombre, 24),
        full: x.nombre,
        valor: x.valor_total_cop / 1e9,
        entidades: x.n_entidades,
        esRosario: false,
      })),
      {
        label: "U. Rosario",
        full: p.nombre || "Universidad del Rosario",
        valor: rosValor / 1e9,
        entidades: p.n_entidades_compradoras || 0,
        esRosario: true,
      },
    ];
    rows.sort((a, b) => b.valor - a.valor);
    return rows.slice(0, 10);
  }, [data.peers_ies, p.nombre, p.n_entidades_compradoras, rosValor]);

  return (
    <div className="panel panel-rosario" style={{ marginBottom: "1rem" }}>
      <h3>{data.titulo || "Rosario en la red SECOP–CTeI"}</h3>
      {data.subtitulo ? <p className="note">{data.subtitulo}</p> : null}

      <div className="grid-3" style={{ margin: "0.75rem 0" }}>
        <div className="kpi">
          <div className="label">Valor adjudicado (Rosario)</div>
          <div className="value">{formatCopShort(rosValor)}</div>
          <div className="hint">NIT {p.nit || "—"} · {p.n_procesos ?? "—"} procesos</div>
        </div>
        <div className="kpi">
          <div className="label">Compradores</div>
          <div className="value">{p.n_entidades_compradoras ?? "—"}</div>
          <div className="hint">
            {p.n_competidores_con_overlap ?? "—"} rivales con overlap en esas entidades
          </div>
        </div>
        <div className="kpi">
          <div className="label">Ranking entre IES</div>
          <div className="value">#{p.ranking_entre_ies ?? "—"}</div>
          <div className="hint">de {p.n_ies_en_universo ?? "—"} IES/centros en este universo</div>
        </div>
      </div>

      {data.lecturas && data.lecturas.length > 0 ? (
        <ul className="rosario-list">
          {data.lecturas.slice(0, 3).map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      ) : null}

      {/* 1) Compradores: barras de dependencia + burbujas peso vs wallet */}
      {compradores.length > 0 ? (
        <div style={{ marginTop: "1.4rem" }}>
          <h4>Quién le compra a Rosario</h4>
          <p className="note">
            Izquierda: dependencia de Rosario. Derecha: peso de Rosario en cada entidad.
          </p>
          <div className="chart-pair">
            <div className="chart-block">
              <div className="chart-caption">Para Rosario: peso del cliente</div>
              <p className="note" style={{ marginTop: 0, marginBottom: "0.35rem" }}>
                % del ingreso CTeI de Rosario que viene de esa entidad.
              </p>
              <ChartInView style={{ width: "100%", height: barsHeight(compradores.length) }}>
                <ResponsiveContainer>
                  <BarChart
                    data={compradores}
                    layout="vertical"
                    margin={{ left: 8, right: 28, top: 8, bottom: 8 }}
                    barCategoryGap="18%"
                  >
                    <CartesianGrid stroke={C.grid} horizontal={false} />
                    <XAxis
                      type="number"
                      tick={{ fill: C.muted, fontSize: 11 }}
                      unit="%"
                      domain={[0, "auto"]}
                    />
                    <YAxis
                      type="category"
                      dataKey="label"
                      width={148}
                      interval={0}
                      tick={<CatTick />}
                    />
                    <Tooltip
                      cursor={{ fill: "rgba(62,75,142,0.08)" }}
                      content={({ active, payload }) => {
                        if (!active || !payload?.[0]) return null;
                        const d = payload[0].payload;
                        return tipStyle(d.full, [
                          `${d.pct_ingresos_rosario}% de lo que factura Rosario`,
                          `Valor del vínculo: ${formatCop(d.valor_con_rosario_cop)}`,
                          `${d.n_procesos} procesos`,
                        ]);
                      }}
                    />
                    <Bar dataKey="pct_ingresos_rosario" name="% ingresos" radius={[0, 4, 4, 0]}>
                      {compradores.map((_, i) => (
                        <Cell key={i} fill={i < 2 ? C.cream : C.teal} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartInView>
            </div>
            <div className="chart-block">
              <div className="chart-caption">Para el cliente: cuota de Rosario</div>
              <p className="note" style={{ marginTop: 0, marginBottom: "0.35rem" }}>
                % del gasto CTeI de la entidad que se adjudicó a Rosario.
              </p>
              <ChartInView style={{ width: "100%", height: barsHeight(walletBars.length) }}>
                <ResponsiveContainer>
                  <BarChart
                    data={walletBars}
                    layout="vertical"
                    margin={{ left: 8, right: 28, top: 8, bottom: 8 }}
                    barCategoryGap="18%"
                  >
                    <CartesianGrid stroke={C.grid} horizontal={false} />
                    <XAxis
                      type="number"
                      tick={{ fill: C.muted, fontSize: 11 }}
                      unit="%"
                      domain={[0, "auto"]}
                    />
                    <YAxis
                      type="category"
                      dataKey="label"
                      width={148}
                      interval={0}
                      tick={<CatTick />}
                    />
                    <Tooltip
                      cursor={{ fill: "rgba(139,58,74,0.08)" }}
                      content={({ active, payload }) => {
                        if (!active || !payload?.[0]) return null;
                        const d = payload[0].payload;
                        return tipStyle(d.full, [
                          `Rosario se lleva el ${d.share_of_wallet_pct}% del gasto CTeI de esta entidad`,
                          `Valor con Rosario: ${formatCop(d.valor_con_rosario_cop)}`,
                          `Gasto CTeI total de la entidad: ${formatCop(d.gasto_entidad_ctei_cop || 0)}`,
                        ]);
                      }}
                    />
                    <Bar dataKey="share_of_wallet_pct" name="Cuota Rosario" radius={[0, 4, 4, 0]}>
                      {walletBars.map((d, i) => (
                        <Cell
                          key={i}
                          fill={d.share_of_wallet_pct >= 10 ? C.coral : C.gold}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartInView>
            </div>
          </div>
        </div>
      ) : null}

      {/* 2) Competidores: barras pareadas + mapa overlap */}
      {comps.length > 0 ? (
        <div style={{ marginTop: "1.5rem" }}>
          <h4>Competidores frecuentes</h4>
          <p className="note">
            Rivales con los que Rosario comparte compradores CTeI. Misma comparación, dos
            lecturas.
          </p>
          <div className="chart-pair">
            <div className="chart-block">
              <div className="chart-caption">¿Quién factura más donde se cruzan?</div>
              <p className="note" style={{ marginTop: 0, marginBottom: "0.35rem" }}>
                Valor adjudicado (mil millones COP) en las entidades que ambos atienden.
              </p>
              <ChartInView style={{ width: "100%", height: barsHeight(comps.length, 44) }}>
                <ResponsiveContainer>
                  <BarChart
                    data={comps}
                    layout="vertical"
                    margin={{ left: 8, right: 16, top: 8, bottom: 8 }}
                    barCategoryGap="18%"
                  >
                    <CartesianGrid stroke={C.grid} horizontal={false} />
                    <XAxis type="number" tick={{ fill: C.muted, fontSize: 11 }} />
                    <YAxis
                      type="category"
                      dataKey="label"
                      width={132}
                      interval={0}
                      tick={<CatTick />}
                    />
                    <Tooltip
                      cursor={{ fill: "rgba(139,58,74,0.08)" }}
                      content={({ active, payload }) => {
                        if (!active || !payload?.[0]) return null;
                        const d = payload[0].payload;
                        return tipStyle(d.full, [
                          `${d.comunes} entidades en común`,
                          `Rival: ${d.rival.toFixed(1)} MM`,
                          `Rosario: ${d.rosario.toFixed(1)} MM`,
                          `Ratio: ${d.ratio}× · ${d.es_ies ? "IES" : "Otro"}`,
                        ]);
                      }}
                    />
                    <Legend wrapperStyle={{ color: C.muted, fontSize: 12 }} />
                    <Bar dataKey="rival" name="Rival" fill={C.coral} radius={[0, 3, 3, 0]} />
                    <Bar dataKey="rosario" name="Rosario" fill={C.wheat} radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartInView>
            </div>
            <div className="chart-block">
              <div className="chart-caption">¿Con quién se cruza más y quién gana?</div>
              <p className="note" style={{ marginTop: 0, marginBottom: "0.35rem" }}>
                Derecha = más compradores en común. Arriba de la línea = el rival factura más
                que Rosario. Tamaño = plata del rival en ese cruce.
              </p>
              <ChartInView style={{ width: "100%", height: 340 }}>
                <ResponsiveContainer>
                  <ScatterChart margin={{ left: 8, right: 16, top: 8, bottom: 28 }}>
                    <CartesianGrid stroke={C.grid} />
                    <XAxis
                      type="number"
                      dataKey="x"
                      name="Entidades en común"
                      allowDecimals={false}
                      tick={{ fill: C.muted, fontSize: 11 }}
                      label={{
                        value: "Entidades en común →",
                        position: "insideBottom",
                        offset: -2,
                        fill: C.muted,
                        fontSize: 11,
                      }}
                    />
                    <YAxis
                      type="number"
                      dataKey="y"
                      name="Ratio rival/Rosario"
                      tick={{ fill: C.muted, fontSize: 11 }}
                      label={{
                        value: "Ratio rival / Rosario",
                        angle: -90,
                        position: "insideLeft",
                        fill: C.muted,
                        fontSize: 11,
                      }}
                    />
                    <ZAxis type="number" dataKey="z" range={[50, 320]} name="Valor rival" />
                    <ReferenceLine y={1} stroke={C.teal} strokeDasharray="4 4" />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (!active || !payload?.[0]) return null;
                        const d = payload[0].payload;
                        return tipStyle(shortName(d.nombre, 48), [
                          `${d.x} entidades en común`,
                          `Ratio: ${d.yRaw}× (línea = 1×)`,
                          `Rival: ${formatCop(d.rival)}`,
                          `Rosario en overlap: ${formatCop(d.rosario)}`,
                          d.es_ies ? "Tipo: IES" : "Tipo: otro proveedor",
                        ]);
                      }}
                    />
                    <Legend
                      verticalAlign="bottom"
                      height={28}
                      wrapperStyle={{ color: C.muted, fontSize: 12 }}
                      payload={[
                        { value: "IES", type: "circle", color: C.coral },
                        { value: "Otro proveedor", type: "circle", color: C.gold },
                        {
                          value: "Línea: empatan con Rosario",
                          type: "line",
                          color: C.teal,
                        },
                      ]}
                    />
                    <Scatter name="Rivales" data={compsBubble}>
                      {compsBubble.map((d, i) => (
                        <Cell
                          key={`${d.nombre}-${i}`}
                          fill={d.es_ies ? C.coral : C.gold}
                          fillOpacity={0.88}
                        />
                      ))}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              </ChartInView>
            </div>
          </div>
        </div>
      ) : null}

      {/* 3) Peers IES: ranking con Rosario anclada */}
      {peersChart.length > 0 ? (
        <div style={{ marginTop: "1.5rem" }}>
          <h4>Dónde queda Rosario entre IES</h4>
          <p className="note">
            Valor total CTeI adjudicado. Beige = Rosario; azul = otras IES.
          </p>
          <div className="chart-block" style={{ maxWidth: 720 }}>
            <ChartInView style={{ width: "100%", height: barsHeight(peersChart.length, 42) }}>
              <ResponsiveContainer>
                <BarChart
                  data={peersChart}
                  layout="vertical"
                  margin={{ left: 8, right: 24, top: 8, bottom: 16 }}
                  barCategoryGap="18%"
                >
                  <CartesianGrid stroke={C.grid} horizontal={false} />
                  <XAxis
                    type="number"
                    tick={{ fill: C.muted, fontSize: 11 }}
                    label={{
                      value: "Mil millones COP",
                      position: "insideBottom",
                      offset: -2,
                      fill: C.muted,
                      fontSize: 11,
                    }}
                  />
                  <YAxis
                    type="category"
                    dataKey="label"
                    width={140}
                    interval={0}
                    tick={<CatTick />}
                  />
                  <Tooltip
                    cursor={{ fill: "rgba(246,224,182,0.2)" }}
                    content={({ active, payload }) => {
                      if (!active || !payload?.[0]) return null;
                      const d = payload[0].payload;
                      return tipStyle(d.full, [
                        `Valor: ${d.valor.toFixed(1)} MM`,
                        `${d.entidades} entidades compradoras`,
                        d.esRosario ? "← ancla Rosario" : `≈ ${((d.valor * 1e9) / (rosValor || 1) * 100).toFixed(0)}% vs Rosario`,
                      ]);
                    }}
                  />
                  <Bar dataKey="valor" name="Valor (MM)" radius={[0, 4, 4, 0]}>
                    {peersChart.map((d, i) => (
                      <Cell key={i} fill={d.esRosario ? C.cream : C.teal} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartInView>
          </div>
        </div>
      ) : null}

      {data.nota ? (
        <details className="method-note" style={{ marginTop: "1rem" }}>
          <summary>Metodología (red Rosario)</summary>
          <p>{data.nota}</p>
          <p className="note" style={{ marginTop: "0.5rem" }}>
            Totales de referencia: {formatCop(rosValor)} adjudicados a Rosario en el CSV limpio
            Cap.2.
          </p>
        </details>
      ) : null}
    </div>
  );
}
