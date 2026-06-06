"""Run the Controllers & Analysers GUI from a source checkout."""

from __future__ import annotations

import os
import sys


ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from ca_app.app import main


if __name__ == "__main__":
    main()
