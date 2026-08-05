import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { forceCollide, forceX, forceY } from "d3-force-3d";
import { formatCop, formatCopShort } from "../lib/format";

export type RedMercado = {
  titulo?: string;
  subtitulo?: string;
  lectura?: string;
  meta?: {
    n_nodos: number;
    n_aristas: number;
    n_entidades?: number;
    n_proveedores?: number;
    n_anclas_urosario?: number;
    n_edges_universo?: number;
    modo?: string;
  };
  leyenda?: { kind: string; color: string; nombre: string }[];
  como_leer?: string[];
  palacios?: { id: string; nombre: string; degree: number; valor: number }[];
  nodes: {
    id: string;
    kind: string;
    label: string;
    nombre: string;
    valor: number;
    degree: number;
    nit?: string;
    palacio?: number;
    ancla?: boolean;
    ancla_id?: string | null;
    competidor?: boolean;
    rol?: string;
  }[];
  links: {
    source: string | { id: string };
    target: string | { id: string };
    valor: number;
    n_procesos: number;
    peso?: number;
    dependencia_proveedor_pct?: number;
    participacion_entidad_pct?: number;
    segmento?: string;
    depto?: string;
  }[];
};

type Props = {
  red: RedMercado;
  /** Vistas alternativas (mercado / ego Rosario) */
  vistas?: { id: string; label: string; red: RedMercado }[];
};

/**
 * Ajusta estos valores y guarda — Vite recarga solo.
 *
 * | Variable            | Si subes…                         | Si bajas…                         |
 * |---------------------|-----------------------------------|-----------------------------------|
 * | linkDistance        | nodos unidos más separados        | más pegados                       |
 * | linkStrength        | aristas más tirantes              | más flojas                        |
 * | chargeStrength      | más negativo = menos amontonados  | cerca de 0 = más apelotonados     |
 * | chargeDistanceMax   | rechazo actúa más lejos           | islas no salen disparadas         |
 * | centerStrength      | todo más cerca del centro         | componentes libres flotan         |
 * | collidePadding      | más aire entre círculos           | más solapamiento                  |
 * | soloComponenteMayor | true = oculta islas sueltas       | false = muestra todo              |
 */
export const NETWORK_LAYOUT = {
  linkDistance: 95,
  linkStrength: 0.55,
  chargeStrength: -320,
  chargeDistanceMax: 240,
  centerStrength: 0.12,
  collidePadding: 10,
  cooldownTicks: 140,
  alphaDecay: 0.022,
  velocityDecay: 0.4,
  soloComponenteMayor: false,
  zoomPadding: 48,
  nodeSizeMin: 5,
  nodeSizeMax: 16,
};

const COLOR = {
  entidad: "#7a8dbd",
  proveedor: "#b7c7d1",
  competidor: "#8b3a4a",
  ancla: "#f6e0b6",
  dim: "rgba(62,75,142,0.14)",
  link: "rgba(122,141,189,0.35)",
  linkHot: "rgba(122,141,189,0.85)",
  stroke: "#5a6f9e",
  label: "#4a3a48",
};

function linkId(l: RedMercado["links"][0]): [string, string] {
  const s = typeof l.source === "object" ? l.source.id : l.source;
  const t = typeof l.target === "object" ? l.target.id : l.target;
  return [s, t];
}

function largestComponent(
  nodes: RedMercado["nodes"],
  links: RedMercado["links"]
): { nodes: RedMercado["nodes"]; links: RedMercado["links"] } {
  const adj = new Map<string, string[]>();
  for (const n of nodes) adj.set(n.id, []);
  for (const l of links) {
    const [s, t] = linkId(l);
    if (!adj.has(s) || !adj.has(t)) continue;
    adj.get(s)!.push(t);
    adj.get(t)!.push(s);
  }
  const seen = new Set<string>();
  let best: Set<string> = new Set();
  for (const n of nodes) {
    if (seen.has(n.id)) continue;
    const stack = [n.id];
    const comp = new Set<string>();
    seen.add(n.id);
    while (stack.length) {
      const u = stack.pop()!;
      comp.add(u);
      for (const v of adj.get(u) || []) {
        if (!seen.has(v)) {
          seen.add(v);
          stack.push(v);
        }
      }
    }
    if (comp.size > best.size) best = comp;
  }
  const keepNodes = nodes.filter((n) => best.has(n.id));
  const keepLinks = links.filter((l) => {
    const [s, t] = linkId(l);
    return best.has(s) && best.has(t);
  });
  return { nodes: keepNodes, links: keepLinks };
}

