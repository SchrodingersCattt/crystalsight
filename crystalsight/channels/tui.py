"""Channel 3: interactive ASCII. A text-only model drives a MatterVis
TerminalSession (same engine as ``mat-vis tui --session-format jsonl``).

Leakage control: the model sees ONLY the rendered frame lines plus the camera
state. The observation's title, scope (formula/atom counts) and warnings
(which name molecule IDs) are withheld. Perception-only actions are allowed;
select/focus (which open the chemistry inspector) are refused, following the
MatterVis ``inspect-structure-tui`` skill.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import subprocess
import sys
import threading
from pathlib import Path

from ..models import extract_json
from ..paths import CACHE, ROOT, SUBPROCESS_ENV
from .base import SYSTEM, Channel, answer_instructions, task_structures, unwrap

ALLOWED = ("observe", "reset", "orbit", "align", "pan", "zoom", "fit", "set_display")
WIDTH, HEIGHT = 100, 36

GUIDE = f"""You are looking at the structure through a {WIDTH}x{HEIGHT} ASCII terminal renderer
(MatterVis TUI, ASCII-7 charset, orthographic, unit cell). You cannot see coordinates.
Each turn reply with exactly ONE JSON object, either an action or the final answer:
  {{"action": "orbit", "arguments": {{"yaw_deg": 30, "pitch_deg": 15}}}}
  {{"action": "align", "arguments": {{"axis": "c"}}}}            axes: a b c a* b* c*
  {{"action": "zoom", "arguments": {{"factor": 1.5}}}}
  {{"action": "pan", "arguments": {{"dx": 0.1, "dy": 0.0}}}}
  {{"action": "fit", "arguments": {{"target": "all"}}}}
  {{"action": "set_display", "arguments": {{"display_level": "atom", "label_mode": "element", "show_bonds": true, "show_cell": true}}}}
     display_level: atom | molecule ; label_mode: auto | element | none
  {{"action": "reset", "arguments": {{}}}}
  {{"answer": ...}}
