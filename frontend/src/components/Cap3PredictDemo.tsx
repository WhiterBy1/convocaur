import { useEffect, useMemo, useState } from "react";
import { api, apiPost } from "../lib/api";
import { formatCop } from "../lib/format";

type Preset = {
  id: string;
  nombre: string;
  descripcion: string;
  payload: PredictInput;
};

type PredictInput = {
  precio_base_cop: number;
  duracion_meses: number;
  numero_de_lotes: number;
  mes_publicacion: number;
  anio_publicacion: number;
  modalidad: string;
  departamento: string;
  entidad: string;
};

type PredictMeta = {
  ok: boolean;
  error?: string;
  modalidades?: string[];
  departamentos?: string[];
  presets?: Preset[];
  modelo_adjudicacion?: string;
  fecha_corte?: string;
};

type PredictResult = {
  ok: boolean;
  adjudicacion: {
    probabilidad_pct: number;
    lectura: string;
    modelo: string;
  };
  presupuesto: {
    nombre: string;
    bin: string;
    lectura: string;
    nota?: string;
  };
  segmento: {
    nombre: string;
    codigo: string;
    lectura: string;
  };
};

const MES = [
  "",
  "Ene",
  "Feb",
  "Mar",
  "Abr",
  "May",
  "Jun",
  "Jul",
  "Ago",
  "Sep",
  "Oct",
  "Nov",
  "Dic",
];

const empty: PredictInput = {
  precio_base_cop: 500_000_000,
  duracion_meses: 12,
  numero_de_lotes: 1,
  mes_publicacion: 6,
  anio_publicacion: 2025,
  modalidad: "Licitación pública",
  departamento: "Distrito Capital de Bogotá",
  entidad: "",
};

