"""Thin, cached wrapper around the installed ``mck`` CLI (JSON mode).

Ground truth and the tools channel both go through this module, so the tool
the model calls is literally the command that produced the gold answer.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from .paths import CACHE, SUBPROCESS_ENV, venv_bin

ALLOWED = {
    "summary": ("analyze", "summary"),
    "sanity-check": ("analyze", "sanity-check"),
    "interactions": ("analyze", "interactions"),
    "polyhedra": ("analyze", "polyhedra"),
    "molecules": ("io", "molecules"),
}


def file_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_mck(command: str, path: Path, *extra: str, timeout: float = 600.0, use_cache: bool = True) -> dict[str, Any]:
    """Run ``mck <group> <cmd> PATH [extra] --json``; returns {"ok", "data"|"error"}."""
    if command not in ALLOWED:
        raise ValueError(f"mck command not allowed: {command}")
    group, sub = ALLOWED[command]
    key = hashlib.sha256(json.dumps([command, file_sha(path), list(extra)]).encode()).hexdigest()[:24]
    cache_file = CACHE / "mck" / f"{key}.json"
    if use_cache and cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    argv = [venv_bin("mck"), group, sub, str(path), *extra, "--json"]
    try:
        p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, env=SUBPROCESS_ENV)
    except subprocess.TimeoutExpired:
        out = {"ok": False, "error": f"timeout after {timeout}s", "argv": argv[1:]}
    else:
        try:
            out = {"ok": p.returncode == 0, "data": json.loads(p.stdout), "argv": argv[1:]}
            if p.returncode != 0:
                out["error"] = (p.stderr or "")[-800:]
        except json.JSONDecodeError:
            out = {"ok": False, "error": (p.stderr or p.stdout or "")[-800:], "argv": argv[1:]}
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(out), encoding="utf-8")
    return out


def trim_molecules(data: list[dict]) -> list[dict]:
    keep = ("molecule_index", "formula", "species_id", "atom_count", "centroid_frac")
    return [{k: m.get(k) for k in keep} for m in data]


def trim_summary(data: dict) -> dict:
    out = dict(data)
    sym = dict(out.get("symmetry") or {})
    sym.pop("wyckoff_sites", None)
    out["symmetry"] = sym
    return out


def trim_polyhedra(data: list[dict]) -> list[dict]:
    keep = ("center_index", "center_symbol", "coordination_number", "shell_distances", "enclosed")
    return [{k: p.get(k) for k in keep} for p in data]