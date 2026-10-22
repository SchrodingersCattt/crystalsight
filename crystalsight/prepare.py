"""Warm the expensive per-structure caches in parallel processes:
MatterVis renders (image channel) and TUI CrystalIR pickles (tui channel).
Writes data/prepare_log.json with timings and failures."""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from .paths import DATA, ROOT, TASKS


def _prep(sid: str, path: str, do_render: bool, do_tui: bool) -> dict:
    out = {"structure_id": sid}
    if do_render:
        from .channels.image import render_views
        t = time.monotonic()
        try:
            render_views(sid, ROOT / path)
            out["render_s"] = round(time.monotonic() - t, 1)
        except Exception as e:  # noqa: BLE001
            out["render_error"] = str(e)[:300]
    if do_tui:
        from .channels.tui import load_crystal
        t = time.monotonic()
        try:
            load_crystal(sid, ROOT / path)
            out["tui_load_s"] = round(time.monotonic() - t, 1)
        except Exception as e:  # noqa: BLE001
            out["tui_error"] = f"{type(e).__name__}: {str(e)[:300]}"
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--no-tui", action="store_true")
    args = ap.parse_args()
    tasks = [json.loads(l) for l in (TASKS / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    structs = sorted({(t["structure_id"], t["path"]) for t in tasks})
    log_path = DATA / "prepare_log.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else {}
    with ProcessPoolExecutor(args.workers) as ex:
        futs = [ex.submit(_prep, sid, p, not args.no_render, not args.no_tui) for sid, p in structs]
        for f in as_completed(futs):
            r = f.result()
            log[r["structure_id"]] = {**log.get(r["structure_id"], {}), **r}
            print(json.dumps(r), flush=True)
            log_path.write_text(json.dumps(log, indent=1), encoding="utf-8")
    print(f"prepared {len(structs)} structures")


if __name__ == "__main__":
    main()