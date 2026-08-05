import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { forceCollide, forceX, forceY } from "d3-force-3d";

export type MatchNode = {
  id: string;
  kind: string;
  label: string;
  score?: number | null;
  rank?: number;
  aporte?: number;
  peso?: number;
  distancia?: number;
  val?: number;
  facultad?: string;
  terminos_clave?: { term: string; peso: number }[];
};

export type MatchLink = {
  source: string | { id: string };
  target: string | { id: string };
  score?: number;
  kind?: string;
  length?: number;
  distancia?: number;
};

type Props = {
  grafo: { nodes: MatchNode[]; links: MatchLink[]; lectura?: string };
  activeId: string | null;
  onSelect: (id: string) => void;
};

/** Tunables del layout matching (como Cap.2). */
export const MATCH_LAYOUT = {
  chargeStrength: -280,
  chargeDistanceMax: 260,
  centerStrength: 0.18,
  collidePadding: 8,
  cooldownTicks: 120,
  zoomPadding: 40,
};

const COLOR: Record<string, string> = {
  convocatoria: "#3e4b8e",
  profesor: "#a6bcc9",
  termino: "#c4a06a",
  aporte: "#6a5a68",
  dim: "rgba(61,21,52,0.22)",
};

function linkEnds(l: MatchLink): [string, string] {
  const s = typeof l.source === "object" ? l.source.id : l.source;
  const t = typeof l.target === "object" ? l.target.id : l.target;
  return [s, t];
}

