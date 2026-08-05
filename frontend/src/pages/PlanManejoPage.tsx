import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { cleanDocenteName } from "../lib/names";

type Docente = {
  id?: string;
  nombre?: string;
  facultad?: string;
  categoria?: string;
  score_final?: number;
  rol?: string;
  rank?: number;
};

type Oportunidad = {
  id: string;
  numero: string;
  titulo: string;
  objetivo_preview?: string;
  fecha_apertura?: string;
  reciente?: boolean;
  modo_elegibilidad?: string;
  prioridad: number;
  en_plan?: boolean;
  match: {
    top1_nombre?: string;
    top1_score?: number;
    n_docentes_equipo?: number;
    docentes?: Docente[];
  };
  secop_proxy?: {
    probabilidad?: number;
    probabilidad_pct?: number;
    lectura?: string;
    nota?: string;
    error?: string;
    presupuesto_bin?: string;
  } | null;
  plan_manejo?: {
    investigador_principal?: Docente;
    equipo?: Docente[];
    acciones?: string[];
    riesgos?: string[];
    lineas_tematicas?: string[];
    alianza_obligatoria?: boolean | null;
  } | null;
};

type PlanPayload = {
  ok: boolean;
  generado_en?: string;
  resumen: {
    n_elegibles?: number;
    n_oportunidades?: number;
    n_con_ranking?: number;
    n_en_plan?: number;
    n_recientes?: number;
    formula_prioridad?: string;
    umbral_equipo?: number;
  };
  modelo_secop?: { ok?: boolean; modelo_adjudicacion?: string; error?: string };
  mercado_secop?: {
    n_procesos_cteI?: number;
    n_competitivos?: number;
    auc_adjudicacion?: number;
    nota?: string;
  };
  nota_metodologica?: string;
  oportunidades: Oportunidad[];
  planes: Oportunidad[];
};

function score(n?: number | null) {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toFixed(2);
}

function clamp01(n?: number | null) {
  if (n == null || Number.isNaN(n)) return 0;
  return Math.max(0, Math.min(1, n));
}

function shortCategoria(cat?: string | null) {
  if (!cat) return "";
  return String(cat).split("(")[0].trim();
}

function Meter({
  label,
  value,
  display,
  tone = "accent",
}: {
  label: string;
  value?: number | null;
  display: string;
  tone?: "accent" | "wheat" | "ink";
}) {
  const w = clamp01(value) * 100;
  return (
    <div className={`plan-meter plan-meter-${tone}`}>
      <div className="plan-meter-head">
        <span>{label}</span>
        <strong>{display}</strong>
      </div>
      <div className="plan-meter-track" aria-hidden="true">
        <span style={{ width: `${w}%` }} />
      </div>
    </div>
  );
}

function DocenteRow({
  d,
  index,
}: {
  d: Docente;
  index: number;
}) {
  const rol = index === 0 ? "Investigador" : "Co-investigador";
  const isIp = index === 0;
  return (
    <li className={`plan-person ${isIp ? "is-ip" : ""}`}>
      <span className={`plan-role-badge ${isIp ? "ip" : "co"}`}>{rol}</span>
      <div className="plan-person-main">
        <strong>{cleanDocenteName(d.nombre, d.id)}</strong>
        <span className="plan-person-meta">
          {d.facultad || "Facultad sin dato"}
          {d.categoria ? ` · ${shortCategoria(d.categoria)}` : ""}
        </span>
      </div>
      <div className="plan-person-score">
        <span>{score(d.score_final)}</span>
        <div className="plan-meter-track thin" aria-hidden="true">
          <span style={{ width: `${clamp01(d.score_final) * 100}%` }} />
        </div>
      </div>
    </li>
  );
}

