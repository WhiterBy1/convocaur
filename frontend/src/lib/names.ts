/** Limpia ORCID/URLs y humaniza slugs de docentes. */
export function cleanDocenteName(
  nombre?: string | null,
  fallback?: string | null
): string {
  let raw = String(nombre || "").trim();
  if (!raw || raw.toLowerCase() === "nan" || raw.toLowerCase() === "none") {
    raw = String(fallback || "").trim();
  }

  raw = raw
    .replace(/https?:\/\/(?:www\.)?orcid\.org\/\S+/gi, "")
    .replace(/\s*[|/]\s*orcid\.org\/\S+/gi, "")
    .replace(/\borcid\.org\/\S+/gi, "")
    .replace(/\bORCID\s*[:=]?\s*\d{4}-\d{4}-\d{4}-\d{3}[\dXx]\b/gi, "")
    .replace(/\b\d{4}-\d{4}-\d{4}-\d{3}[\dXx]\b/g, "")
    .replace(/\s*[|/]\s*$/g, "")
    .replace(/\s{2,}/g, " ")
    .replace(/^[\s\-|/]+|[\s\-|/]+$/g, "")
    .trim();

  // slug completo: luis-antonio-orozco
  if (/^[a-z0-9]+(?:-[a-z0-9]+)+$/.test(raw)) {
    raw = titleWords(raw.replace(/-/g, " "));
  } else if (/^[a-z]/.test(raw) && raw.includes("-") && !raw.includes(" ")) {
    raw = titleWords(raw.replace(/-/g, " "));
  } else if (raw === raw.toLowerCase() && /\s/.test(raw)) {
    raw = titleWords(raw);
  } else {
    // "Javier-Leonardo Gonzalez" → "Javier Leonardo Gonzalez"
    raw = raw.replace(/([A-Za-zÁÉÍÓÚáéíóúÑñ])-([A-Za-zÁÉÍÓÚáéíóúÑñ])/g, "$1 $2");
  }

  if (!raw) {
    const fb = String(fallback || "").trim();
    if (/^[a-z0-9]+(?:-[a-z0-9]+)+$/.test(fb)) {
      raw = titleWords(fb.replace(/-/g, " "));
    } else {
      raw = fb || "Docente";
    }
  }
  return raw;
}

function titleWords(s: string): string {
  return s
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}
