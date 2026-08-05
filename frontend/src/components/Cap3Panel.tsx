import { useState } from "react";
import { motion } from "framer-motion";
import { Cap3PredictDemo } from "./Cap3PredictDemo";
import { Cap3MarketForecast, type OutlookMercado } from "./Cap3MarketForecast";

export type Capacidad3 = {
  titulo: string;
  subtitulo?: string;
  outlook_mercado?: OutlookMercado;
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
  scorePct: number;
  comparePct?: number;
  usar: boolean;
  badge: string;
};

type Props = { data: Capacidad3 };

export function Cap3Panel({ data }: Props) {
  const [showProceso, setShowProceso] = useState(false);
  const k = data.kpis;
  const outlook = data.outlook_mercado;

  const cards: PredCard[] = [];
  if (data.pregunta_adjudicacion) {
    const p = data.pregunta_adjudicacion;
    cards.push({
      id: "adj",
      pregunta: p.pregunta,
      scorePct: p.metrica_valor,
      comparePct: 50,
      usar: true,
      badge: "Sí usar",
    });
  }
  if (data.pregunta_presupuesto) {
    const p = data.pregunta_presupuesto;
    cards.push({
      id: "pres",
      pregunta: p.pregunta,
      scorePct: p.acc_modelo_pct,
      comparePct: p.acc_trivial_pct,
      usar: true,
      badge: "Sí usar",
    });
  }
  if (data.pregunta_segmento) {
    const p = data.pregunta_segmento;
    cards.push({
      id: "seg",
      pregunta: p.pregunta,
      scorePct: p.acc_modelo_pct,
      comparePct: p.acc_trivial_pct,
      usar: false,
      badge: "Aún débil",
    });
  }
  if (data.pregunta_adjudicacion_mala) {
    const p = data.pregunta_adjudicacion_mala;
    cards.push({
      id: "adj_bad",
      pregunta: p.pregunta,
      scorePct: p.metrica_valor,
      comparePct: 50,
      usar: false,
      badge: "No usar",
    });
  }

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
      {outlook && <Cap3MarketForecast outlook={outlook} />}

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
          <h3 style={{ margin: 0 }}>Demo: un proceso</h3>
          <button type="button" className="tab" onClick={() => setShowProceso((v) => !v)}>
            {showProceso ? "Ocultar" : "Abrir"}
          </button>
        </div>
        {k && showProceso && (
          <ul className="rosario-list hallazgos" style={{ marginTop: "0.65rem" }}>
            <li>
              Adjudicación AUC {k.auc_pct}% · {(k.n_competitivos || 0).toLocaleString("es-CO")}{" "}
              competitivos · corte {k.fecha_corte}
            </li>
          </ul>
        )}
      </div>

      {showProceso && (
        <>
          <Cap3PredictDemo />

          {cards.length > 0 && (
            <div className="panel" style={{ marginBottom: "1rem" }}>
              <h3>Calidad del modelo</h3>
              <div className="predict-quality">
                {cards.map((c) => (
                  <div key={c.id} className={`predict-quality-item ${c.usar ? "ok" : "bad"}`}>
                    <span className={`pred-badge ${c.usar ? "ok" : "bad"}`}>{c.badge}</span>
                    <strong>{c.pregunta}</strong>
                    <span className="hint">
                      {c.scorePct}%
                      {c.comparePct != null ? ` vs ${c.comparePct}% baseline` : ""}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {data.cierre_rosario && (
        <div className="panel panel-rosario">
          <h3>Hallazgos para Rosario</h3>
          <ul className="rosario-list hallazgos">
            {data.cierre_rosario.puntos.slice(0, 4).map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
          {data.nota_metodologica && (
            <details className="method-note">
              <summary>Metodología</summary>
              <p>{data.nota_metodologica}</p>
            </details>
          )}
        </div>
      )}
    </motion.div>
  );
}
