#!/usr/bin/env python
"""Colecciona TdR normalizados y extrae secciones."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from convocaur.minciencias.coleccionar_tdr import main as main_tdr
from convocaur.minciencias.secciones_tdr import main as main_sec


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "secciones":
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        main_sec()
    else:
        main_tdr()
