"""Wrap full-width chart height divs with ChartInView."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "frontend" / "src"
TARGETS = [
    ROOT / "components" / "Cap2RosarioInsights.tsx",
    ROOT / "components" / "Cap3MarketForecast.tsx",
]


def wrap_file(path: Path) -> None:
    t = path.read_text(encoding="utf-8")
    if "ChartInView" not in t:
        lines = t.splitlines(True)
        last = 0
        for i, line in enumerate(lines):
            if line.startswith("import "):
                last = i
        lines.insert(last + 1, 'import { ChartInView } from "./ChartInView";\n')
        t = "".join(lines)

    pat = re.compile(
        r'<div(\s+style=\{\{\s*width:\s*"100%",\s*height:[^}]+\}\}\s*)>'
    )

    out = []
    i = 0
    while True:
        m = pat.search(t, i)
        if not m:
            out.append(t[i:])
            break
        out.append(t[i : m.start()])
        attrs = m.group(1)
        end_open = m.end()
        depth = 1
        j = end_open
        while j < len(t) and depth:
            if t.startswith("<div", j):
                depth += 1
                j = t.find(">", j) + 1
                continue
            if t.startswith("</div>", j):
                depth -= 1
                if depth == 0:
                    inner = t[end_open:j]
                    # only wrap if contains ResponsiveContainer
                    if "ResponsiveContainer" in inner:
                        out.append(f"<ChartInView{attrs}>")
                        out.append(inner)
                        out.append("</ChartInView>")
                    else:
                        out.append(m.group(0))
                        out.append(inner)
                        out.append("</div>")
                    j += len("</div>")
                    break
                j += len("</div>")
                continue
            j += 1
        i = j
    path.write_text("".join(out), encoding="utf-8")
    print("updated", path.name)


def main() -> None:
    for p in TARGETS:
        wrap_file(p)


if __name__ == "__main__":
    main()
