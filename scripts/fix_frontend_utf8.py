"""Repair UTF-8 mojibake caused by PowerShell Set-Content re-encoding."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"

REPL = {
    "Ã¡": "á",
    "Ã©": "é",
    "Ã­": "í",
    "Ã³": "ó",
    "Ãº": "ú",
    "Ã±": "ñ",
    "Ã": "Á",
    "Ã‰": "É",
    "Ã": "Í",
    "Ã“": "Ó",
    "Ãš": "Ú",
    "Ã‘": "Ñ",
    "Â¿": "¿",
    "Â¡": "¡",
    "Â·": "·",
    "Â°": "°",
    "â€”": "—",
    "â€“": "–",
    "â€˜": "‘",
    "â€™": "’",
    "â€œ": "“",
    "â€": "”",
    "â€¦": "…",
    "â†’": "→",
    "â‰ˆ": "≈",
    "â€¢": "•",
}


def looks_mojibake(text: str) -> bool:
    return any(m in text for m in ("Ã", "Â¿", "Â¡", "Â·", "â€", "â†", "â‰", "Ã±", "Ã³"))


def fix_text(text: str) -> str:
    if not looks_mojibake(text):
        return text
    try:
        candidate = text.encode("latin-1").decode("utf-8")
        if looks_mojibake(candidate):
            for a, b in REPL.items():
                candidate = candidate.replace(a, b)
        return candidate
    except UnicodeError:
        out = text
        for a, b in REPL.items():
            out = out.replace(a, b)
        return out


def main() -> None:
    files: list[Path] = []
    files.append(FRONTEND / "index.html")
    files.extend((FRONTEND / "src").rglob("*.tsx"))
    files.extend((FRONTEND / "src").rglob("*.ts"))
    files.extend((FRONTEND / "src").rglob("*.css"))
    n = 0
    for f in files:
        if not f.exists():
            continue
        raw = f.read_bytes()
        bom = raw.startswith(b"\xef\xbb\xbf")
        if bom:
            raw = raw[3:]
        text = raw.decode("utf-8")
        fixed = fix_text(text)
        # broken em-dash comment artifacts in css
        fixed = fixed.replace("/*  Cap.3 predict demo  */", "/* Cap.3 predict demo */")
        if fixed != text or bom:
            f.write_text(fixed, encoding="utf-8", newline="\n")
            n += 1
            print("fixed", f.relative_to(ROOT))
    print("total", n)


if __name__ == "__main__":
    main()
