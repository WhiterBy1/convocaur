import { useState } from "react";
import { motion } from "framer-motion";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Cap3PredictDemo } from "./Cap3PredictDemo";
import { formatCop } from "../lib/format";

export type Capacidad3 = {
  titulo: string;
  subtitulo?: string;
  outlook_mercado?: {
    metodo?: string;
    honestidad?: string;
    ancla_hasta?: string;
    horizonte_meses?: number;
    lectura?: string;
    para_empresa?: string[];
    serie_combinada?: {
      periodo: string;
      etiqueta?: string;
      n_procesos: number;
      valor_sin_mega_cop: number;
      tipo: "observado" | "proyeccion";
    }[];
    proximos_meses?: {
      periodo: string;
      etiqueta: string;
      n_procesos_estimado: number;
      valor_sin_mega_estimado_cop: number;
    }[];
  };
  para_empresa?: {
    titulo: string;
    capas: {
      id: string;
      nombre: string;
      pregunta: string;
      uso: string;
      como: string;
    }[];
  };
  kpis?: {
    auc_adjudicacion: number;
    auc_pct: number;
    n_competitivos: number;
    tasa_adjudicacion: number;
    fecha_corte: string;
    modelo_recomendado: string;
  };
  universo?: {
    n_competitivos: number;
    tasa_adjudicacion: number;
    n_resueltos: number;
    n_abiertos: number;
    lectura: string;
  };
  pregunta_adjudicacion?: {
    pregunta: string;
    usar: boolean;
    metrica_valor: number;
    metrica_guia?: string;
    accuracy_pct?: number;
    modelo?: string;
    n_train?: number;
    n_test?: number;
    lectura: string;
  };
  pregunta_adjudicacion_mala?: {
    pregunta: string;
    usar: boolean;
    metrica_valor: number;
    lectura: string;
  };
  pregunta_presupuesto?: {
    pregunta: string;
    usar: boolean;
    acc_modelo_pct: number;
    acc_trivial_pct: number;
    bins?: string[];
    lectura: string;
  };
  pregunta_segmento?: {
    pregunta: string;
    usar: boolean;
    acc_modelo_pct: number;
    acc_trivial_pct: number;
    lectura: string;
  };
  reglas_uso?: { titulo: string; items: string[] }[];
  cierre_rosario?: { titulo: string; puntos: string[] };
  nota_metodologica?: string;
};

type PredCard = {
  id: string;
  pregunta: string;
  respuestaCorta: string;
  scoreLabel: string;
  scorePct: number;
  compareLabel?: string;
  comparePct?: number;
  usar: boolean;
  badge: string;
  lectura: string;
};

function ScoreBar({
  scorePct,
  comparePct,
  compareLabel,
  good,
}: {
  scorePct: number;
  comparePct?: number;
  compareLabel?: string;
  good: boolean;
}) {
  return (
    <div className="score-bars">
      <div className="score-row">
        <span className="score-name">Nuestro modelo</span>
        <div className="score-track">
          <div
            className={`score-fill ${good ? "good" : "bad"}`}
            style={{ width: `${Math.min(scorePct, 100)}%` }}
          />
        </div>
        <strong>{scorePct}%</strong>
      </div>
      {comparePct != null && (
        <div className="score-row">
          <span className="score-name">{compareLabel || "Sin modelo"}</span>
          <div className="score-track">
            <div className="score-fill muted" style={{ width: `${Math.min(comparePct, 100)}%` }} />
          </div>
          <strong>{comparePct}%</strong>
        </div>
      )}
    </div>
  );
}

type Props = { data: Capacidad3 };

