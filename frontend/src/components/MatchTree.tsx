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
  objetivo,
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
    const H = showTerms ? 640 : 480;
    const cx = W / 2;
    const yConv = 64;
    const yDoc = 250;
    const yTerm = 460;
    const padX = 56;

    const nodes: LaidNode[] = [
      {
        id: "conv-root",
        kind: "conv",
        label: convocatoriaLabel,
        shortLabel: "Conv.",
        x: cx,
        y: yConv,
        r: 40,
      },
    ];
    const links: { x1: number; y1: number; x2: number; y2: number; hot?: boolean }[] = [];

    const n = Math.max(sorted.length, 1);
    const span = Math.max(W - padX * 2, 120);
    const startX = padX;

    sorted.forEach((row, i) => {
      const x = n === 1 ? cx : startX + (span * i) / Math.max(n - 1, 1);
      const hot = row.id === openedId;
      const r = hot ? 26 : 15 + Math.min(row.score_final, 1) * 8;
      nodes.push({
        id: row.id,
        kind: "docente",
        label: row.nombre || row.id,
        shortLabel: `#${row.rank}`,
        x,
        y: yDoc,
        r,
        score: row.score_final,
        rank: row.rank,
        labelSide: i % 2 === 0 ? "down" : "up",
      });
      links.push({
        x1: cx,
        y1: yConv + 40,
        x2: x,
        y2: yDoc - r,
        hot,
      });
    });

    if (openedRow && terms.length) {
      const parent = nodes.find((n) => n.id === openedRow.id)!;
      const tSpan = Math.min(W - 100, Math.max(terms.length * 100, 280));
      const tStart = Math.min(
        Math.max(parent.x - tSpan / 2, padX),
        W - padX - tSpan
      );
      terms.forEach((t, i) => {
        const x =
          terms.length === 1
            ? parent.x
            : tStart + (tSpan * i) / Math.max(terms.length - 1, 1);
        const termHot = modalTerm?.term === t.term;
        nodes.push({
          id: `${openedRow.id}::${t.term}`,
          kind: "termino",
          label: t.term,
          shortLabel: t.term.slice(0, 14),
          term: t.term,
          x,
          y: yTerm,
          r: (termHot ? 16 : 12) + Math.min(t.peso * 35, 10),
          score: t.peso,
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
            Convocatoria arriba · clic en docente → términos · clic en término → evidencia.
            {objetivo
              ? ` ${objetivo.slice(0, 140)}${objetivo.length > 140 ? "…" : ""}`
              : ""}
          </p>
        </div>
        <p className="note match-tree-hint">
          {openedRow
            ? "Ahora haz clic en un término (amarillo) para ver el texto"
            : "Haz clic en un docente para expandir sus términos"}
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
              stroke={l.hot ? "rgba(94,196,168,0.7)" : "rgba(196,163,90,0.32)"}
              strokeWidth={l.hot ? 2.4 : 1.4}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            />
          ))}

          {layout.nodes.map((n) => {
            const hotDoc = n.id === openedId;
            const hotTerm = n.kind === "termino" && modalTerm?.term === n.term;
            const fill =
              n.kind === "conv"
                ? "#c4a35a"
                : n.kind === "docente"
                  ? hotDoc
                    ? "#5ec4a8"
                    : "#143028"
                  : hotTerm
                    ? "#f0d78a"
                    : "#e8c97a";
            const stroke =
              n.kind === "conv" || hotDoc || hotTerm
                ? "#eef5f0"
                : n.kind === "docente"
                  ? "#5ec4a8"
                  : "rgba(238,245,240,0.45)";
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
                  strokeWidth={hotDoc || hotTerm || n.kind === "conv" ? 2.6 : 1.5}
                />
                {n.kind === "conv" && (
                  <text
                    x={n.x}
                    y={n.y + 5}
                    textAnchor="middle"
                    fill="#1a1408"
                    fontSize="13"
                    fontWeight="700"
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
                      fill={hotDoc ? "#08110e" : "#5ec4a8"}
                      fontSize="11"
                      fontWeight="700"
                    >
                      {(n.score ?? 0).toFixed(2)}
                    </text>
                    <text
                      x={n.x}
                      y={n.labelSide === "up" ? n.y - n.r - 10 : n.y + n.r + 16}
                      textAnchor="middle"
                      fill="#eef5f0"
                      fontSize="11"
                    >
                      {n.shortLabel}
                    </text>
                    <title>{n.label}</title>
                  </>
                )}
                {n.kind === "termino" && (
                  <>
                    <text
                      x={n.x}
                      y={n.y + n.r + 14}
                      textAnchor="middle"
                      fill="#e2c98a"
                      fontSize="11"
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
          <i style={{ background: "#c4a35a" }} /> Convocatoria
        </span>
        <span>
          <i style={{ background: "#5ec4a8" }} /> Docente (expandir)
        </span>
        <span>
          <i style={{ background: "#e8c97a" }} /> Término (modal)
        </span>
        {openedRow && (
          <span className="note" style={{ margin: 0 }}>
            #{openedRow.rank} {openedRow.nombre || openedRow.id} · score{" "}
            {openedRow.score_final.toFixed(3)}
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
