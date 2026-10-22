"""Channel 4: tool calls (reference upper bound, reported separately from the main leaderboard).

The model may call read-only MolCrysKit analyses. Several of these are the same
computations that produce the gold answers, so this channel measures tool use and
reading, not perception.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..mck_cli import run_mck, trim_molecules, trim_polyhedra, trim_summary
from ..models import extract_json
from ..paths import DATA, ROOT
from .base import SYSTEM, Channel, answer_instructions, task_structures, unwrap
from .geom_tools import GEOM_TOOLS, call_geom

MAX_TOOL_CHARS = 12000
TOOLS = {
    "mck_analyze_summary": "composition, cell, space group, disorder summary (partial-occupancy sites, disorder groups)",
    "mck_io_molecules": "molecule inventory: one entry per molecule/ion with formula, species_id, atom count",
    "mck_analyze_sanity_check": "clashes, isolated atoms, hydrogen presence, bond distances",
    "mck_add_h_report": "runs MolCrysKit hydrogen completion; reports H count before, H added, added H per parent element",
    "mck_analyze_polyhedra": "coordination polyhedra for one donor element; arguments {\"central\": \"Zn\", \"ligand\": \"N\"}",
    "mck_coordination_shape": "metal donor shell (all non-H donors) with CShM shape fit; arguments {\"metal\": \"Zn\"}",
}


def _gt(path: Path) -> dict:
    sid = path.stem
    f = DATA / "gt" / f"{sid}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def call_tool(name: str, args: dict, path: Path) -> object:
    if name.startswith("geom_"):  # ad hoc geometry tools (geom_tools.py), offered for v4 tasks only
        return call_geom(name, args, path)
    if name == "mck_analyze_summary":
        r = run_mck("summary", path)
        return trim_summary(r["data"]) if r["ok"] else {"error": r.get("error")}
    if name == "mck_io_molecules":
        r = run_mck("molecules", path)
        return trim_molecules(r["data"]) if r["ok"] else {"error": r.get("error")}
    if name == "mck_analyze_sanity_check":
        r = run_mck("sanity-check", path)
        if not r["ok"]:
            return {"error": r.get("error")}
        return [{"name": x["name"], "status": x["status"], "message": x["message"]}
                for x in r["data"]["frames"][0]["results"]]
    if name == "mck_add_h_report":
        h = _gt(path).get("hydrogen") or {}
        if "n_added" not in h:
            return {"error": h.get("error", "hydrogen completion unavailable")}
        return {"h_before": h["n_before"], "h_added": h["n_added"], "added_per_parent_element": h["added_by_element"]}
    if name == "mck_analyze_polyhedra":
        c, l = str(args.get("central", "")), str(args.get("ligand", ""))
        if not c.isalpha() or not l.isalpha():
            return {"error": "central and ligand must be element symbols"}
        r = run_mck("polyhedra", path, "--central", c, "--ligand", l, "--level", "atom")
        return trim_polyhedra(r["data"]) if r["ok"] else {"error": r.get("error")}
    if name == "mck_coordination_shape":
        m = (_gt(path).get("metals") or {}).get(str(args.get("metal", "")))
        if not m:
            return {"error": "no such metal in structure"}
        return {k: m.get(k) for k in ("n_sites", "cns", "cn", "geometry", "cshm") if k in m}
    return {"error": f"unknown tool {name}"}


class ToolsChannel(Channel):
    name = "tools"
    max_steps = 6

    def run(self, task, model):
        rec = {"channel": self.name, "steps": 0, "tool_calls": []}
        structs = {st["label"]: ROOT / st["path"] for st in task_structures(task)}
        pair = len(structs) > 1
        offered = dict(TOOLS, **(GEOM_TOOLS if task.get("benchmark") == "v4" else {}))
        tools_txt = "\n".join(f"  {k}: {v}" for k, v in offered.items())
        if task.get("benchmark") == "v4":
            tools_txt += ("\n  (geom_* = ad hoc geometry tools over the expanded crystal; atoms are named with copy-aware labels "
                          "SITE#k[i,j,k] as defined in the question; they return raw contacts/neighbours/paths - choose the "
                          "criteria the question uses and count/interpret the results yourself)")
        user = (f"Question: {task['question']}\n{answer_instructions(task)}\n\n"
                "You cannot see the structure, but you may call MolCrysKit analysis tools on it. "
                "Each turn reply with exactly one JSON object: either a tool call "
                "{\"tool\": \"<name>\", \"arguments\": {...}} or the final {\"answer\": ...}.\n"
                + ("Two structures are available; add \"structure\": \"A\" or \"B\" to the arguments of every tool call.\n" if pair else "")
                + f"Tools:\n{tools_txt}\nYou may make at most {self.max_steps} tool calls.")
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
        self.log_turn(rec, "user", f"Question: {task['question']}\n<tool list>")
        for step in range(self.max_steps + 1):
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
            if "answer" in parsed or step >= self.max_steps:
                return self.final(rec, r.text)
            name = parsed.get("tool")
            args = dict(parsed.get("arguments") or {})
            label = str(args.pop("structure", "")).strip().upper() if pair else ""
            if pair and label not in structs:
                result = {"error": "add \"structure\": \"A\" or \"B\" to the arguments"}
            elif not name:
                result = {"error": "no tool or answer"}
            elif str(name) not in offered:
                result = {"error": f"unknown tool {name}; available: {', '.join(offered)}"}
            else:
                result = call_tool(str(name), args, structs[label])
            txt = json.dumps(result, ensure_ascii=False)
            if len(txt) > MAX_TOOL_CHARS:
                txt = txt[:MAX_TOOL_CHARS] + " ...<truncated>"
            rec["tool_calls"].append({"tool": name, "arguments": parsed.get("arguments") or {}, "result_chars": len(txt)})
            msgs.append({"role": "assistant", "content": r.text})
            msgs.append({"role": "user", "content": f"Tool result ({name}{' on ' + label if label else ''}):\n{txt}"})
            self.log_turn(rec, "user", f"<tool result {name}, {len(txt)} chars>")
        return self.final(rec, "")
