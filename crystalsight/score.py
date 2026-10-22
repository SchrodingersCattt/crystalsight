"""Auto-scorer: deterministic comparison against mck-derived gold."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from .paths import RUNS, TASKS


def _norm_formula(f: str) -> str:
    """Canonical Hill-like form: element counts sorted C, H, then alphabetical."""
    f = re.sub(r"[\s\[\]{}()]", "", str(f))
    counts: dict[str, float] = defaultdict(float)
    for el, n in re.findall(r"([A-Z][a-z]?)(\d*\.?\d*)", f):
        counts[el] += float(n) if n else 1.0
    order = sorted(counts, key=lambda e: (e != "C", e != "H", e))
    return "".join(f"{e}{'' if counts[e] == 1 else int(counts[e]) if counts[e].is_integer() else counts[e]}" for e in order)


def _as_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str) and v.strip().lower() in ("true", "yes"):
        return True
    if isinstance(v, str) and v.strip().lower() in ("false", "no"):
        return False
    return None


def _as_int(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)) and float(v).is_integer():
        return int(v)
    if isinstance(v, str) and re.fullmatch(r"\s*-?\d+\s*", v):
        return int(v)
    return None


def _as_list(v):
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        return [x for x in re.split(r"[,\s]+", v) if x]
    return None


def _f1(pred, ref) -> float:
    pred, ref = set(pred), set(ref)
    if not pred and not ref:
        return 1.0
    tp = len(pred & ref)
    if tp == 0:
        return 0.0
    p, r = tp / len(pred), tp / len(ref)
    return 2 * p * r / (p + r)


def _norm_set(v, upper_first: bool = False):
    lst = _as_list(v) if v is not None else []
    if lst is None:
        return None
    out = set()
    for x in lst:
        x = str(x).strip()
        out.add(x[:1].upper() + x[1:].lower() if upper_first else x.lower())
    return out


# ------------------------------------------------------------------ family scoring
# Partial credit, every family scores in [0, 1]:
#  Q3_hydrogen   gold complete: 1 iff missing_h=false.  gold missing: 0.5*[missing_h=true] + 0.5*F1(elements)
#  Q4_disorder   gold ordered: 1 iff disordered=false.  gold disordered: 1/3*[disordered=true]
#                + 1/3*F1(components) + 1/3*F1(types)   (components/types only count if disordered=true)
#  Q6_coordination 0.5*[cn exact] + 0.5*[geometry exact]
#  Q7_usability  gold usable: 1 iff usable=true.  gold not usable: 0.5*[usable=false] + 0.5*F1(issues)
#  Q8_compare    exact match of A / B / both / neither
FLAG = {"Q3_hydrogen": ("missing_h", True, "elements"), "Q4_disorder": ("disordered", True, None),
        "Q7_usability": ("usable", False, "issues")}


def score_object(task: dict, ans) -> tuple[float, str]:
    if not isinstance(ans, dict):
        return 0.0, "unparseable"
    q, gold = task["qtype"], task["gold"]
    if q == "Q6_coordination":
        cn = _as_int(ans.get("cn"))
        geo = str(ans.get("geometry", "")).strip().lower().replace(" ", "_").replace("-", "_")
        return 0.5 * (cn == gold["cn"]) + 0.5 * (geo == gold["geometry"]), ""
    flag, bad_value, set_key = FLAG[q]
    pf = _as_bool(ans.get(flag))
    if pf is None:
        return 0.0, "unparseable"
    gf = gold[flag]
    if gf != bad_value:  # clean structure: only the flag matters
        return float(pf == gf), ""
    if pf != bad_value:
        return 0.0, ""
    if q == "Q4_disorder":
        c = _norm_set(ans.get("components")) or set()
        t = _norm_set(ans.get("types")) or set()
        return (1 + _f1(c, gold["components"]) + _f1(t, gold["types"])) / 3, ""
    pred = _norm_set(ans.get(set_key), upper_first=(q == "Q3_hydrogen")) or set()
    return 0.5 + 0.5 * _f1(pred, gold[set_key]), ""


def score_answer(task: dict, answer) -> tuple[float, str]:
    """Returns (score in [0,1], note)."""
    t, gold = task["answer_type"], task["gold"]
    if answer is None:
        return 0.0, "no answer"
    if t == "object":
        return score_object(task, answer)
    if t == "choice":
        a = str(answer).strip()
        return float(a.lower() == str(gold).lower()), ("" if a.lower() in [o.lower() for o in task.get("options", [])] else "unparseable")
    if t == "bool":
        b = _as_bool(answer)
        return (1.0 if b == gold else 0.0), ("unparseable" if b is None else "")
    if t == "int":
        i = _as_int(answer)
        return (1.0 if i == gold else 0.0), ("unparseable" if i is None else "")
    if t in ("set", "formula_set"):
        lst = _as_list(answer)
        if lst is None:
            return 0.0, "unparseable"
        norm = _norm_formula if t == "formula_set" else (lambda s: str(s).strip().lower())
        pred, ref = {norm(x) for x in lst}, {norm(x) for x in gold}
        if not pred and not ref:
            return 1.0, ""
        tp = len(pred & ref)
        if tp == 0:
            return 0.0, ""
        p, r = tp / len(pred), tp / len(ref)
        return 2 * p * r / (p + r), ""
    return 0.0, f"unknown answer_type {t}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--tasks", default=str(TASKS / "tasks.jsonl"))
    args = ap.parse_args()
    run_dir = RUNS / args.run_id
    tasks = {t["id"]: t for t in (json.loads(l) for l in Path(args.tasks).read_text(encoding="utf-8").splitlines() if l.strip())}
    records = [json.loads(l) for l in (run_dir / "records.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    # keep the last record per (model, channel, task)
    latest = {}
    for r in records:
        latest[(r["model"], r["channel"], r["task_id"])] = r
    scored = []
    for (m, c, tid), r in sorted(latest.items()):
        task = tasks.get(tid)
        if task is None:
            continue
        if r.get("error"):
            s, note = 0.0, "infra error"
        else:
            s, note = score_answer(task, r.get("answer"))
        scored.append({"model": m, "channel": c, "task_id": tid, "qtype": task["qtype"], "structure_id": task["structure_id"],
                       "score": round(s, 4), "note": note, "answer": r.get("answer"), "gold": task["gold"],
                       "error": bool(r.get("error")), "steps": r.get("steps", 0),
                       "prompt_tokens": (r.get("usage") or {}).get("prompt_tokens", 0),
                       "completion_tokens": (r.get("usage") or {}).get("completion_tokens", 0)})
    (run_dir / "scored.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in scored) + "\n", encoding="utf-8")

    agg = defaultdict(lambda: {"n": 0, "sum": 0.0, "errors": 0, "unparseable": 0})
    for x in scored:
        for key in ((x["model"], x["channel"], "ALL"), (x["model"], x["channel"], x["qtype"])):
            a = agg[key]
            a["n"] += 1
            a["sum"] += x["score"]
            a["errors"] += x["error"]
            a["unparseable"] += x["note"] in ("unparseable", "no answer")
    rows = [{"model": k[0], "channel": k[1], "qtype": k[2], "n": v["n"], "accuracy": round(v["sum"] / v["n"], 4),
             "infra_errors": v["errors"], "unparseable": v["unparseable"]} for k, v in sorted(agg.items())]
    with (run_dir / "leaderboard.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["model"])
        w.writeheader()
        w.writerows(rows)
    (run_dir / "summary.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    for r in rows:
        if r["qtype"] == "ALL":
            print(f"{r['model']:24s} {r['channel']:8s} n={r['n']:4d} acc={r['accuracy']:.3f} err={r['infra_errors']} unparse={r['unparseable']}")


if __name__ == "__main__":
    main()