export function Cap3PredictDemo() {
  const [meta, setMeta] = useState<PredictMeta | null>(null);
  const [form, setForm] = useState<PredictInput>(empty);
  const [result, setResult] = useState<PredictResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api<PredictMeta>("/api/secop/predict/meta")
      .then((m) => {
        setMeta(m);
        if (m.presets?.[0]) setForm({ ...m.presets[0].payload });
      })
      .catch((e) => setErr(String(e.message || e)));
  }, []);

  const set = (patch: Partial<PredictInput>) => setForm((f) => ({ ...f, ...patch }));

  const run = async (payload?: PredictInput) => {
    const body = payload || form;
    setBusy(true);
    setErr(null);
    try {
      const r = await apiPost<PredictResult>("/api/secop/predict", body);
      setResult(r);
      setForm(body);
    } catch (e) {
      setErr(String((e as Error).message || e));
      setResult(null);
    } finally {
      setBusy(false);
    }
  };

  const modalidades = useMemo(() => meta?.modalidades || [], [meta]);
  const departamentos = useMemo(() => meta?.departamentos || [], [meta]);

  return (
    <div className="panel panel-rosario" style={{ marginBottom: "1rem" }}>
      <h3>Simular un proceso (bid / no-bid)</h3>
      <p className="note">
        Caso de uso: tu empresa o Rosario ve una licitación competitiva y quiere saber si
        vale la pena seguirla. Elige un ejemplo o ajusta los datos — el backend corre los
        modelos reales sobre procesos históricos parecidos.
        {meta?.ok === false && (
          <>
            {" "}
            <span className="error">Modelos no cargaron: {meta.error}</span>
          </>
        )}
      </p>

      {meta?.presets && (
        <div className="tabs" style={{ marginBottom: "0.85rem" }}>
          {meta.presets.map((p) => (
            <button
              key={p.id}
              type="button"
              className="tab"
              disabled={busy}
              onClick={() => run(p.payload)}
              title={p.descripcion}
            >
              {p.nombre}
            </button>
          ))}
        </div>
      )}

      <div className="predict-form">
        <label>
          Precio base (COP)
          <input
            type="number"
            value={form.precio_base_cop}
            onChange={(e) => set({ precio_base_cop: Number(e.target.value) })}
          />
        </label>
        <label>
          Duración (meses)
          <input
            type="number"
            value={form.duracion_meses}
            onChange={(e) => set({ duracion_meses: Number(e.target.value) })}
          />
        </label>
        <label>
          Lotes
          <input
            type="number"
            value={form.numero_de_lotes}
            onChange={(e) => set({ numero_de_lotes: Number(e.target.value) })}
          />
        </label>
        <label>
          Mes publicación
          <select
            value={form.mes_publicacion}
            onChange={(e) => set({ mes_publicacion: Number(e.target.value) })}
          >
            {MES.slice(1).map((n, i) => (
              <option key={n} value={i + 1}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <label>
          Año
          <input
            type="number"
            value={form.anio_publicacion}
            onChange={(e) => set({ anio_publicacion: Number(e.target.value) })}
          />
        </label>
        <label>
          Modalidad
          <select
            value={form.modalidad}
            onChange={(e) => set({ modalidad: e.target.value })}
          >
            {(modalidades.length ? modalidades : [form.modalidad]).map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <label>
          Departamento
          <select
            value={form.departamento}
            onChange={(e) => set({ departamento: e.target.value })}
          >
            {(departamentos.length ? departamentos : [form.departamento]).map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <label>
          Entidad (opcional)
          <input
            type="text"
            placeholder="Si la conoces, mejora la predicción"
            value={form.entidad}
            onChange={(e) => set({ entidad: e.target.value })}
          />
        </label>
      </div>

      <div className="actions-row" style={{ marginTop: "0.85rem" }}>
        <button className="btn btn-primary" type="button" disabled={busy} onClick={() => run()}>
          {busy ? "Prediciendo…" : "Predecir ahora"}
        </button>
      </div>

      {err && <p className="error">{err}</p>}

      {result && (
        <div className="pred-grid" style={{ marginTop: "1rem" }}>
          <article className="pred-card pred-ok">
            <div className="pred-head">
              <span className="pred-badge ok">Adjudicación</span>
            </div>
            <h4>¿Se adjudicará?</h4>
            <p className="pred-short">
              Entrada: {formatCop(form.precio_base_cop)} · {form.modalidad} ·{" "}
              {MES[form.mes_publicacion]} {form.anio_publicacion}
            </p>
            <div className="kpi">
              <div className="label">Probabilidad</div>
              <div className="value">{result.adjudicacion.probabilidad_pct}%</div>
              <div className="hint">{result.adjudicacion.modelo}</div>
            </div>
            <div className="score-track" style={{ marginTop: "0.65rem" }}>
              <div
                className="score-fill good"
                style={{ width: `${Math.min(result.adjudicacion.probabilidad_pct, 100)}%` }}
              />
            </div>
            <p className="pred-lectura">{result.adjudicacion.lectura}</p>
          </article>

          <article className="pred-card pred-ok">
            <div className="pred-head">
              <span className="pred-badge ok">Presupuesto</span>
            </div>
            <h4>¿Qué rango de presupuesto?</h4>
            <div className="kpi">
              <div className="label">Rango estimado</div>
              <div className="value" style={{ fontSize: "1.5rem" }}>
                {result.presupuesto.nombre}
              </div>
              <div className="hint">{result.presupuesto.bin}</div>
            </div>
            <p className="pred-lectura">{result.presupuesto.lectura}</p>
            {result.presupuesto.nota && (
              <p className="note">{result.presupuesto.nota}</p>
            )}
          </article>

          <article className="pred-card pred-bad" style={{ gridColumn: "1 / -1" }}>
            <div className="pred-head">
              <span className="pred-badge bad">Segmento (débil)</span>
            </div>
            <h4>¿Educación, gestión o investigación?</h4>
            <div className="kpi">
              <div className="label">Pista del modelo</div>
              <div className="value" style={{ fontSize: "1.35rem" }}>
                {result.segmento.nombre}
              </div>
              <div className="hint">código {result.segmento.codigo}</div>
            </div>
            <p className="pred-lectura">{result.segmento.lectura}</p>
          </article>
        </div>
      )}
    </div>
  );
}
