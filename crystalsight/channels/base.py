from __future__ import annotations

import json
from typing import Any

from ..models import Model, extract_json

SYSTEM = (
    "You are an expert crystallographer and structural chemist. You will be asked one "
    "question about a crystal structure. Base your answer only on what you are given or "
    "observe. When you are ready, reply with a single JSON object {\"answer\": <value>} "
    "and nothing else."
)

FORMAT = {
    "int": "The answer must be a single integer, e.g. {\"answer\": 4}.",
    "bool": "The answer must be true or false, e.g. {\"answer\": true}.",
    "set": "The answer must be a JSON list of option strings (possibly empty), e.g. {\"answer\": [\"hydrogen_bond\"]}.",
    "formula_set": "The answer must be a JSON list of Hill formulas, e.g. {\"answer\": [\"C8H9NO2\"]}.",
}


FORMAT["choice"] = "The answer must be exactly one of the options as a JSON string, e.g. {\"answer\": \"A\"}."


def _field_desc(name: str, spec: dict) -> str:
    t = spec["type"]
    d = {"bool": "true/false", "int": "integer", "set": "JSON list", "choice": "one string", "label": "atom label string"}[t]
    if spec.get("options"):
        d += " from [" + ", ".join(spec["options"]) + "]"
    if spec.get("hint"):
        d += " (" + spec["hint"] + ")"
    return f"  \"{name}\": {d}"


def answer_instructions(task: dict) -> str:
    if task.get("benchmark") in ("v3", "v4"):  # the question already states the answer object; only the wrapper is added
        keys = list(task["gold"])
        if keys == ["answer"]:
            return 'Final reply format: {"answer": "<letter>"}.'
        inner = ", ".join(f'"{k}": ...' for k in keys)
        return ('Final reply format: {"answer": {' + inner + '}} - the JSON object requested above wrapped in '
                '{"answer": ...}. ' + ('Write atom copies in the copy-aware label form defined in the question.' if task.get("benchmark") == "v4" else 'Use atom labels exactly as written in the CIF (no symmetry/copy suffixes).'))
    if task["answer_type"] == "object":
        fields = "\n".join(_field_desc(k, v) for k, v in task["schema"].items())
        return ("The answer must be a JSON object with exactly these keys:\n" + fields +
                "\nReply as {\"answer\": {...}}. If the first key is false/negative, give empty lists for the others.")
    s = FORMAT.get(task["answer_type"], "")
    if task.get("options"):
        s += " Options: " + ", ".join(task["options"]) + "."
    return s


def task_structures(task: dict) -> list[dict]:
    """[{label, structure_id, path}] - one entry for single-structure tasks, two (A, B) for comparisons."""
    if task.get("structures"):
        return task["structures"]
    return [{"label": "", "structure_id": task["structure_id"], "path": task["path"]}]


# Lenient parsing (applied identically to every model): a reply that gives the answer object
# itself, without the {"answer": ...} wrapper, is accepted when it carries a family key.
BARE_KEYS = {"missing_h", "disordered", "cn", "usable",
             # v3 spatial tasks (tasks_v3/): the question text shows the bare object
             "acceptor_label", "relation", "network", "axis", "packing", "distance_bin", "stacking",
             # v4 (tasks_v4/)
             "acceptor", "hops", "ring_size", "n_molecules", "count", "major", "minor"}


def unwrap(parsed):
    if not isinstance(parsed, dict):
        return None
    if "answer" in parsed:
        return parsed
    if "action" not in parsed and "tool" not in parsed and BARE_KEYS & set(parsed):
        return {"answer": parsed}
    return None


class Channel:
    name = "base"
    needs_vision = False
    max_steps = 1

    def run(self, task: dict, model: Model) -> dict[str, Any]:
        raise NotImplementedError

    # helpers ---------------------------------------------------------
    @staticmethod
    def final(record: dict, reply_text: str) -> dict:
        parsed = unwrap(extract_json(reply_text))
        record["raw_final"] = reply_text[-4000:]
        if parsed is None or "answer" not in parsed:
            record["parse_error"] = "no {answer} JSON in final reply"
            record["answer"] = None
        else:
            record["answer"] = parsed["answer"]
        return record

    @staticmethod
    def log_turn(record: dict, role: str, content: Any, **extra) -> None:
        record.setdefault("transcript", []).append({"role": role, "content": content, **extra})

    @staticmethod
    def usage_add(record: dict, usage: dict, latency_ms: float) -> None:
        u = record.setdefault("usage", {"prompt_tokens": 0, "completion_tokens": 0, "latency_ms": 0.0, "calls": 0})
        u["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
        u["completion_tokens"] += int(usage.get("completion_tokens") or 0)
        u["latency_ms"] += latency_ms
        u["calls"] += 1


def dumps(o: Any) -> str:
    return json.dumps(o, ensure_ascii=False)