export function Cap2NetworkGraph({ red: redProp, vistas }: Props) {
  const [vistaId, setVistaId] = useState(vistas?.[0]?.id || "default");
  const red = useMemo(() => {
    if (!vistas?.length) return redProp;
    return vistas.find((v) => v.id === vistaId)?.red || vistas[0].red || redProp;
  }, [redProp, vistas, vistaId]);

  const fgRef = useRef<any>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 900, h: 560 });
  const [query, setQuery] = useState("");
  const [hover, setHover] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [kindFilter, setKindFilter] = useState<"todos" | "entidad" | "proveedor">("todos");
  const [soloMayor, setSoloMayor] = useState(NETWORK_LAYOUT.soloComponenteMayor);
  const L = NETWORK_LAYOUT;

  useEffect(() => {
    setSelected(null);
    setHover(null);
    setQuery("");
  }, [vistaId, red.meta?.n_nodos]);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setSize({ w: el.clientWidth, h: Math.max(520, Math.min(680, el.clientWidth * 0.64)) });
    });
    ro.observe(el);
    setSize({ w: el.clientWidth, h: Math.max(520, Math.min(680, el.clientWidth * 0.64)) });
    return () => ro.disconnect();
  }, []);

  const baseGraph = useMemo(() => {
    if (soloMayor) return largestComponent(red.nodes, red.links);
    return { nodes: red.nodes, links: red.links };
  }, [red, soloMayor]);

  const maxValor = useMemo(
    () => Math.max(...baseGraph.nodes.map((n) => n.valor), 1),
    [baseGraph.nodes]
  );

  const nodeRadius = useCallback(
    (node: { valor: number }) => {
      const t = Math.sqrt(node.valor / maxValor);
      return L.nodeSizeMin + t * (L.nodeSizeMax - L.nodeSizeMin);
    },
    [maxValor, L.nodeSizeMin, L.nodeSizeMax]
  );

  const neighbors = useMemo(() => {
    const m = new Map<string, Set<string>>();
    for (const n of baseGraph.nodes) m.set(n.id, new Set());
    for (const l of baseGraph.links) {
      const [s, t] = linkId(l);
      m.get(s)?.add(t);
      m.get(t)?.add(s);
    }
    return m;
  }, [baseGraph]);

  const graphData = useMemo(() => {
    const q = query.trim().toLowerCase();
    let seed = baseGraph.nodes;
    if (kindFilter !== "todos") {
      seed = seed.filter((n) => n.kind === kindFilter);
    }
    if (q) {
      seed = seed.filter(
        (n) =>
          n.label.toLowerCase().includes(q) ||
          n.nombre.toLowerCase().includes(q) ||
          (n.nit || "").toLowerCase().includes(q)
      );
    }
    if (kindFilter !== "todos" || q) {
      const keep = new Set(seed.map((n) => n.id));
      for (const id of [...keep]) {
        neighbors.get(id)?.forEach((v) => keep.add(v));
      }
      seed = baseGraph.nodes.filter((n) => keep.has(n.id));
    }
    const ids = new Set(seed.map((n) => n.id));
    const links = baseGraph.links.filter((l) => {
      const [s, t] = linkId(l);
      return ids.has(s) && ids.has(t);
    });
    return {
      nodes: seed.map((n) => ({ ...n })),
      links: links.map((l) => ({ ...l })),
    };
  }, [baseGraph, query, kindFilter, neighbors]);

  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    try {
      // Reusar fuerzas internas del force-graph (no reemplazar link con otro array)
      const charge = fg.d3Force("charge");
      if (charge?.strength) {
        charge.strength(L.chargeStrength);
        if (typeof charge.distanceMax === "function") {
          charge.distanceMax(L.chargeDistanceMax);
        }
      }
      const link = fg.d3Force("link");
      if (link?.distance) {
        link.distance(L.linkDistance);
        if (typeof link.strength === "function") link.strength(L.linkStrength);
      }
      fg.d3Force("x", forceX(0).strength(L.centerStrength));
      fg.d3Force("y", forceY(0).strength(L.centerStrength));
      fg.d3Force(
        "collide",
        forceCollide()
          .radius((n: any) => nodeRadius(n) + L.collidePadding)
          .strength(0.85)
          .iterations(2)
      );
      fg.d3ReheatSimulation();
    } catch (e) {
      console.warn("[Cap2NetworkGraph] fuerzas:", e);
    }
  }, [graphData.nodes.length, graphData.links.length, L, nodeRadius]);

  const focus = selected || hover;

  const selectedNode = useMemo(
    () => baseGraph.nodes.find((n) => n.id === selected) || null,
    [baseGraph.nodes, selected]
  );

  const selectedLinks = useMemo(() => {
    if (!selected) return [];
    return baseGraph.links
      .filter((l) => {
        const [s, t] = linkId(l);
        return s === selected || t === selected;
      })
      .sort((a, b) => b.valor - a.valor)
      .slice(0, 8);
  }, [baseGraph.links, selected]);

  const paintNode = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const r = nodeRadius(node);
      const isFocus = focus === node.id;
      const neigh = focus ? neighbors.get(focus) : null;
      const dim = focus && !isFocus && !neigh?.has(node.id);
      const color = node.ancla
        ? COLOR.ancla
        : node.competidor
          ? COLOR.competidor
          : node.kind === "entidad"
            ? COLOR.entidad
            : COLOR.proveedor;

      ctx.beginPath();
      ctx.arc(node.x, node.y, r * (node.ancla ? 1.25 : 1), 0, 2 * Math.PI);
      ctx.fillStyle = dim ? COLOR.dim : color;
      ctx.globalAlpha = dim ? 0.3 : 0.95;
      ctx.fill();

      if (isFocus || node.palacio || node.ancla) {
        ctx.strokeStyle = node.ancla
          ? "#ffffff"
          : isFocus
            ? COLOR.stroke
            : "rgba(122,141,189,0.7)";
        ctx.lineWidth = ((isFocus || node.ancla) ? 2.6 : 1.3) / globalScale;
        ctx.stroke();
      }

      if (!dim && (isFocus || node.ancla || (node.degree || 0) >= 5)) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r * 1.45, 0, 2 * Math.PI);
        ctx.fillStyle = color;
        ctx.globalAlpha = 0.14;
        ctx.fill();
      }

      const showLabel =
        isFocus ||
        node.ancla ||
        node.competidor ||
        globalScale > 1.35 ||
        (qMatch(query, node) && !!query);
      if (showLabel && !dim) {
        ctx.globalAlpha = 1;
        ctx.font = `${(node.ancla ? 12 : 11) / globalScale}px "Source Sans 3", sans-serif`;
        ctx.fillStyle = COLOR.label;
        ctx.textAlign = "center";
        ctx.fillText(node.label, node.x, node.y + r + 11 / globalScale);
      }
      ctx.globalAlpha = 1;
    },
    [focus, neighbors, nodeRadius, query]
  );

  const paintLink = useCallback(
    (link: any, ctx: CanvasRenderingContext2D) => {
      const s = link.source;
      const t = link.target;
      if (s?.x == null || t?.x == null) return;
      const sid = s.id || s;
      const tid = t.id || t;
      const hot = !!(focus && (sid === focus || tid === focus));
      const dim = !!(focus && !hot);
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);
      ctx.strokeStyle = hot ? COLOR.linkHot : dim ? "rgba(122,141,189,0.08)" : COLOR.link;
      ctx.lineWidth = hot ? 1.6 : Math.min(0.5 + (link.peso || 0.1) * 0.25, 1.8);
      ctx.globalAlpha = dim ? 0.2 : 0.85;
      ctx.stroke();
      ctx.globalAlpha = 1;
    },
    [focus]
  );

  const centerOn = (id: string) => {
    setSelected(id);
    const node = graphData.nodes.find((n) => n.id === id) as any;
    if (node && fgRef.current && node.x != null) {
      fgRef.current.centerAt(node.x, node.y, 600);
      fgRef.current.zoom(2.0, 600);
    }
  };

  return (
    <div className="panel panel-rosario" style={{ marginBottom: "1rem" }}>
      <h3>{red.titulo || "Red del mercado"}</h3>
      <p className="note">{red.subtitulo || red.lectura}</p>
      {vistas && vistas.length > 1 ? (
        <div className="tabs" style={{ marginBottom: "0.75rem" }}>
          {vistas.map((v) => (
            <button
              key={v.id}
              type="button"
              className={`tab ${vistaId === v.id ? "active" : ""}`}
              onClick={() => setVistaId(v.id)}
            >
              {v.label}
            </button>
          ))}
        </div>
      ) : null}
      {red.meta?.n_edges_universo ? (
        <p className="note" style={{ marginTop: 0 }}>
          Universo CTeI: {red.meta.n_edges_universo.toLocaleString("es-CO")} vínculos
          entidad↔proveedor · mapa actual: {red.meta.n_nodos} nodos (muestra navegable; no se
          renderizan los ~17k proveedores a la vez).
        </p>
      ) : null}

      <div className="grid-3" style={{ margin: "0.75rem 0" }}>
        <div className="kpi">
          <div className="label">Actores en el mapa</div>
          <div className="value">{graphData.nodes.length}</div>
          <div className="hint">
            {soloMayor
              ? `filtro: solo componente principal · datos ${red.meta?.n_entidades ?? "—"}E / ${red.meta?.n_proveedores ?? "—"}P`
              : `${red.meta?.n_entidades ?? "—"} entidades · ${red.meta?.n_proveedores ?? "—"} proveedores (subgrafo Cap.2)`}
          </div>
        </div>
        <div className="kpi">
          <div className="label">Vínculos</div>
          <div className="value">{graphData.links.length}</div>
          <div className="hint">adjudicaciones agregadas entidad↔proveedor</div>
        </div>
        <div className="kpi">
          <div className="label">Hubs</div>
          <div className="value">{red.palacios?.length ?? 0}</div>
          <div className="hint">compradores con más conexiones</div>
        </div>
      </div>

      <div className="network-toolbar">
        <input
          type="search"
          placeholder="Buscar entidad o proveedor…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="tabs">
          {(["todos", "entidad", "proveedor"] as const).map((k) => (
            <button
              key={k}
              type="button"
              className={`tab ${kindFilter === k ? "active" : ""}`}
              onClick={() => setKindFilter(k)}
            >
              {k === "todos" ? "Todos" : k === "entidad" ? "Entidades" : "Proveedores"}
            </button>
          ))}
        </div>
        <button
          type="button"
          className={`tab ${soloMayor ? "active" : ""}`}
          onClick={() => setSoloMayor((v) => !v)}
          title="Si está activo, oculta nodos que no estánen al componente más grande"
        >
          {soloMayor ? "Solo red conectada" : "Mostrar todas las islas"}
        </button>
        {baseGraph.nodes.some((n) => n.ancla_id === "urosario") ? (
          <button
            type="button"
            className="tab"
            onClick={() => {
              const n = baseGraph.nodes.find((x) => x.ancla_id === "urosario");
              if (n) centerOn(n.id);
            }}
          >
            Ir a Rosario
          </button>
        ) : null}
      </div>

      <div className="network-layout">
        <div className="network-canvas" ref={wrapRef}>
          <ForceGraph2D
            ref={fgRef}
            width={size.w}
            height={size.h}
            graphData={graphData}
            backgroundColor="#fff4eb"
            nodeCanvasObject={paintNode}
            linkCanvasObject={paintLink}
            linkDirectionalParticles={0}
            cooldownTicks={L.cooldownTicks}
            d3AlphaDecay={L.alphaDecay}
            d3VelocityDecay={L.velocityDecay}
            onEngineStop={() => {
              try {
                const nodes = graphData.nodes as any[];
                const ok = nodes.some((n) => Number.isFinite(n.x) && Number.isFinite(n.y));
                if (ok) fgRef.current?.zoomToFit(400, L.zoomPadding);
              } catch {
                /* ignore */
              }
            }}
            onNodeHover={(n: any) => setHover(n ? n.id : null)}
            onNodeClick={(n: any) => {
              setSelected(n.id);
              fgRef.current?.centerAt(n.x, n.y, 500);
              fgRef.current?.zoom(2.0, 500);
            }}
            onBackgroundClick={() => setSelected(null)}
            nodePointerAreaPaint={(node: any, color, ctx) => {
              const r = nodeRadius(node) + 4;
              ctx.beginPath();
              ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
              ctx.fillStyle = color;
              ctx.fill();
            }}
          />
          <div className="network-legend">
            {(red.leyenda || []).map((l) => (
              <span key={l.kind}>
                <i
                  style={{
                    background:
                      COLOR[l.kind as keyof typeof COLOR] || l.color || COLOR.proveedor,
                  }}
                />{" "}
                {l.nombre}
              </span>
            ))}
          </div>
        </div>

        <aside className="network-side">
          <h4>Compradores clave</h4>
          <p className="note" style={{ marginTop: 0 }}>
            Hubs del grafo: más vínculos CTeI. Clic para centrar.
          </p>
          <ul className="network-palacios">
            {(red.palacios || []).slice(0, 8).map((p, i) => {
              const maxDeg = Math.max(...(red.palacios || []).map((x) => x.degree), 1);
              const pct = Math.round((100 * p.degree) / maxDeg);
              return (
                <li key={p.id}>
                  <button type="button" onClick={() => centerOn(p.id)}>
                    <span className="hub-rank">#{i + 1}</span>
                    <strong>
                      {p.nombre.length > 42 ? p.nombre.slice(0, 40) + "…" : p.nombre}
                    </strong>
                    <span className="hub-meta">
                      {p.degree} vínculos · {formatCopShort(p.valor)}
                    </span>
                    <span className="hub-bar" aria-hidden="true">
                      <i style={{ width: `${pct}%` }} />
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>

          {selectedNode ? (
            <div className="network-detail">
              <h4>{selectedNode.kind === "entidad" ? "Entidad" : "Proveedor"}</h4>
              <p className="network-detail-name">{selectedNode.nombre}</p>
              <ul className="rosario-list">
                <li>Valor en universo: {formatCop(selectedNode.valor)}</li>
                <li>Conexiones en el mapa: {selectedNode.degree}</li>
                {selectedNode.nit && <li>ID / NIT: {selectedNode.nit}</li>}
              </ul>
              {selectedLinks.length > 0 && (
                <>
                  <p className="note">Principales vínculos</p>
                  <ul className="network-edges">
                    {selectedLinks.map((l, i) => {
                      const [s, t] = linkId(l);
                      const other = s === selected ? t : s;
                      const otherNode = baseGraph.nodes.find((n) => n.id === other);
                      return (
                        <li key={i}>
                          <button type="button" onClick={() => centerOn(other)}>
                            {otherNode?.label || other}
                          </button>
                          <span>
                            {formatCopShort(l.valor)} · {l.n_procesos} proc.
                            {l.dependencia_proveedor_pct != null
                              ? ` · dep. ${l.dependencia_proveedor_pct}%`
                              : ""}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </>
              )}
            </div>
          ) : (
            <div className="network-detail muted">
              <p className="note">
                Clic en un nodo para fijarlo. {(red.como_leer || []).join(" ")}
              </p>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

function qMatch(q: string, node: { label: string; nombre: string; nit?: string }) {
  if (!q.trim()) return false;
  const s = q.toLowerCase();
  return (
    node.label.toLowerCase().includes(s) ||
    node.nombre.toLowerCase().includes(s) ||
    (node.nit || "").toLowerCase().includes(s)
  );
}
