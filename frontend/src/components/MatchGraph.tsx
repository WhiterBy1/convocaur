import { motion } from "framer-motion";
import { useMemo } from "react";

type Node = {
  id: string;
  kind: string;
  label: string;
  score?: number | null;
  rank?: number;
  aporte?: number;
};

type Link = {
  source: string;
  target: string;
  score?: number;
  kind?: string;
};

type Props = {
  grafo: { nodes: Node[]; links: Link[] };
  activeId: string | null;
  onSelect: (id: string) => void;
};

export function MatchGraph({ grafo, activeId, onSelect }: Props) {
  const layout = useMemo(() => {
    const W = 800;
    const H = 560;
    const cx = W / 2;
    const cy = H / 2 - 20;

    const conv = grafo.nodes.find((n) => n.kind === "convocatoria");
    const profes = grafo.nodes.filter((n) => n.kind === "profesor");
    const aportes = grafo.nodes.filter((n) => n.kind === "aporte");

    const pos = new Map<string, { x: number; y: number }>();
    if (conv) pos.set(conv.id, { x: cx, y: cy });

    const R = 180;
    profes.forEach((p, i) => {
      const a = -Math.PI / 2 + (i / Math.max(profes.length, 1)) * Math.PI * 2;
      pos.set(p.id, { x: cx + Math.cos(a) * R, y: cy + Math.sin(a) * R });
    });

    aportes.forEach((a) => {
      const parent = grafo.nodes.find((n) => n.id === a.id.split("::")[0]);
      const pp = parent ? pos.get(parent.id) : null;
      if (!pp) return;
      const siblings = aportes.filter((x) => x.id.startsWith(parent!.id + "::"));
      const idx = siblings.findIndex((x) => x.id === a.id);
      const ang = Math.atan2(pp.y - cy, pp.x - cx);
      const spread = (idx - (siblings.length - 1) / 2) * 0.35;
      const rr = 78;
      pos.set(a.id, {
        x: pp.x + Math.cos(ang + spread) * rr,
        y: pp.y + Math.sin(ang + spread) * rr,
      });
    });

    return { W, H, pos, conv, profes, aportes };
  }, [grafo]);

  return (
    <div className="graph-stage">
      <svg viewBox={`0 0 ${layout.W} ${layout.H}`} role="img" aria-label="Grafo de matching">
        {grafo.links.map((l, i) => {
          const a = layout.pos.get(l.source);
          const b = layout.pos.get(l.target);
          if (!a || !b) return null;
          const isAporte = l.kind === "aporte";
          const active =
            l.source === activeId ||
            l.target === activeId ||
            l.target.startsWith((activeId || "") + "::");
          return (
            <motion.line
              key={`${l.source}-${l.target}-${i}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={isAporte ? "rgba(196,163,90,0.35)" : "rgba(61,207,176,0.35)"}
              strokeWidth={active ? 2.4 : isAporte ? 1 : 1.4}
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: active ? 1 : 0.55 }}
              transition={{ duration: 0.7, delay: i * 0.01 }}
            />
          );
        })}

        {layout.aportes.map((n, i) => {
          const p = layout.pos.get(n.id);
          if (!p) return null;
          const parentActive = activeId && n.id.startsWith(activeId + "::");
          return (
            <motion.g
              key={n.id}
              initial={{ opacity: 0, scale: 0.6 }}
              animate={{ opacity: parentActive ? 1 : 0.35, scale: 1 }}
              transition={{ delay: 0.2 + i * 0.02 }}
            >
              <circle cx={p.x} cy={p.y} r={parentActive ? 10 : 7} fill="#c4a35a" />
              {parentActive && (
                <text
                  x={p.x}
                  y={p.y - 14}
                  textAnchor="middle"
                  fill="#e2c98a"
                  fontSize="10"
                >
                  {n.label.slice(0, 18)}
                </text>
              )}
            </motion.g>
          );
        })}

        {layout.profes.map((n, i) => {
          const p = layout.pos.get(n.id);
          if (!p) return null;
          const active = n.id === activeId;
          const r = active ? 22 : 16;
          return (
            <motion.g
              key={n.id}
              style={{ cursor: "pointer" }}
              onClick={() => onSelect(n.id)}
              initial={{ opacity: 0, scale: 0.5 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.1 + i * 0.04, type: "spring", stiffness: 160 }}
            >
              <circle
                cx={p.x}
                cy={p.y}
                r={r}
                fill={active ? "#3dcfb0" : "#1a2e26"}
                stroke={active ? "#e2c98a" : "#3dcfb0"}
                strokeWidth={active ? 2.5 : 1.5}
              />
              <text
                x={p.x}
                y={p.y + r + 14}
                textAnchor="middle"
                fill="#eef5f0"
                fontSize="11"
              >
                {(n.label || n.id).slice(0, 22)}
              </text>
              {n.score != null && (
                <text
                  x={p.x}
                  y={p.y + 4}
                  textAnchor="middle"
                  fill={active ? "#08110e" : "#3dcfb0"}
                  fontSize="10"
                  fontWeight="700"
                >
                  {Number(n.score).toFixed(2)}
                </text>
              )}
            </motion.g>
          );
        })}

        {layout.conv && layout.pos.get(layout.conv.id) && (
          <motion.g
            initial={{ scale: 0.4, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 120 }}
          >
            <circle
              cx={layout.pos.get(layout.conv.id)!.x}
              cy={layout.pos.get(layout.conv.id)!.y}
              r={36}
              fill="#c4a35a"
            />
            <text
              x={layout.pos.get(layout.conv.id)!.x}
              y={layout.pos.get(layout.conv.id)!.y + 5}
              textAnchor="middle"
              fill="#1a1408"
              fontSize="12"
              fontWeight="700"
            >
              Conv.
            </text>
          </motion.g>
        )}
      </svg>
    </div>
  );
}
