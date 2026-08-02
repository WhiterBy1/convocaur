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
  hhi: {
    antes_outliers: number;
    despues_correccion: number;
    lectura: string;
    guia?: { rango: string; significado: string }[];
  };
  pareto: {
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
};

type Props = { data: Capacidad2 };

export function Cap2Panel({ data }: Props) {
  const k = data.kpis;
  const hhiBars = [
    { etapa: "Sin limpiar datos", hhi: data.hhi.antes_outliers, fill: "#e07a5f" },
    { etapa: "Datos corregidos", hhi: data.hhi.despues_correccion, fill: "#3dcfb0" },
  ];
  const curva = data.pareto.curva || [];
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
        <h3>{data.titulo}</h3>
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

      <div className="grid-2">
        <div className="panel">
          <h3>¿El mercado es de pocos o de muchos?</h3>
          <p className="note">{data.hhi.lectura}</p>
          <div className="chart-wrap">
            <ResponsiveContainer>
              <BarChart data={hhiBars} layout="vertical" margin={{ left: 8, right: 12 }}>
                <CartesianGrid stroke="rgba(238,245,240,0.06)" />
                <XAxis type="number" stroke="#8fa89a" domain={[0, 10000]} />
                <YAxis type="category" dataKey="etapa" width={120} stroke="#8fa89a" tick={{ fontSize: 12 }} />
                <Tooltip
                  formatter={(v: number) => [Number(v).toLocaleString("es-CO"), "Concentración"]}
                />
                <Bar dataKey="hhi" fill="#c4a35a" radius={[0, 8, 8, 0]} animationDuration={900} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          {data.hhi.guia && (
            <ul className="detail-list" style={{ marginTop: "0.75rem" }}>
              {data.hhi.guia.map((g) => (
                <li key={g.rango}>
                  <span>{g.rango}</span>
                  <strong style={{ fontWeight: 500, fontSize: "0.85rem" }}>{g.significado}</strong>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="panel">
          <h3>¿Cuántos se necesitan para el 80% del valor?</h3>
          <p className="note">
            {data.pareto.lectura ||
              "Curva de Pareto: qué porcentaje de proveedores acumula qué porcentaje del dinero."}
          </p>
          <div className="chart-wrap">
            <ResponsiveContainer>
              <LineChart data={curva}>
                <CartesianGrid stroke="rgba(238,245,240,0.06)" />
                <XAxis
                  dataKey="pct_proveedores"
                  stroke="#8fa89a"
                  unit="%"
                  label={{ value: "% proveedores", position: "insideBottom", offset: -2, fill: "#8fa89a", fontSize: 11 }}
                />
                <YAxis stroke="#8fa89a" unit="%" domain={[0, 100]} />
                <Tooltip
                  formatter={(v: number) => [`${v}%`, "% del valor"]}
                  labelFormatter={(l) => `${l}% de proveedores`}
                />
                <Line
                  type="monotone"
                  dataKey="pct_valor"
                  name="% del valor adjudicado"
                  stroke="#3dcfb0"
                  strokeWidth={2.4}
                  dot={false}
                  animationDuration={1000}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid-2" style={{ marginTop: "1rem" }}>
        <div className="panel">
          <h3>Quiénes concentran más valor (top 10)</h3>
          <p className="note">Proveedores con mayor valor adjudicado ya corregido.</p>
          <div className="chart-wrap tall">
            <ResponsiveContainer>
              <BarChart data={top} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid stroke="rgba(238,245,240,0.06)" />
                <XAxis type="number" stroke="#8fa89a" tickFormatter={(v) => formatCopShort(Number(v))} />
                <YAxis type="category" dataKey="nombre" width={140} stroke="#8fa89a" tick={{ fontSize: 10 }} />
                <Tooltip
                  formatter={(v: number, _n, p) => [
                    `${formatCop(Number(v))} (${(p?.payload as { pct?: number })?.pct ?? ""}%)`,
                    "Valor",
                  ]}
                />
                <Bar dataKey="valor" fill="#c4a35a" radius={[0, 8, 8, 0]} animationDuration={900} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel">
          <h3>Nichos: entidades muy concentradas</h3>
          <p className="note">
            Aunque el país se ve competitivo, algunos compradores casi siempre
            contratan a los mismos. (Mín. 20 procesos.)
          </p>
          <div className="chart-wrap tall">
            <ResponsiveContainer>
              <BarChart
                data={nichos.map((n) => ({
                  entidad: n.entidad.length > 40 ? n.entidad.slice(0, 38) + "…" : n.entidad,
                  hhi: n.hhi,
                }))}
              >
                <CartesianGrid stroke="rgba(238,245,240,0.06)" />
                <XAxis dataKey="entidad" stroke="#8fa89a" tick={{ fontSize: 10 }} interval={0} angle={-18} textAnchor="end" height={80} />
                <YAxis stroke="#8fa89a" domain={[0, 10000]} />
                <Tooltip />
                <Bar dataKey="hhi" name="Concentración" fill="#e07a5f" radius={[8, 8, 0, 0]} animationDuration={900} />
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
                <CartesianGrid stroke="rgba(238,245,240,0.06)" />
                <XAxis dataKey="anio" stroke="#8fa89a" />
                <YAxis stroke="#8fa89a" unit="%" domain={[0, 100]} />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="jaccard_top50_vs_anio_prev_pct"
                  name="Similitud top-50 vs año anterior"
                  stroke="#3dcfb0"
                  strokeWidth={2.4}
                  connectNulls={false}
                  animationDuration={1000}
                />
                <Line
                  type="monotone"
                  dataKey="top1_participacion_pct"
                  name="Peso del #1 ese año"
                  stroke="#c4a35a"
                  strokeWidth={2}
                  animationDuration={1100}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="note" style={{ marginTop: "0.5rem" }}>
            Similitud cercana a 100% = casi los mismos del año previo. Valores
            bajos = mucha rotación (oportunidad para nuevos).
          </p>
        </div>
      )}

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
