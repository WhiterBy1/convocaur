import { useEffect, useState } from "react";
import { Cap1Panel, type Capacidad1 } from "../components/Cap1Panel";
import { Cap2Panel, type Capacidad2 } from "../components/Cap2Panel";
import { Cap3Panel, type Capacidad3 } from "../components/Cap3Panel";
import { api } from "../lib/api";

type Dashboard = {
  meta: Record<string, string>;
  universo: Record<string, number | string>;
  capacidad_1: Capacidad1;
  capacidad_2: Capacidad2;
  capacidad_3: Capacidad3;
};

export function SecopPage() {
  const [tab, setTab] = useState<1 | 2 | 3>(1);
  const [data, setData] = useState<Dashboard | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api<Dashboard>("/api/secop/dashboard")
      .then(setData)
      .catch((e) => setErr(String(e.message || e)));
  }, []);

  if (err) return <p className="error">{err}</p>;
  if (!data) return <p className="loading">Cargando análisis SECOP…</p>;

  return (
    <section className="section" style={{ paddingTop: "2rem" }}>
      <p className="section-kicker">SECOP II · mercado CTeI</p>
      <h2>Tres capacidades del reto</h2>
      <p className="section-lead">
        Lectura del mercado de contratación pública afín a ciencia, tecnología e
        innovación — pensada para decidir cuándo y dónde mirar oportunidades para
        Rosario.
      </p>

      <div className="tabs">
        {(
          [
            [1, "1 · Tendencias"],
            [2, "2 · Mercado"],
            [3, "3 · Predicción"],
          ] as const
        ).map(([n, label]) => (
          <button
            key={n}
            className={`tab ${tab === n ? "active" : ""}`}
            onClick={() => setTab(n)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 1 && <Cap1Panel data={data.capacidad_1} />}
      {tab === 2 && <Cap2Panel data={data.capacidad_2} />}
      {tab === 3 && <Cap3Panel data={data.capacidad_3} />}
    </section>
  );
}
