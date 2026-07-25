#!/usr/bin/env python
"""Orquesta NLP + elegibilidad sobre TdR ya seccionados."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from convocaur.nlp.piloto_tdr import main

if __name__ == "__main__":
    main()
