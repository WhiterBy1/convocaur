#!/usr/bin/env python
"""Re-evalúa elegibilidad Rosario sobre JSON NLP existentes."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from convocaur.nlp.verificar_elegibilidad import main

if __name__ == "__main__":
    main()
