import { useEffect, useMemo, useState } from "react";
import { api, apiPost } from "../lib/api";
import { formatCop, formatCopShort } from "../lib/format";

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

function shortPreset(nombre: string) {
  const t = nombre.split("·")[0]?.trim() || nombre;
  return t.length > 28 ? t.slice(0, 26) + "…" : t;
}

export function Cap3PredictDemo() {
  const [meta, setMeta] = useState<PredictMeta | null>(null);
  const [form, setForm] = useState<PredictInput>(empty);
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [result, setResult] = useState<PredictResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api<PredictMeta>("/api/secop/predict/meta")
      .then((m) => {
        setMeta(m);
        if (m.presets?.[0]) {
          setForm({ ...m.presets[0].payload });
          setActivePreset(m.presets[0].id);
        }
      })
      .catch((e) => setErr(String(e.message || e)));
  }, []);

  const set = (patch: Partial<PredictInput>) => {
    setActivePreset(null);
    setForm((f) => ({ ...f, ...patch }));
  };

  const run = async (payload?: PredictInput, presetId?: string) => {
    const body = payload || form;
    setBusy(true);
    setErr(null);
    try {
      const r = await apiPost<PredictResult>("/api/secop/predict", body);
      setResult(r);
      setForm(body);
      if (presetId) setActivePreset(presetId);
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
    <div className="panel predict-demo" style={{ marginBottom: "1rem" }}>
      <div className="predict-demo-head">
        <h3>Simular un proceso</h3>
        {meta?.modelo_adjudicacion ? (
          <span className="predict-meta-chip">{meta.modelo_adjudicacion}</span>
        ) : null}
      </div>

      {meta?.ok === false && (
        <p className="error">Modelos no cargaron: {meta.error}</p>
      )}

      {meta?.presets && meta.presets.length > 0 ? (
        <div className="predict-presets">
          {meta.presets.map((p) => (
            <button
              key={p.id}
              type="button"
              className={`predict-preset ${activePreset === p.id ? "active" : ""}`}
              disabled={busy}
              title={p.descripcion || p.nombre}
              onClick={() => run(p.payload, p.id)}
            >
              {shortPreset(p.nombre)}
            </button>
          ))}
        </div>
      ) : null}

      <div className="predict-form">
        <label className="pf-field pf-span-2">
          <span>Precio base</span>
          <input
            type="number"
            value={form.precio_base_cop}
            onChange={(e) => set({ precio_base_cop: Number(e.target.value) })}
          />
          <em>{formatCopShort(form.precio_base_cop)}</em>
        </label>

        <label className="pf-field">
          <span>Duración (meses)</span>
          <input
            type="number"
            min={1}
            value={form.duracion_meses}
            onChange={(e) => set({ duracion_meses: Number(e.target.value) })}
          />
        </label>

        <label className="pf-field">
          <span>Lotes</span>
          <input
            type="number"
            min={1}
            value={form.numero_de_lotes}
            onChange={(e) => set({ numero_de_lotes: Number(e.target.value) })}
          />
        </label>

        <label className="pf-field">
          <span>Mes</span>
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

        <label className="pf-field">
          <span>Año</span>
          <input
            type="number"
            value={form.anio_publicacion}
            onChange={(e) => set({ anio_publicacion: Number(e.target.value) })}
          />
        </label>

        <label className="pf-field pf-span-2">
          <span>Modalidad</span>
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

        <label className="pf-field pf-span-2">
          <span>Departamento</span>
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

        <label className="pf-field pf-span-4">
          <span>Entidad (opcional)</span>
          <input
            type="text"
            placeholder="Nombre de la entidad contratante"
            value={form.entidad}
            onChange={(e) => set({ entidad: e.target.value })}
          />
        </label>
      </div>

      <div className="predict-actions">
        <button
          className="btn btn-primary"
          type="button"
          disabled={busy || meta?.ok === false}
          onClick={() => run()}
        >
          {busy ? "Prediciendo…" : "Predecir"}
        </button>
        {result ? (
          <span className="predict-summary">
            {formatCop(form.precio_base_cop)} · {form.modalidad} ·{" "}
            {MES[form.mes_publicacion]} {form.anio_publicacion}
          </span>
        ) : null}
      </div>

      {err && <p className="error">{err}</p>}

      {result && (
        <div className="predict-results">
          <div className="predict-result">
            <div className="label">Adjudicación</div>
            <div className="value">{result.adjudicacion.probabilidad_pct}%</div>
            <div className="predict-bar">
              <div
                className="predict-bar-fill"
                style={{ width: `${Math.min(result.adjudicacion.probabilidad_pct, 100)}%` }}
              />
            </div>
          </div>
          <div className="predict-result">
            <div className="label">Rango presupuesto</div>
            <div className="value value-sm">{result.presupuesto.nombre}</div>
            <div className="hint">{result.presupuesto.bin}</div>
          </div>
          <div className="predict-result muted">
            <div className="label">Segmento (débil)</div>
            <div className="value value-sm">{result.segmento.nombre}</div>
            <div className="hint">UNSPSC {result.segmento.codigo}</div>
          </div>
        </div>
      )}
    </div>
  );
}