export function Cap3Panel({ data }: Props) {
  const [showProceso, setShowProceso] = useState(false);
  const k = data.kpis;
  const outlook = data.outlook_mercado;
  const serie = (outlook?.serie_combinada || []).map((r) => ({
    ...r,
    label: r.etiqueta || r.periodo,
    n_obs: r.tipo === "observado" ? r.n_procesos : null,
    n_proy: r.tipo === "proyeccion" ? r.n_procesos : null,
  }));

  const cards: PredCard[] = [];
  if (data.pregunta_adjudicacion) {
    const p = data.pregunta_adjudicacion;
    cards.push({
      id: "adj",
      pregunta: p.pregunta,
      respuestaCorta: "Probabilidad de que el proceso competitivo se adjudique",
      scoreLabel: "Qué tan bien ordena los casos (frente al azar)",
      scorePct: p.metrica_valor,
      compareLabel: "Adivinar al azar",
      comparePct: 50,
      usar: true,
      badge: "Sí usar",
      lectura: p.lectura,
    });
  }
  if (data.pregunta_presupuesto) {
    const p = data.pregunta_presupuesto;
    cards.push({
      id: "pres",
      pregunta: p.pregunta,
      respuestaCorta: "Clasifica el monto en bajo / medio / alto (4 rangos)",
      scoreLabel: "Aciertos del modelo",
      scorePct: p.acc_modelo_pct,
      compareLabel: "Sin modelo (siempre lo más común)",
      comparePct: p.acc_trivial_pct,
      usar: true,
      badge: "Sí usar",
      lectura: p.lectura,
    });
  }
  if (data.pregunta_segmento) {
    const p = data.pregunta_segmento;
    cards.push({
      id: "seg",
      pregunta: p.pregunta,
      respuestaCorta: "¿Educación, gestión o investigación/tecnología?",
      scoreLabel: "Aciertos del modelo",
      scorePct: p.acc_modelo_pct,
      compareLabel: "Sin modelo (siempre lo más común)",
      comparePct: p.acc_trivial_pct,
      usar: false,
      badge: "Aún débil",
      lectura: p.lectura,
    });
  }
  if (data.pregunta_adjudicacion_mala) {
    const p = data.pregunta_adjudicacion_mala;
    cards.push({
      id: "adj_bad",
      pregunta: p.pregunta,
      respuestaCorta: "Entrenar solo con procesos ya cerrados",
      scoreLabel: "Calidad aparente",
      scorePct: p.metrica_valor,
      compareLabel: "Adivinar al azar",
      comparePct: 50,
      usar: false,
      badge: "No usar en vivo",
      lectura: p.lectura,
    });
  }

  const prox = outlook?.proximos_meses || [];
  const pico = prox.length
    ? prox.reduce((a, b) => (b.n_procesos_estimado > a.n_procesos_estimado ? b : a))
    : null;

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
      <div className="panel" style={{ marginBottom: "1rem" }}>
        <h3>{data.titulo || "Predicción"}</h3>
        <p className="note">
          {data.subtitulo ||
            "Primero el ritmo del mercado; después (opcional) un proceso concreto."}
        </p>
      </div>

      {data.para_empresa && (
        <div className="panel" style={{ marginBottom: "1rem" }}>
          <h3>{data.para_empresa.titulo}</h3>
          <div className="pred-grid" style={{ marginTop: "0.75rem" }}>
            {data.para_empresa.capas.map((c) => (
              <article key={c.id} className="pred-card pred-ok">
                <div className="pred-head">
                  <span className={`pred-badge ${c.id === "mercado" ? "ok" : "bad"}`}>
                    {c.id === "mercado" ? "Principal" : "Secundaria"}
                  </span>
                </div>
                <h4>{c.nombre}</h4>
                <p className="pred-short">{c.pregunta}</p>
                <p className="pred-lectura">
                  <strong>Uso:</strong> {c.uso}
                </p>
                <p className="note" style={{ marginTop: "0.4rem" }}>
                  {c.como}
                </p>
              </article>
            ))}
          </div>
        </div>
      )}

      {outlook && serie.length > 0 && (
        <div className="panel" style={{ marginBottom: "1rem" }}>
          <h3>Próximos meses: ritmo esperado del mercado CTeI</h3>
          <p className="note">{outlook.lectura}</p>
          {pico && (
            <div className="grid-3" style={{ margin: "0.85rem 0" }}>
              <div className="kpi">
                <div className="label">Mes más activo (proyección)</div>
                <div className="value" style={{ fontSize: "1.25rem" }}>
                  {pico.etiqueta}
                </div>
                <div className="hint">
                  ~{pico.n_procesos_estimado.toLocaleString("es-CO")} procesos
                </div>
              </div>
              <div className="kpi">
                <div className="label">Valor típico ese mes</div>
                <div className="value" style={{ fontSize: "1.25rem" }}>
                  {formatCop(pico.valor_sin_mega_estimado_cop)}
                </div>
                <div className="hint">sin megacontratos · pesos constantes</div>
              </div>
              <div className="kpi">
                <div className="label">Método</div>
                <div className="value" style={{ fontSize: "1.05rem" }}>
                  Estacionalidad
                </div>
                <div className="hint">
                  ancla hasta {outlook.ancla_hasta || "—"} · no es ML del mercado
                </div>
              </div>
            </div>
          )}

          <div style={{ width: "100%", height: 280 }}>
            <ResponsiveContainer>
              <LineChart data={serie}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(238,245,240,0.08)" />
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
                  formatter={(value: number, name: string) => [
                    Number(value).toLocaleString("es-CO"),
                    name,
                  ]}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="n_obs"
                  name="Observado"
                  stroke="#c4a35a"
                  strokeWidth={2.5}
                  connectNulls={false}
                  dot={{ r: 3 }}
                />
                <Line
                  type="monotone"
                  dataKey="n_proy"
                  name="Proyección"
                  stroke="#5ec4a8"
                  strokeWidth={2.5}
                  strokeDasharray="6 4"
                  connectNulls={false}
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {outlook.para_empresa && (
            <ul className="rosario-list" style={{ marginTop: "0.75rem" }}>
              {outlook.para_empresa.map((it) => (
                <li key={it}>{it}</li>
              ))}
            </ul>
          )}
          {outlook.honestidad && (
            <p className="note" style={{ marginTop: "0.75rem" }}>
              {outlook.honestidad}
            </p>
          )}
        </div>
      )}

      <div className="panel" style={{ marginBottom: "1rem" }}>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "0.75rem",
          }}
        >
          <div>
            <h3 style={{ marginBottom: "0.25rem" }}>
              Herramienta secundaria: un proceso concreto
            </h3>
            <p className="note" style={{ margin: 0 }}>
              No predice el mercado. Sirve cuando ya tienes (o publicas) un proceso
              competitivo y quieres priorizar: ¿vale la pena seguirlo? ¿en qué rango de
              monto suele caer?
            </p>
          </div>
          <button type="button" className="tab" onClick={() => setShowProceso((v) => !v)}>
            {showProceso ? "Ocultar" : "Abrir demo del modelo"}
          </button>
        </div>
        {k && showProceso && (
          <div className="grid-3" style={{ marginTop: "0.85rem" }}>
            <div className="kpi">
              <div className="label">Calidad adjudicación</div>
              <div className="value">{k.auc_pct}%</div>
              <div className="hint">frente a 50% al azar</div>
            </div>
            <div className="kpi">
              <div className="label">Procesos competitivos</div>
              <div className="value">{(k.n_competitivos || 0).toLocaleString("es-CO")}</div>
              <div className="hint">
                {(k.tasa_adjudicacion * 100).toFixed(0)}% se adjudican en los datos
              </div>
            </div>
            <div className="kpi">
              <div className="label">Evaluado con corte</div>
              <div className="value" style={{ fontSize: "1.2rem" }}>
                {k.fecha_corte}
              </div>
              <div className="hint">entrenar pasado · probar futuro</div>
            </div>
          </div>
        )}
      </div>

      {showProceso && (
        <>
          <Cap3PredictDemo />

          {data.universo && (
            <div className="panel" style={{ marginBottom: "1rem" }}>
              <h3>¿Sobre qué procesos se predice?</h3>
              <p className="note">{data.universo.lectura}</p>
            </div>
          )}

          <div className="panel" style={{ marginBottom: "1rem" }}>
            <h3>Calidad de cada predicción por proceso</h3>
            <p className="note">
              Cada tarjeta es una pregunta sobre <em>un</em> proceso. Si la barra del modelo
              no gana claro a “sin modelo”, no conviene usarlo.
            </p>

            {cards.length === 0 ? (
              <p className="error">
                No llegaron las predicciones desde la API. Reinicia el backend o recarga la
                página.
              </p>
            ) : (
              <div className="pred-grid">
                {cards.map((c) => (
                  <article
                    key={c.id}
                    className={`pred-card ${c.usar ? "pred-ok" : "pred-bad"}`}
                  >
                    <div className="pred-head">
                      <span className={`pred-badge ${c.usar ? "ok" : "bad"}`}>{c.badge}</span>
                    </div>
                    <h4>{c.pregunta}</h4>
                    <p className="pred-short">{c.respuestaCorta}</p>
                    <p className="pred-metric-label">{c.scoreLabel}</p>
                    <ScoreBar
                      scorePct={c.scorePct}
                      comparePct={c.comparePct}
                      compareLabel={c.compareLabel}
                      good={c.usar}
                    />
                    <p className="pred-lectura">{c.lectura}</p>
                  </article>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {data.reglas_uso && data.reglas_uso.length > 0 && (
        <div className="grid-2" style={{ marginBottom: "1rem" }}>
          {data.reglas_uso.map((bloque) => (
            <div className="panel" key={bloque.titulo}>
              <h3>{bloque.titulo}</h3>
              <ul className="rosario-list">
                {bloque.items.map((it) => (
                  <li key={it}>{it}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {data.cierre_rosario && (
        <div className="panel panel-rosario">
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
