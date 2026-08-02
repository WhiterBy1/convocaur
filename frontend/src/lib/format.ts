/** Formato de dinero en billones/millones COP para docentes. */
export function formatCop(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  const abs = Math.abs(n);
  if (abs >= 1e12) return `$ ${(n / 1e12).toFixed(2)} billones`;
  if (abs >= 1e9) return `$ ${(n / 1e9).toFixed(1)} mil millones`;
  if (abs >= 1e6) return `$ ${(n / 1e6).toFixed(0)} millones`;
  return `$ ${Math.round(n).toLocaleString("es-CO")}`;
}

export function formatCopShort(n: number): string {
  if (Math.abs(n) >= 1e12) return `${(n / 1e12).toFixed(1)} B`;
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(0)} MM`;
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(0)} M`;
  return String(Math.round(n));
}
