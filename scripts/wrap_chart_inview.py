"""Wrap chart-wrap divs with ChartInView for viewport re-animation."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "frontend" / "src"


def close_matching(text: str, open_pat: str, open_tag: str, close_tag: str) -> str:
    """Replace <div className=\"chart-wrap...\">...</div> with ChartInView pairs."""
    out = []
    i = 0
    while True:
        m = re.search(open_pat, text[i:])
        if not m:
            out.append(text[i:])
            break
        start = i + m.start()
        end_open = i + m.end()
        out.append(text[i:start])
        attrs = m.group(1)
        # find matching close div by depth
        depth = 1
        j = end_open
        while j < len(text) and depth:
            if text.startswith("<div", j):
                # could be <div or <div>
                depth += 1
                j = text.find(">", j) + 1
                continue
            if text.startswith("</div>", j):
                depth -= 1
                if depth == 0:
                    inner = text[end_open:j]
                    out.append(f"<{open_tag}{attrs}>")
                    out.append(inner)
                    out.append(f"</{close_tag}>")
                    j += len("</div>")
                    break
                j += len("</div>")
                continue
            j += 1
        else:
            # failed; keep original open
            out.append(m.group(0))
            i = end_open
            continue
        i = j
    return "".join(out)


def process(path: Path) -> bool:
    if path.name in {"ChartInView.tsx", "Home.tsx"}:
        return False
    t = path.read_text(encoding="utf-8")
    if 'className="chart-wrap' not in t:
        return False
    orig = t
    if "ChartInView" not in t:
        imp = (
            'import { ChartInView } from "./ChartInView";\n'
            if path.parent.name == "components"
            else 'import { ChartInView } from "../components/ChartInView";\n'
        )
        lines = t.splitlines(True)
        last = 0
        for i, line in enumerate(lines):
            if line.startswith("import "):
                last = i
        lines.insert(last + 1, imp)
        t = "".join(lines)

    t = close_matching(
        t,
        r'<div(\s+className="chart-wrap[^"]*"[^>]*)>',
        "ChartInView",
        "ChartInView",
    )
    if t != orig:
        path.write_text(t, encoding="utf-8")
        return True
    return False


def main() -> None:
    n = 0
    for f in ROOT.rglob("*.tsx"):
        if process(f):
            print("updated", f.relative_to(ROOT))
            n += 1
    print("files", n)


if __name__ == "__main__":
    main()