Allowed actions: {", ".join(ALLOWED)}. You have a budget of {{budget}} actions; after that you must answer."""


def _frame(obs: dict) -> str:
    cam = obs.get("camera", {})
    disp = obs.get("display", {})
    head = (f"[camera az={cam.get('azimuth', 0):.0f} el={cam.get('elevation', 0):.0f} roll={cam.get('roll', 0):.0f} "
            f"zoom={cam.get('zoom', 1):.2f}] [display level={disp.get('display_level')} labels={disp.get('label_mode')} "
            f"bonds={disp.get('show_bonds')} cell={disp.get('show_cell')}]")
    return head + "\n" + obs["frame"]["text"]


_crystals: dict[str, object] = {}
_clock = threading.Lock()
_slocks: dict[str, threading.Lock] = {}

# Building the TUI CrystalIR runs full MolCrysKit perception. For a few heavily
# disordered structures (e.g. mck_anhydrousCaffeine2) it does not finish in >1 h,
# which previously stalled the whole run. It now runs in a child process with a
# hard timeout; a failure is cached as a ``.failed`` marker and the task is
# recorded as an infrastructure error (excluded from scoring) instead of hanging.
TUI_LOAD_TIMEOUT_S = int(os.environ.get("CRYSTALSIGHT_TUI_LOAD_TIMEOUT", "600"))
_LOADER = (
    "import pickle, sys\n"
    "from mat_viewer.tui.loader_adapter import load_for_tui\n"
    "c = load_for_tui(sys.argv[1], display_mode='auto')\n"
    "open(sys.argv[2], 'wb').write(pickle.dumps(c))\n"
)


class TuiLoadError(RuntimeError):
    pass


def _kill_tree(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        proc.kill()


def _build_pickle(path: Path, pkl: Path, failed: Path) -> None:
    pkl.parent.mkdir(parents=True, exist_ok=True)
    tmp = pkl.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    proc = subprocess.Popen([sys.executable, "-c", _LOADER, str(path), str(tmp)], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", env=SUBPROCESS_ENV)
    try:
        _, err = proc.communicate(timeout=TUI_LOAD_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        proc.communicate()
        failed.write_text(f"TUI load timeout after {TUI_LOAD_TIMEOUT_S}s", encoding="utf-8")
        raise TuiLoadError(failed.read_text(encoding="utf-8"))
    if proc.returncode != 0 or not tmp.exists():
        failed.write_text(f"TUI load failed (rc={proc.returncode}): {(err or '')[-400:]}", encoding="utf-8")
        raise TuiLoadError(failed.read_text(encoding="utf-8"))
    tmp.replace(pkl)


def load_crystal(structure_id: str, path: Path):
    """Load the MatterVis terminal CrystalIR once per structure (memory + pickle cache)."""
    with _clock:
        lock = _slocks.setdefault(structure_id, threading.Lock())
    with lock:
        if structure_id in _crystals:
            return _crystals[structure_id]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        pkl = CACHE / "tui" / f"{structure_id}_{digest}.pkl"
        failed = pkl.with_suffix(".failed")
        if failed.exists():
            raise TuiLoadError(failed.read_text(encoding="utf-8"))
        crystal = None
        if pkl.exists():
            try:
                crystal = pickle.loads(pkl.read_bytes())
            except Exception:  # noqa: BLE001 - stale/incompatible cache
                crystal = None
        if crystal is None:
            _build_pickle(path, pkl, failed)
            crystal = pickle.loads(pkl.read_bytes())
        _crystals[structure_id] = crystal
        return crystal


PAIR_GUIDE = """
Two structures (A and B) are loaded in separate viewers; actions apply to the active one.
  {"action": "switch", "arguments": {"structure": "B"}}   makes B active and shows its current view (costs one action)."""


class TuiChannel(Channel):
    name = "tui"
    max_steps = 8

    def __init__(self, budget: int = 8):
        self.budget = budget

    def run(self, task, model):
        from mat_viewer.tui import TerminalAction, TerminalSession

        rec = {"channel": self.name, "steps": 0, "frames": [], "actions": []}
        structs = task_structures(task)
        sessions = {}
        for st in structs:
            crystal = load_crystal(st["structure_id"], Path(ROOT / st["path"]))
            sessions[st["label"]] = TerminalSession(crystal, width=WIDTH, height=HEIGHT, charset="ascii7")
        labels = list(sessions)
        active = labels[0]
        pair = len(labels) > 1
        budget = self.budget * (2 if pair else 1)
        allowed = ALLOWED + (("switch",) if pair else ())

        def tag(label):
            return f"[structure {label}] " if pair else ""

        initial = []
        for lab in labels:
            fr = tag(lab) + _frame(sessions[lab].observe().as_dict())
            rec["frames"].append(fr)
            initial.append(fr)
        guide = GUIDE.replace("{budget}", str(budget)) + (PAIR_GUIDE if pair else "")
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Question: {task['question']}\n{answer_instructions(task)}\n\n{guide}\n\n"
                                            f"Initial view{'s' if pair else ''} (active: {active or 'the structure'}):\n" + "\n\n".join(initial)}]
        self.log_turn(rec, "user", f"Question: {task['question']}\n<initial frame(s)>")
        invalid = 0
        for step in range(budget + 1):
            r = model.complete(msgs, context={"task": task, "channel": self.name, "step": step})
            self.usage_add(rec, r.usage, r.latency_ms)
            if r.error:
                rec["error"] = r.error
                rec["answer"] = None
                return rec
            self.log_turn(rec, "assistant", r.text[-2000:])
            rec["steps"] = step + 1
            raw = extract_json(r.text) or {}
            parsed = unwrap(raw) or raw
            if "answer" in parsed:
                return self.final(rec, r.text)
            if step >= budget:
                break
            name = parsed.get("action")
            args = parsed.get("arguments") or {}
            msgs.append({"role": "assistant", "content": r.text})
            left = budget - step - 1
            if name not in allowed:
                invalid += 1
                feedback = f"Invalid action {name!r}. Allowed: {', '.join(allowed)}. Reply with one JSON object."
                rec["actions"].append({"action": name, "ok": False})
                if invalid >= 2:
                    msgs.append({"role": "user", "content": feedback + " Two invalid actions in a row: answer now."})
                    self.log_turn(rec, "user", "<two invalid actions; forced answer>")
                    r = model.complete(msgs, context={"task": task, "channel": self.name, "step": budget})
                    self.usage_add(rec, r.usage, r.latency_ms)
                    self.log_turn(rec, "assistant", r.text[-2000:])
                    return self.final(rec, r.text)
            elif name == "switch":
                want = str(args.get("structure", "")).strip().upper()
                if want in sessions:
                    active, invalid = want, 0
                    frame = tag(active) + _frame(sessions[active].observe().as_dict())
                    rec["frames"].append(frame)
                    rec["actions"].append({"action": name, "arguments": args, "ok": True})
                    feedback = f"Now viewing structure {active} ({left} actions left):\n{frame}"
                else:
                    invalid += 1
                    rec["actions"].append({"action": name, "arguments": args, "ok": False})
                    feedback = f"Unknown structure {want!r}; use A or B."
            else:
                try:
                    obs = sessions[active].execute(TerminalAction(name, dict(args))).as_dict()
                    if "frame" not in obs:
                        raise ValueError(obs.get("error") or "action returned no frame")
                    invalid = 0
                    frame = tag(active) + _frame(obs)
                    rec["frames"].append(frame)
                    rec["actions"].append({"action": name, "arguments": args, "ok": True, "structure": active})
                    feedback = f"View after {name} ({left} actions left):\n{frame}"
                except Exception as exc:  # noqa: BLE001 - structured error back to model
                    invalid += 1
                    rec["actions"].append({"action": name, "arguments": args, "ok": False, "error": str(exc)[:200]})
                    feedback = f"Action error: {str(exc)[:200]}. Reply with one JSON object."
            msgs.append({"role": "user", "content": feedback})
            self.log_turn(rec, "user", feedback.split("\n", 1)[0])
        msgs.append({"role": "user", "content": "Action budget exhausted. Reply now with {\"answer\": ...} only."})
        r = model.complete(msgs, context={"task": task, "channel": self.name, "step": budget + 1})
        self.usage_add(rec, r.usage, r.latency_ms)
        self.log_turn(rec, "assistant", r.text[-2000:])
        return self.final(rec, r.text)