export function PlanManejoPage() {
  const [data, setData] = useState<PlanPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api<PlanPayload>("/api/plan/manejo?top=8")
      .then((d) => {
        setData(d);
        const first = d.planes?.[0]?.id || d.oportunidades?.[0]?.id || null;
        setSelected(first);
      })
      .catch((e) => setErr(String(e.message || e)))
      .finally(() => setLoading(false));
  }, []);

  const active =
    data?.oportunidades.find((o) => o.id === selected) ||
    data?.planes?.[0] ||
    null;

  const padj = active?.secop_proxy?.probabilidad ?? null;
  const equipo =
    active?.plan_manejo?.equipo?.length
      ? active.plan_manejo.equipo
      : active?.match.docentes || [];

  return (
    <div className="plan-page">
      <header className="plan-hero">
        <p className="eyebrow">Matching + SECOP Cap.3</p>
        <h1>Plan de manejo</h1>
        <p className="section-lead">
          Prioriza convocatorias elegibles, muestra el equipo docente sugerido
          y la señal de adjudicación SECOP. Un vistazo para decidir dónde
          concentrar esfuerzo.
        </p>
      </header>

      {loading && <p className="note">Calculando oportunidades…</p>}
      {err && <p className="error">{err}</p>}

      {data && (
        <>
          <section className="plan-kpis" aria-label="Resumen">
            <div>
              <span className="kpi-label">Elegibles</span>
              <strong className="kpi-num">{data.resumen.n_elegibles ?? "—"}</strong>
            </div>
            <div>
              <span className="kpi-label">En radar</span>
              <strong className="kpi-num">{data.resumen.n_oportunidades ?? "—"}</strong>
            </div>
            <div>
              <span className="kpi-label">Con plan</span>
              <strong className="kpi-num">{data.resumen.n_en_plan ?? "—"}</strong>
            </div>
            <div>
              <span className="kpi-label">Modelo SECOP</span>
              <strong className="kpi-num plan-kpi-sm">
                {data.modelo_secop?.ok ? "activo" : "offline"}
              </strong>
            </div>
          </section>

          <div className="plan-layout">
            <aside className="plan-list panel">
              <h3>Cola de prioridad</h3>
              <p className="note">
                Orden por score compuesto. Las marcadas tienen plan de equipo.
              </p>
              <ul>
                {data.oportunidades.slice(0, 20).map((o, idx) => (
                  <li key={o.id}>
                    <button
                      type="button"
                      className={o.id === selected ? "active" : undefined}
                      onClick={() => setSelected(o.id)}
                    >
                      <span className="plan-list-top">
                        <span className="plan-rank-idx">#{idx + 1}</span>
                        <span>Conv. {o.numero}</span>
                        {o.en_plan && <em>plan</em>}
                      </span>
                      <span className="plan-list-title">{o.titulo}</span>
                      <div className="plan-list-bars">
                        <span>
                          Prioridad
                          <b>{score(o.prioridad)}</b>
                        </span>
                        <div className="plan-meter-track thin" aria-hidden="true">
                          <span style={{ width: `${clamp01(o.prioridad) * 100}%` }} />
                        </div>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            </aside>

            <section className="plan-detail">
              {!active && <p className="note">Selecciona una convocatoria.</p>}
              {active && (
                <>
                  <div className="panel plan-detail-head">
                    <div className="plan-detail-tags">
                      <span className="chip">Elegible</span>
                      {active.en_plan && (
                        <span className="chip chip-accent">Plan listo</span>
                      )}
                      {active.modo_elegibilidad && (
                        <span className="chip">{active.modo_elegibilidad}</span>
                      )}
                      {active.plan_manejo?.alianza_obligatoria === true && (
                        <span className="chip chip-warn">Alianza obligatoria</span>
                      )}
                    </div>
                    <h2>
                      <span className="plan-conv-num">#{active.numero}</span>{" "}
                      {active.titulo}
                    </h2>
                    {active.objetivo_preview && (
                      <p className="plan-objetivo">{active.objetivo_preview}</p>
                    )}

                    <div className="plan-signal-grid">
                      <Meter
                        label="Prioridad"
                        value={active.prioridad}
                        display={score(active.prioridad)}
                        tone="ink"
                      />
                      <Meter
                        label="Match docente"
                        value={active.match.top1_score}
                        display={score(active.match.top1_score)}
                        tone="accent"
                      />
                      <Meter
                        label="P(adjudicación SECOP)"
                        value={padj}
                        display={
                          active.secop_proxy?.probabilidad_pct != null
                            ? `${active.secop_proxy.probabilidad_pct}%`
                            : "—"
                        }
                        tone="wheat"
                      />
                    </div>

                    {active.secop_proxy?.lectura && (
                      <p className="plan-lectura">{active.secop_proxy.lectura}</p>
                    )}

                    <div className="plan-links">
                      <Link className="btn btn-ghost" to="/matching">
                        Matching
                      </Link>
                      <Link className="btn btn-ghost" to="/secop">
                        SECOP Cap.3
                      </Link>
                    </div>
                  </div>

                  <div className="panel">
                    <div className="plan-section-head">
                      <h3>Equipo sugerido</h3>
                      <p className="note">
                        #1 = Investigador · resto = Co-investigador
                      </p>
                    </div>
                    {!equipo.length ? (
                      <p className="note">Sin ranking para esta convocatoria.</p>
                    ) : (
                      <ul className="plan-people">
                        {equipo.map((d, i) => (
                          <DocenteRow key={d.id || i} d={d} index={i} />
                        ))}
                      </ul>
                    )}
                  </div>

                  {active.plan_manejo ? (
                    <>
                      <div className="plan-split">
                        <div className="panel">
                          <h3>Qué hacer</h3>
                          <ol className="plan-acciones">
                            {(active.plan_manejo.acciones || []).map((a) => (
                              <li key={a}>{a}</li>
                            ))}
                          </ol>
                        </div>
                        <div className="panel plan-riesgos-panel">
                          <h3>Atención / riesgos</h3>
                          <ul className="plan-riesgos">
                            {(active.plan_manejo.riesgos || []).map((r) => (
                              <li key={r}>{r}</li>
                            ))}
                          </ul>
                        </div>
                      </div>
                      {!!(active.plan_manejo.lineas_tematicas || []).length && (
                        <div className="panel plan-lineas">
                          <h3>Líneas a cubrir</h3>
                          <div className="chip-row plan-lineas-row">
                            {active.plan_manejo.lineas_tematicas!.map((ln) => (
                              <span className="chip" key={ln}>
                                {ln}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="panel">
                      <h3>Sin plan detallado</h3>
                      <p className="note">
                        Está en el radar, pero fuera del top{" "}
                        {data.resumen.n_en_plan}. Elige una marcada como{" "}
                        <em>plan</em> para ver acciones y riesgos.
                      </p>
                    </div>
                  )}

                  <details className="plan-method">
                    <summary>Cómo se calcula</summary>
                    <p>{data.nota_metodologica}</p>
                    <p className="note">{data.resumen.formula_prioridad}</p>
                  </details>
                </>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