export function MatchGraph({ grafo, activeId, onSelect }: Props) {
  const fgRef = useRef<any>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 720, h: 520 });
  const [hover, setHover] = useState<string | null>(null);
  const L = MATCH_LAYOUT;

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setSize({
        w: Math.max(320, el.clientWidth),
        h: Math.max(420, Math.min(560, el.clientWidth * 0.72)),
      });
    });
    ro.observe(el);
    setSize({
      w: Math.max(320, el.clientWidth),
      h: Math.max(420, Math.min(560, el.clientWidth * 0.72)),
    });
    return () => ro.disconnect();
  }, []);

  const graphData = useMemo(() => {
    const nodes = grafo.nodes.map((n) => {
      const copy: any = { ...n };
      // Fijar convocatoria cerca del origen (palacio central)
      if (n.kind === "convocatoria") {
        copy.fx = 0;
        copy.fy = 0;
      }
      return copy;
    });
    const links = grafo.links.map((l) => ({ ...l }));
    return { nodes, links };
  }, [grafo]);

  const neighbors = useMemo(() => {
    const m = new Map<string, Set<string>>();
    for (const n of grafo.nodes) m.set(n.id, new Set());
    for (const l of grafo.links) {
      const [s, t] = linkEnds(l);
      m.get(s)?.add(t);
      m.get(t)?.add(s);
    }
    return m;
  }, [grafo]);

  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    try {
      const charge = fg.d3Force("charge");
      if (charge?.strength) {
        charge.strength(L.chargeStrength);
        if (typeof charge.distanceMax === "function") {
          charge.distanceMax(L.chargeDistanceMax);
        }
      }
      const link = fg.d3Force("link");
      if (link?.distance) {
        link.distance((l: any) => Number(l.length) || 90);
        if (typeof link.strength === "function") {
          link.strength((l: any) => {
            if (l.kind === "match") return 0.85;
            if (l.kind === "termino_doc" || l.kind === "termino_conv") return 0.45;
            return 0.35;
          });
        }
      }
      fg.d3Force("x", forceX(0).strength(L.centerStrength));
      fg.d3Force("y", forceY(0).strength(L.centerStrength));
      fg.d3Force(
        "collide",
        forceCollide()
          .radius((n: any) => radiusOf(n) + L.collidePadding)
          .strength(0.9)
          .iterations(2)
      );
      fg.d3ReheatSimulation();
    } catch (e) {
      console.warn("[MatchGraph] fuerzas:", e);
    }
  }, [graphData.nodes.length, graphData.links.length, L]);

  const focus = activeId || hover;

  const paintNode = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const r = radiusOf(node);
      const isFocus = focus === node.id;
      const neigh = focus ? neighbors.get(focus) : null;
      const dim = focus && !isFocus && !neigh?.has(node.id) && node.kind !== "convocatoria";
      const color = COLOR[node.kind] || COLOR.profesor;

      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.fillStyle = dim ? COLOR.dim : color;
      ctx.globalAlpha = dim ? 0.28 : 0.95;
      ctx.fill();

      if (node.kind === "convocatoria" || isFocus) {
        ctx.strokeStyle = "#eef5f0";
        ctx.lineWidth = (node.kind === "convocatoria" ? 2.4 : 1.8) / globalScale;
        ctx.stroke();
      }

      if (!dim && (node.kind === "convocatoria" || node.kind === "termino")) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r * 1.4, 0, 2 * Math.PI);
        ctx.fillStyle = color;
        ctx.globalAlpha = 0.12;
        ctx.fill();
      }

      const showLabel =
        node.kind === "convocatoria" ||
        node.kind === "termino" ||
        isFocus ||
        globalScale > 1.25 ||
        (node.kind === "profesor" && (node.rank == null || node.rank <= 8));

      if (showLabel && !dim) {
        ctx.globalAlpha = 1;
        const fs = node.kind === "termino" ? 10 : 11;
        ctx.font = `${fs / globalScale}px "Source Sans 3", sans-serif`;
        ctx.fillStyle = node.kind === "termino" ? "#a6bcc9" : "#3d1534";
        ctx.textAlign = "center";
        const label =
          node.kind === "convocatoria"
            ? "Convocatoria"
            : (node.label || "").slice(0, node.kind === "termino" ? 20 : 18);
        ctx.fillText(label, node.x, node.y + r + 10 / globalScale);
        if (node.kind === "profesor" && node.score != null && (isFocus || globalScale > 1.1)) {
          ctx.fillStyle = "#a6bcc9";
          ctx.font = `${9 / globalScale}px "Source Sans 3", sans-serif`;
          ctx.fillText(Number(node.score).toFixed(2), node.x, node.y + 3 / globalScale);
        }
      }
      ctx.globalAlpha = 1;
    },
    [focus, neighbors]
  );

  const paintLink = useCallback(
    (link: any, ctx: CanvasRenderingContext2D) => {
      const s = link.source;
      const t = link.target;
      if (s?.x == null || t?.x == null) return;
      const sid = s.id || s;
      const tid = t.id || t;
      const hot = focus && (sid === focus || tid === focus);
      const dim = focus && !hot;
      const isMatch = link.kind === "match";
      const isTerm =
        link.kind === "termino_doc" || link.kind === "termino_conv";

      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);
      if (hot) ctx.strokeStyle = "rgba(94,196,168,0.95)";
      else if (isMatch) ctx.strokeStyle = "rgba(94,196,168,0.45)";
      else if (isTerm) ctx.strokeStyle = "rgba(196,163,90,0.4)";
      else ctx.strokeStyle = "rgba(122,143,134,0.35)";
      if (dim) ctx.strokeStyle = "rgba(238,245,240,0.06)";

      const score = Number(link.score) || 0;
      ctx.lineWidth = isMatch
        ? Math.max(1.2, 1 + score * 3)
        : isTerm
          ? Math.max(0.7, 0.5 + score * 8)
          : 0.9;
      ctx.globalAlpha = dim ? 0.2 : 0.9;
      ctx.stroke();
      ctx.globalAlpha = 1;
    },
    [focus]
  );

  return (
    <div className="panel panel-rosario" style={{ marginBottom: 0, padding: "0.75rem" }}>
      <p className="note" style={{ marginTop: 0, marginBottom: "0.5rem" }}>
        {grafo.lectura ||
          "Mayor score = más cerca de la convocatoria. Nodos dorados = términos con más peso compartido."}
      </p>
      <div className="network-legend" style={{ position: "relative", marginBottom: "0.4rem" }}>
        <span>
          <i style={{ background: COLOR.convocatoria }} /> Convocatoria
        </span>
        <span>
          <i style={{ background: COLOR.profesor }} /> Docente
        </span>
        <span>
          <i style={{ background: COLOR.termino }} /> Término (peso)
        </span>
        <span>
          <i style={{ background: COLOR.aporte }} /> Boost
        </span>
      </div>
      <div
        className="network-canvas"
        ref={wrapRef}
        style={{ minHeight: 420, borderRadius: 12 }}
      >
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
          d3AlphaDecay={0.024}
          d3VelocityDecay={0.38}
          onEngineStop={() => {
            try {
              const ok = (graphData.nodes as any[]).some(
                (n) => Number.isFinite(n.x) && Number.isFinite(n.y)
              );
              if (ok) fgRef.current?.zoomToFit(400, L.zoomPadding);
            } catch {
              /* ignore */
            }
          }}
          onNodeHover={(n: any) => setHover(n ? n.id : null)}
          onNodeClick={(n: any) => {
            if (n.kind === "profesor") onSelect(n.id);
            if (n.kind === "aporte" && n.parent) onSelect(n.parent);
            if (n.x != null) {
              fgRef.current?.centerAt(n.x, n.y, 450);
              fgRef.current?.zoom(n.kind === "termino" ? 2.4 : 1.9, 450);
            }
          }}
          nodePointerAreaPaint={(node: any, color, ctx) => {
            const r = radiusOf(node) + 3;
            ctx.beginPath();
            ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
            ctx.fillStyle = color;
            ctx.fill();
          }}
        />
      </div>
    </div>
  );
}

function radiusOf(node: { kind?: string; score?: number | null; peso?: number; val?: number }) {
  if (node.kind === "convocatoria") return 22;
  if (node.kind === "profesor") return 10 + Math.min(Number(node.score) || 0, 1) * 10;
  if (node.kind === "termino") return 5 + Math.min((Number(node.peso) || Number(node.val) || 0) * 40, 10);
  return 6;
}

