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

export type Capacidad1 = {
  titulo: string;
  subtitulo?: string;
  kpis?: {
    n_procesos: number;
    valor_total_cop: number;
    n_megacontratos: number;
    pct_valor_megacontratos: number;
    desde?: string;
    hasta?: string;
  };
  serie_mensual?: {
    periodo: string;
    etiqueta?: string;
    n_procesos: number;
    valor_total_cop: number;
    valor_sin_mega_cop: number;
  }[];
  estacionalidad_mensual?: {
    mes: number;
    nombre: string;
    n_procesos_promedio: number;
    valor_promedio_cop: number;
  }[];
  unspsc_mix: { codigo: string; nombre: string; pct: number }[];
  fondos_administrados: { n_procesos: number; pct_valor: number; nota: string };
  estacionalidad?: { lectura?: string; mes_pico?: { nombre: string } | null };
  cierre_rosario?: { titulo: string; puntos: string[] };
  nota_metodologica?: string;
};

type Props = { data: Capacidad1 };

export function Cap1Panel({ data }: Props) {
  const serie = (data.serie_mensual || []).map((r) => ({
    ...r,
    label: r.etiqueta || r.periodo,
  }));
  const estacional = data.estacionalidad_mensual || [];
  const mix = data.unspsc_mix.map((u) => ({
    nombre: u.nombre,
    pct: Math.round(u.pct * 1000) / 10,
  }));
  const k = data.kpis;

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
      <div className="panel" style={{ marginBottom: "1rem" }}>
        <h3>{data.titulo}</h3>
        <p className="note">
          {data.subtitulo ||
            "Mes a mes, en pesos constantes (ajustados por inflación)."}
          {k?.desde && k?.hasta ? ` · ${k.desde} a ${k.hasta}` : ""}
        </p>
        {k && (
          <div className="grid-3">
            <div className="kpi">
              <div className="label">Contratos publicados</div>
              <div className="value">{k.n_procesos.toLocaleString("es-CO")}</div>
              <div className="hint">universo CTeI (educación, investigación, gestión)</div>
            </div>
            <div className="kpi">
              <div className="label">Dinero del mercado</div>
              <div className="value" style={{ fontSize: "1.45rem" }}>
                {formatCop(k.valor_total_cop)}
              </div>
              <div className="hint">pesos constantes (IPC)</div>
            </div>
            <div className="kpi">
              <div className="label">Megacontratos</div>
              <div className="value">
                {(k.pct_valor_megacontratos * 100).toFixed(0)}%
              </div>
              <div className="hint">
                {k.n_megacontratos} contratos concentran esa fracción del valor
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="grid-2">
        <div className="panel">
          <h3>¿Cuántos contratos se publican cada mes?</h3>
          <p className="note">
            Cada punto es un mes. Sirve para ver si el mercado CTeI está más o
            menos activo.
          </p>
          <div className="chart-wrap tall">
            <ResponsiveContainer>
              <LineChart data={serie}>
                <CartesianGrid stroke="rgba(238,245,240,0.06)" />
                <XAxis
                  dataKey="label"
                  stroke="#8fa89a"
                  interval="preserveStartEnd"
                  tick={{ fontSize: 10 }}
                  minTickGap={28}
                />
                <YAxis
                  stroke="#8fa89a"
                  tickFormatter={(v) => Number(v).toLocaleString("es-CO")}
                  width={56}
                />
                <Tooltip
                  formatter={(v: number) => [
                    Number(v).toLocaleString("es-CO"),
                    "Contratos",
                  ]}
                  labelFormatter={(l) => String(l)}
                />
                <Line
                  type="monotone"
                  dataKey="n_procesos"
                  name="Contratos publicados"
                  stroke="#3dcfb0"
                  strokeWidth={2.4}
                  dot={false}
                  animationDuration={1000}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel">
          <h3>¿Cuánto dinero mueve el mercado?</h3>
          <p className="note">
            La línea dorada incluye todo. La menta quita los contratos
            excepcionalmente grandes — esa es la lectura más útil para
            oportunidades cotidianas.
          </p>
          <div className="chart-wrap tall">
            <ResponsiveContainer>
              <LineChart data={serie}>
                <CartesianGrid stroke="rgba(238,245,240,0.06)" />
                <XAxis
                  dataKey="label"
                  stroke="#8fa89a"
                  interval="preserveStartEnd"
                  tick={{ fontSize: 10 }}
                  minTickGap={28}
                />
                <YAxis
                  stroke="#8fa89a"
                  tickFormatter={(v) => formatCopShort(Number(v))}
                  width={48}
                />
                <Tooltip
                  formatter={(v: number, name: string) => [formatCop(Number(v)), name]}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="valor_total_cop"
                  name="Valor total"
                  stroke="#c4a35a"
                  strokeWidth={2.2}
                  dot={false}
                  animationDuration={1000}
                />
                <Line
                  type="monotone"
                  dataKey="valor_sin_mega_cop"
                  name="Sin megacontratos"
                  stroke="#3dcfb0"
                  strokeWidth={2.2}
                  dot={false}
                  animationDuration={1100}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="note" style={{ marginTop: "0.5rem" }}>
            {data.fondos_administrados.nota}
          </p>
        </div>
      </div>

      <div className="grid-2" style={{ marginTop: "1rem" }}>
        <div className="panel">
          <h3>¿En qué se concentra el mercado?</h3>
          <p className="note">
            Tres familias de contratación afines a ciencia, tecnología e
            innovación.
          </p>
          <div className="chart-wrap">
            <ResponsiveContainer>
              <BarChart data={mix} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid stroke="rgba(238,245,240,0.06)" />
                <XAxis type="number" unit="%" stroke="#8fa89a" />
                <YAxis
                  type="category"
                  dataKey="nombre"
                  width={150}
                  stroke="#8fa89a"
                  tick={{ fontSize: 11 }}
                />
                <Tooltip formatter={(v: number) => [`${v}%`, "Participación"]} />
                <Bar dataKey="pct" fill="#3dcfb0" radius={[0, 8, 8, 0]} animationDuration={900} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel">
          <h3>¿Qué meses suelen ser más activos?</h3>
          <p className="note">
            {data.estacionalidad?.lectura ||
              "Promedio de contratos publicados según el mes del año."}
          </p>
          <div className="chart-wrap">
            <ResponsiveContainer>
              <BarChart data={estacional}>
                <CartesianGrid stroke="rgba(238,245,240,0.06)" />
                <XAxis dataKey="nombre" stroke="#8fa89a" />
                <YAxis stroke="#8fa89a" tickFormatter={(v) => Number(v).toLocaleString("es-CO")} />
                <Tooltip
                  formatter={(v: number) => [
                    Number(v).toLocaleString("es-CO", { maximumFractionDigits: 0 }),
                    "Contratos (promedio)",
                  ]}
                />
                <Bar
                  dataKey="n_procesos_promedio"
                  name="Contratos promedio"
                  fill="#c4a35a"
                  radius={[8, 8, 0, 0]}
                  animationDuration={900}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {data.cierre_rosario && (
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
