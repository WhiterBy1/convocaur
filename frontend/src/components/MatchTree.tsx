import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

export type TerminoClave = {
  term: string;
  peso: number;
  evidencia_docente?: string | null;
  evidencia_convocatoria?: string | null;
};

export type MatchTreeRow = {
  id: string;
  nombre: string;
  facultad?: string;
  score_final: number;
  score_emb?: number;
  score_tfidf?: number;
  boost?: number;
  rank: number;
  terminos_clave?: TerminoClave[];
  caracteristicas?: { id: string; label: string; aporte: number; tipo: string }[];
};

type Props = {
  convocatoriaLabel: string;
  objetivo?: string;
  rows: MatchTreeRow[];
  activeId: string | null;
  onSelect: (id: string | null) => void;
};

type LaidNode = {
  id: string;
  kind: "conv" | "docente" | "termino";
  label: string;
  shortLabel: string;
  term?: string;
  x: number;
  y: number;
  r: number;
  score?: number;
  rank?: number;
  labelSide?: "up" | "down";
};

export function MatchTree({
  convocatoriaLabel,
  objetivo: _objetivo,
  rows,
  activeId,
  onSelect,
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(960);
  const [openedId, setOpenedId] = useState<string | null>(null);
  const [modalTerm, setModalTerm] = useState<TerminoClave | null>(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setWidth(Math.max(640, el.clientWidth));
    });
    ro.observe(el);
    setWidth(Math.max(640, el.clientWidth));
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (activeId && openedId && activeId !== openedId) {
      setOpenedId(activeId);
      setModalTerm(null);
    }
  }, [activeId, openedId]);

  useEffect(() => {
    if (!modalTerm) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setModalTerm(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [modalTerm]);

  const sorted = useMemo(
    () => [...rows].sort((a, b) => a.rank - b.rank).slice(0, 12),
    [rows]
  );

  const openedRow = sorted.find((r) => r.id === openedId) || null;
  const terms = (openedRow?.terminos_clave || []).slice(0, 6);

  const layout = useMemo(() => {
    const W = width;
    const showTerms = !!openedRow && terms.length > 0;
    const H = showTerms ? 720 : 560;
    const cx = W / 2;
    const yConv = 56;
    const padX = 72;

    const shortName = (full: string) => {
      const parts = full.trim().split(/\s+/).filter(Boolean);
      if (parts.length <= 2) return full.length > 18 ? full.slice(0, 16) + "…" : full;
      // Apellido(s) + inicial
      const last = parts[parts.length - 1];
      const first = parts[0]?.[0] ? `${parts[0][0]}.` : "";
      const mid = parts.length > 2 ? parts[parts.length - 2] : "";
      const label = mid ? `${first} ${mid} ${last}` : `${first} ${last}`;
      return label.length > 20 ? label.slice(0, 18) + "…" : label;
    };

    const nodes: LaidNode[] = [
      {
        id: "conv-root",
        kind: "conv",
        label: convocatoriaLabel,
        shortLabel: "Conv.",
        x: cx,
        y: yConv,
        r: 36,
      },
    ];
    const links: { x1: number; y1: number; x2: number; y2: number; hot?: boolean }[] = [];

    const n = Math.max(sorted.length, 1);
    // Arco bajo la convocatoria: más aire entre etiquetas
    const arcY = 250;
    const arcSpread = Math.min(W - padX * 2, Math.max(n * 78, 280));
    const arcStart = cx - arcSpread / 2;

    sorted.forEach((row, i) => {
      const t = n === 1 ? 0.5 : i / Math.max(n - 1, 1);
      const x = arcStart + arcSpread * t;
      // Ligera curva: centro más bajo, extremos un poco más altos
      const bow = Math.sin(t * Math.PI) * 28;
      const y = arcY + bow;
      const hot = row.id === openedId;
      const r = hot ? 24 : 14 + Math.min(row.score_final, 1) * 7;
      nodes.push({
        id: row.id,
        kind: "docente",
        label: row.nombre || row.id,
        shortLabel: shortName(row.nombre || `#${row.rank}`),
        x,
        y,
        r,
        score: row.score_final,
        rank: row.rank,
        labelSide: "down",
      });
      links.push({
        x1: cx,
        y1: yConv + 36,
        x2: x,
        y2: y - r,
        hot,
      });
    });

    if (openedRow && terms.length) {
      const parent = nodes.find((nd) => nd.id === openedRow.id)!;
      const yTerm = 520;
      const tSpan = Math.min(W - 100, Math.max(terms.length * 110, 260));
      const tStart = Math.min(
        Math.max(parent.x - tSpan / 2, padX),
        W - padX - tSpan,
      );
      terms.forEach((term, i) => {
        const x =
          terms.length === 1
            ? parent.x
            : tStart + (tSpan * i) / Math.max(terms.length - 1, 1);
        const termHot = modalTerm?.term === term.term;
        nodes.push({
          id: `${openedRow.id}::${term.term}`,
          kind: "termino",
          label: term.term,
          shortLabel:
            term.term.length > 12 ? term.term.slice(0, 11) + "…" : term.term,
          term: term.term,
          x,
          y: yTerm,
          r: (termHot ? 15 : 11) + Math.min(term.peso * 30, 8),
          score: term.peso,
        });
        links.push({
          x1: parent.x,
          y1: parent.y + parent.r,
          x2: x,
          y2: yTerm - 14,
          hot: true,
        });
      });
    }

    return { W, H, nodes, links };
  }, [width, convocatoriaLabel, sorted, openedId, openedRow, terms, modalTerm]);

  const openDoc = (id: string) => {
    setOpenedId(id);
    setModalTerm(null);
    onSelect(id);
  };

  const openTerm = (term: string) => {
    const t = terms.find((x) => x.term === term) || null;
    setModalTerm(t);
  };

  return (
    <div className="panel panel-rosario match-tree match-tree-wide">
      <div className="match-tree-head">
        <div>
          <h3>Árbol de match</h3>
          <p className="note" style={{ margin: 0 }}>
            Clic en un docente (beige) → términos (coral) → evidencia.
          </p>
        </div>
        <p className="note match-tree-hint">
          {openedRow
            ? `Abierto: ${openedRow.nombre || openedRow.id}`
            : "Los nombres van debajo de cada nodo"}
        </p>
      </div>

      <div className="tree-svg-wrap tree-svg-tall" ref={wrapRef}>
        <svg
          viewBox={`0 0 ${layout.W} ${layout.H}`}
          className="tree-svg"
          role="img"
          aria-label="Árbol convocatoria docentes términos"
        >
          {layout.links.map((l, i) => (
            <motion.line
              key={i}
              x1={l.x1}
              y1={l.y1}
              x2={l.x2}
              y2={l.y2}
              stroke={l.hot ? "rgba(62,75,142,0.85)" : "rgba(166,188,201,0.55)"}
              strokeWidth={l.hot ? 2.4 : 1.5}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            />
          ))}

          {layout.nodes.map((n) => {
            const hotDoc = n.id === openedId;
            const hotTerm = n.kind === "termino" && modalTerm?.term === n.term;
            const fill =
              n.kind === "conv"
                ? "#3e4b8e"
                : n.kind === "docente"
                  ? "#f6e0b6"
                  : hotTerm
                    ? "#a85a68"
                    : "#8b3a4a";
            const stroke =
              n.kind === "conv"
                ? "#3e4b8e"
                : hotDoc || hotTerm
                  ? "#3d1534"
                  : n.kind === "docente"
                    ? "rgba(62,75,142,0.55)"
                    : "rgba(61,21,52,0.25)";
            const clickable = n.kind === "docente" || n.kind === "termino";

            return (
              <g
                key={n.id}
                style={{ cursor: clickable ? "pointer" : "default" }}
                onClick={() => {
                  if (n.kind === "docente") openDoc(n.id);
                  if (n.kind === "termino" && n.term) openTerm(n.term);
                }}
              >
                <circle
                  cx={n.x}
                  cy={n.y}
                  r={n.r}
                  fill={fill}
                  stroke={stroke}
                  strokeWidth={hotDoc || hotTerm || n.kind === "conv" ? 2.4 : 1.4}
                />
                {n.kind === "conv" && (
                  <text
                    x={n.x}
                    y={n.y + 5}
                    textAnchor="middle"
                    fill="#fffaf5"
                    fontSize="12"
                    fontWeight="700"
                    fontFamily="Source Sans 3, sans-serif"
                  >
                    Conv.
                  </text>
                )}
                {n.kind === "docente" && (
                  <>
                    <text
                      x={n.x}
                      y={n.y + 4}
                      textAnchor="middle"
                      fill="#3d1534"
                      fontSize="10"
                      fontWeight="700"
                      fontFamily="Source Sans 3, sans-serif"
                    >
                      {(n.score ?? 0).toFixed(2)}
                    </text>
                    <text
                      x={n.x}
                      y={n.y + n.r + 18}
                      textAnchor="middle"
                      fill="#3d1534"
                      fontSize="10"
                      fontWeight="600"
                      fontFamily="Source Sans 3, sans-serif"
                    >
                      {n.shortLabel}
                    </text>
                    <title>
                      #{n.rank} {n.label} · score {(n.score ?? 0).toFixed(3)}
                    </title>
                  </>
                )}
                {n.kind === "termino" && (
                  <>
                    <text
                      x={n.x}
                      y={n.y + n.r + 14}
                      textAnchor="middle"
                      fill="#3d1534"
                      fontSize="10"
                      fontWeight="600"
                      fontFamily="Source Sans 3, sans-serif"
                    >
                      {n.shortLabel}
                    </text>
                    <title>Clic para ver evidencia: {n.label}</title>
                  </>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      <div className="network-legend" style={{ position: "relative", marginTop: "0.5rem" }}>
        <span>
          <i style={{ background: "#3e4b8e" }} /> Convocatoria
        </span>
        <span>
          <i style={{ background: "#f6e0b6" }} /> Docente
        </span>
        <span>
          <i style={{ background: "#8b3a4a" }} /> Término
        </span>
        {openedRow && (
          <span className="note" style={{ margin: 0 }}>
            #{openedRow.rank} · score {openedRow.score_final.toFixed(3)}
          </span>
        )}
      </div>

      <AnimatePresence>
        {modalTerm && openedRow && (
          <motion.div
            className="term-modal-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={() => setModalTerm(null)}
            role="presentation"
          >
            <motion.div
              className="term-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="term-modal-title"
              initial={{ opacity: 0, y: 16, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.98 }}
              transition={{ duration: 0.2 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="term-modal-head">
                <div>
                  <p className="note" style={{ margin: "0 0 0.2rem" }}>
                    #{openedRow.rank} {openedRow.nombre || openedRow.id}
                  </p>
                  <h4 id="term-modal-title">
                    <span className="tree-term">{modalTerm.term}</span>
                    <span className="tree-peso">peso {modalTerm.peso.toFixed(4)}</span>
                  </h4>
                </div>
                <button type="button" className="tab" onClick={() => setModalTerm(null)}>
                  Cerrar
                </button>
              </div>

              <div className="term-modal-body">
                {modalTerm.evidencia_docente ? (
                  <blockquote>
                    <span className="tree-ev-label">Perfil docente</span>
                    {modalTerm.evidencia_docente}
                  </blockquote>
                ) : (
                  <p className="note">Sin fragmento literal en el perfil para este término.</p>
                )}
                {modalTerm.evidencia_convocatoria ? (
                  <blockquote className="conv-quote">
                    <span className="tree-ev-label">Convocatoria</span>
                    {modalTerm.evidencia_convocatoria}
                  </blockquote>
                ) : (
                  <p className="note">Sin fragmento literal en la convocatoria para este término.</p>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

