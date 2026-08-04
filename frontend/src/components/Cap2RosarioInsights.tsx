import { formatCop, formatCopShort } from "../lib/format";

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

export function Cap2RosarioInsights({ data }: Props) {
  const p = data.perfil || {};
  const compradores = (data.compradores || []).slice(0, 12);
  const comps = (data.competidores_frecuentes || []).slice(0, 12);
  const peers = (data.peers_ies || []).slice(0, 10);

  return (
    <div className="panel panel-rosario" style={{ marginBottom: "1rem" }}>
      <h3>{data.titulo || "Rosario en la red SECOP–CTeI"}</h3>
      {data.subtitulo ? <p className="note">{data.subtitulo}</p> : null}

      <div className="grid-3" style={{ margin: "0.75rem 0" }}>
        <div className="kpi">
          <div className="label">Valor adjudicado (Rosario)</div>
          <div className="value">{formatCopShort(p.valor_adjudicado_cop || 0)}</div>
          <div className="hint">NIT {p.nit || "—"} · {p.n_procesos ?? "—"} procesos</div>
        </div>
        <div className="kpi">
          <div className="label">Compradores</div>
          <div className="value">{p.n_entidades_compradoras ?? "—"}</div>
          <div className="hint">
            entidades que le adjudicaron · {p.n_competidores_con_overlap ?? "—"} rivales con overlap
          </div>
        </div>
        <div className="kpi">
          <div className="label">Ranking entre IES</div>
          <div className="value">#{p.ranking_entre_ies ?? "—"}</div>
          <div className="hint">de {p.n_ies_en_universo ?? "—"} IES/centros en este universo CTeI</div>
        </div>
      </div>

      {data.lecturas && data.lecturas.length > 0 ? (
        <ul className="rosario-list">
          {data.lecturas.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      ) : null}

      {compradores.length > 0 ? (
        <div style={{ marginTop: "1.25rem" }}>
          <h4>Quién le compra a Rosario</h4>
          <p className="note">
            Share of wallet = % del gasto CTeI de esa entidad que va a Rosario. % ingresos =
            peso de ese comprador en la facturación Rosario.
          </p>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Entidad</th>
                  <th>Valor con Rosario</th>
                  <th>% ingresos UR</th>
                  <th>Share of wallet</th>
                  <th>Procesos</th>
                </tr>
              </thead>
              <tbody>
                {compradores.map((c) => (
                  <tr key={c.entidad}>
                    <td title={c.entidad}>
                      {c.entidad.length > 48 ? c.entidad.slice(0, 46) + "…" : c.entidad}
                    </td>
                    <td>{formatCopShort(c.valor_con_rosario_cop)}</td>
                    <td>{c.pct_ingresos_rosario}%</td>
                    <td>{c.share_of_wallet_pct}%</td>
                    <td>{c.n_procesos}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {comps.length > 0 ? (
        <div style={{ marginTop: "1.25rem" }}>
          <h4>Competidores frecuentes</h4>
          <p className="note">
            Proveedores que también ganan contratos en las mismas entidades donde Rosario ya
            es proveedor. Orden: más entidades en común, luego valor del rival en ese overlap.
          </p>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Proveedor</th>
                  <th>Entidades en común</th>
                  <th>Valor rival (overlap)</th>
                  <th>Valor Rosario (overlap)</th>
                  <th>Ratio</th>
                  <th>Tipo</th>
                </tr>
              </thead>
              <tbody>
                {comps.map((c) => (
                  <tr key={c.nit}>
                    <td title={c.nombre}>
                      {c.nombre.length > 42 ? c.nombre.slice(0, 40) + "…" : c.nombre}
                    </td>
                    <td>{c.n_entidades_compartidas}</td>
                    <td>{formatCopShort(c.valor_rival_en_compartidas_cop)}</td>
                    <td>{formatCopShort(c.valor_rosario_en_compartidas_cop)}</td>
                    <td>{c.ratio_rival_vs_rosario}×</td>
                    <td>{c.es_ies ? "IES" : "Otro"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {peers.length > 0 ? (
        <div style={{ marginTop: "1.25rem" }}>
          <h4>Otras IES en el universo CTeI</h4>
          <p className="note">Por valor total adjudicado (proxy UNSPSC 80/81/86).</p>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Institución</th>
                  <th>Valor total</th>
                  <th>Entidades</th>
                  <th>vs Rosario</th>
                </tr>
              </thead>
              <tbody>
                {peers.map((p) => (
                  <tr key={p.nit}>
                    <td title={p.nombre}>
                      {p.nombre.length > 48 ? p.nombre.slice(0, 46) + "…" : p.nombre}
                    </td>
                    <td>{formatCopShort(p.valor_total_cop)}</td>
                    <td>{p.n_entidades}</td>
                    <td>{p.vs_rosario_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {data.nota ? (
        <details className="method-note" style={{ marginTop: "1rem" }}>
          <summary>Metodología (red Rosario)</summary>
          <p>{data.nota}</p>
          <p className="note" style={{ marginTop: "0.5rem" }}>
            Totales de referencia: {formatCop(p.valor_adjudicado_cop || 0)} adjudicados a Rosario
            en el CSV limpio Cap.2.
          </p>
        </details>
      ) : null}
    </div>
  );
}
