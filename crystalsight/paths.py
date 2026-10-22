from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TASKS = ROOT / "tasks"
RUNS = ROOT / "runs"
REPORTS = ROOT / "reports"
CACHE = ROOT / "_scratch" / "cache"


def venv_bin(name: str) -> str:
    """Resolve a console script that lives next to the running interpreter."""
    here = Path(sys.executable).parent
    for cand in (here / f"{name}.exe", here / name, here / "Scripts" / f"{name}.exe"):
        if cand.exists():
            return str(cand)
    found = shutil.which(name)
    if not found:
        raise FileNotFoundError(f"console script {name!r} not found next to {sys.executable}")
    return found


def rel(p: Path | str) -> str:
    p = Path(p)
    try:
        return str(p.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


SUBPROCESS_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
