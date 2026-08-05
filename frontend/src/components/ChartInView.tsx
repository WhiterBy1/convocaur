import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

type Props = {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  /** Fracción visible para disparar (0–1). */
  threshold?: number;
};

/**
 * Remonta el contenido cada vez que entra al viewport,
 * para que Recharts vuelva a animar barras/líneas.
 */
export function ChartInView({ children, className, style, threshold = 0.28 }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [ticket, setTicket] = useState(0);
  const [active, setActive] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setTicket((t) => t + 1);
          setActive(true);
        } else {
          setActive(false);
        }
      },
      { threshold, rootMargin: "0px 0px -8% 0px" },
    );

    io.observe(el);
    return () => io.disconnect();
  }, [threshold]);

  return (
    <div ref={ref} className={className} style={style} data-chart-inview={active ? "1" : "0"}>
      {active ? <div key={ticket} style={{ width: "100%", height: "100%" }}>{children}</div> : null}
    </div>
  );
}
