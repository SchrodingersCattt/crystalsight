"""Channel 2: pixels. Three orthographic MatterVis CPU renders along a, b, c."""

from __future__ import annotations

import base64
import json
import subprocess
import threading
from pathlib import Path

from ..paths import DATA, ROOT, SUBPROCESS_ENV, rel, venv_bin
from .base import SYSTEM, Channel, answer_instructions, task_structures

AXES = ("a", "b", "c")
RENDERS = DATA / "renders"
_locks: dict[str, threading.Lock] = {}
_glock = threading.Lock()


def render_views(structure_id: str, cif: Path, size: int = 640) -> list[dict]:
    with _glock:
        lock = _locks.setdefault(structure_id, threading.Lock())
    out = []
    with lock:
        for axis in AXES:
            png = RENDERS / f"{structure_id}_{axis}.png"
            meta = png.with_suffix(".json")
            if not (png.exists() and meta.exists()):
                png.parent.mkdir(parents=True, exist_ok=True)
                argv = [venv_bin("mat-vis"), "render", str(cif), "-o", str(png), "--backend", "cpu",
                        "--view", "unit_cell", "--camera-axis", axis, "--orthogonal", "--show-cell",
                        "--width", str(size), "--height", str(size), "--scale", "1", "--json"]
                p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   timeout=900, env=SUBPROCESS_ENV)
                try:
                    res = json.loads(p.stdout)
                except json.JSONDecodeError:
                    res = {"ok": False, "stderr": (p.stderr or "")[-600:]}
                res["argv"] = [Path(argv[0]).name, *argv[1:]]
                meta.write_text(json.dumps(res), encoding="utf-8")
                if p.returncode != 0 or not png.exists():
                    meta.unlink(missing_ok=True)
                    raise RuntimeError(f"mat-vis render failed for {structure_id}/{axis}: {(p.stderr or '')[-300:]}")
            res = json.loads(meta.read_text(encoding="utf-8"))
            out.append({"axis": axis, "path": rel(png), "sha256": (res.get("output") or {}).get("sha256")})
    return out


class ImageChannel(Channel):
    name = "image"
    needs_vision = True

    def run(self, task, model):
        rec = {"channel": self.name, "steps": 0}
        structs = task_structures(task)
        views = []
        for st in structs:
            for v in render_views(st["structure_id"], ROOT / st["path"]):
                views.append({**v, "label": st["label"]})
        rec["views"] = views
        what = "one unit cell" if len(structs) == 1 else "the unit cell of each structure (A and B)"
        parts = [{"type": "text", "text": (
            f"Question: {task['question']}\n{answer_instructions(task)}\n\n"
            f"Below are three orthographic ball-and-stick renders of {what} (cell edges drawn), "
            "viewed along the crystallographic a, b and c axes. Element colours follow the usual "
            "CPK/Jmol convention.")}]
        for v in views:
            b64 = base64.b64encode((ROOT / v["path"]).read_bytes()).decode()
            lab = f"Structure {v['label']}, view" if v["label"] else "View"
            parts.append({"type": "text", "text": f"{lab} along {v['axis']}:"})
            parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": parts}]
        self.log_turn(rec, "user", f"<3 PNG views {[v['path'] for v in views]}>\nQuestion: {task['question']}")
        r = model.complete(msgs, context={"task": task, "channel": self.name, "step": 0})
        self.usage_add(rec, r.usage, r.latency_ms)
        if r.error:
            rec["error"] = r.error
            rec["answer"] = None
            return rec
        self.log_turn(rec, "assistant", r.text[-4000:])
        rec["steps"] = 1
        return self.final(rec, r.text)