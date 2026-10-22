"""Scoring for CrystalSight v3 spatial tasks (tasks_v3/tasks_v3.jsonl).

Separate from ``score.py`` so the v1/v2 scorer behaviour is unchanged.
Every v3 gold is a flat dict of categorical fields; each field is exact-match
after normalisation, combined with the per-task ``score_weights``
(F1: acceptor_label 0.3 + relation 0.7; F5: 0.5 + 0.5; others: single field = 1.0).
``strict`` is 1.0 only when every field matches.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DEFAULT_WEIGHTS = {"F1": {"acceptor_label": 0.3, "relation": 0.7}, "F5": {"distance_bin": 0.5, "stacking": 0.5}}
_REL_ALIASES = {"2_1": "2_1 screw", "21 screw": "2_1 screw", "2(1) screw": "2_1 screw", "screw": "2_1 screw",
                "screw axis": "2_1 screw", "2-fold screw": "2_1 screw", "2 fold rotation": "2-fold rotation",
                "rotation": "2-fold rotation", "2-fold": "2-fold rotation", "c2": "2-fold rotation",
                "glide plane": "glide", "mirror plane": "mirror", "centre of inversion": "inversion",
                "center of inversion": "inversion", "inversion centre": "inversion", "inversion center": "inversion",
                "lattice translation": "translation", "pure translation": "translation"}


INT_FIELDS = {"hops", "ring_size", "n_molecules", "count", "major", "minor"}  # v4 (tasks_v4/)
_COPY = re.compile(r"^(.+?)(?:#(\d+))?(?:\[(-?\d+),(-?\d+),(-?\d+)\])?$")


def _copy_parts(v):
    """Copy-aware label SITE#k[i,j,k] -> (SITE, k, (i,j,k)); #1 and [0,0,0] may be omitted."""
    if v is None:
        return None
    m = _COPY.match(re.sub(r"\s+", "", str(v)).strip("\"'"))
    if not m:
        return None
    site, k, *sh = m.groups()
    return site.upper(), int(k or 1), tuple(int(x or 0) for x in sh)


def _copy_score(ans, gold) -> float:
    """v4 G1: 0.2 site label + 0.4 symmetry-operation index + 0.4 lattice shift."""
    a, g = _copy_parts(ans), _copy_parts(gold)
    if a is None:
        return 0.0
    return round(0.2 * (a[0] == g[0]) + 0.4 * (a[1] == g[1]) + 0.4 * (a[2] == g[2]), 4)


def _norm(field: str, v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if field in INT_FIELDS:
        try:
            return str(int(float(s)))
        except ValueError:
            return s.lower().strip("\"'")
    if field == "acceptor_label":  # drop the TUI copy-aware suffixes (#k, [i,j,k]); primes etc. are real label parts
        s = re.sub(r"\s+", "", s)
        s = re.sub(r"(#\d+)?(\[-?\d+,-?\d+,-?\d+\])?$", "", s)
        return s.upper()
    s = s.lower().replace("\u2081", "1")
    s = re.sub(r"\s+", " ", s)
    if field == "relation":
        s = s.replace("_", "_") if "2_1" in s else s
        return _REL_ALIASES.get(s, s)
    if field == "answer":
        m = re.match(r"^\(?([a-e])\)?\b", s)
        return m.group(1).upper() if m else s.upper()
    if field == "network":
        return s.replace(" ", "_").replace("-", "_").upper().replace("_AB", "_ab").replace("_AC", "_ac") \
            .replace("_BC", "_bc").replace("_A", "_a").replace("_B", "_b").replace("_C", "_c").replace("_OTHER", "_other")
    return s.replace(" ", "_") if field in ("stacking", "packing") else s


def score_v3(task: dict, answer) -> dict:
    """Return {"score": weighted float, "strict": 0/1, "fields": {field: 0/1}, "reason": str}."""
    gold = task["gold"]
    weights = task.get("score_weights") or DEFAULT_WEIGHTS.get(task.get("family")) or {k: 1.0 / len(gold) for k in gold}
    if isinstance(answer, str):
        try:
            answer = json.loads(answer)
        except json.JSONDecodeError:
            pass  # plain string, e.g. a bare option letter "C"
    if isinstance(answer, dict) and "answer" in answer and isinstance(answer["answer"], dict):
        answer = answer["answer"]
    if not isinstance(answer, dict):
        if len(gold) == 1 and answer is not None:
            answer = {next(iter(gold)): answer}
        else:
            return {"score": 0.0, "strict": 0, "fields": {k: 0 for k in gold}, "reason": "unparseable answer"}
    fields = {}
    for k, g in gold.items():
        if k == "acceptor":  # v4 copy-aware label, partial credit inside the field
            fields[k] = _copy_score(answer.get(k), g)
        else:
            fields[k] = int(_norm(k, answer.get(k)) == _norm(k, g))
    score = sum(weights.get(k, 0.0) * v for k, v in fields.items())
    strict = int(all(v == 1 for v in fields.values()))
    bad = [f"{k}: got {answer.get(k)!r}, gold {gold[k]!r}" for k, v in fields.items() if v != 1]
    return {"score": round(score, 4), "strict": strict, "fields": fields, "reason": "; ".join(bad) or "all fields correct"}


def load_tasks(path: str | Path = Path(__file__).resolve().parents[1] / "tasks_v3" / "tasks_v3.jsonl") -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


if __name__ == "__main__":  # self-test: gold scores 1, chance-like wrong answers score 0 / partial
    for t in load_tasks():
        ok = score_v3(t, t["gold"])
        assert ok["score"] == 1.0 and ok["strict"] == 1, (t["id"], ok)
    t1 = next(t for t in load_tasks() if t["family"] == "F1")
    half = dict(t1["gold"], acceptor_label="ZZ9")
    assert score_v3(t1, half)["score"] == 0.7 and score_v3(t1, half)["strict"] == 0
    t3 = next(t for t in load_tasks() if t["family"] == "F3")
    assert score_v3(t3, t3["gold"]["answer"])["score"] == 1.0, "bare option letter"
    print("score_v3 self-test ok")
