"""Analysis of a CrystalSight run: per-family scores, trivial baselines, problem-subset and balanced
scores, cif vs cif_raw leakage comparison, failure cases. Writes analysis/results.md + CSVs.

    python scripts/analyze.py --run real-full --random-run mock-e2e
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from crystalsight.score import score_answer  # noqa: E402

FAMILIES = ["Q3_hydrogen", "Q4_disorder", "Q6_coordination", "Q7_usability", "Q8_compare"]
FLAGGED = {"Q3_hydrogen": ("missing_h", True), "Q4_disorder": ("disordered", True), "Q7_usability": ("usable", False)}
CHANNEL_ORDER = ["cif", "cif_raw", "image", "tui", "tools"]


def run_dir(run: str) -> Path:
    """runs/<run> if it exists locally, else the compact released copy in results/<run>."""
    d = ROOT / "runs" / run
    return d if (d / "scored.jsonl").exists() else ROOT / "results" / run


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def is_problem(task: dict) -> bool | None:
    f = FLAGGED.get(task["qtype"])
    if not f:
        return None
    return task["gold"][f[0]] == f[1]


def no_problem_answer(task: dict, majority: dict) -> object:
    q = task["qtype"]
    if q == "Q3_hydrogen":
        return {"missing_h": False, "elements": []}
    if q == "Q4_disorder":
        return {"disordered": False, "components": [], "types": []}
    if q == "Q7_usability":
        return {"usable": True, "issues": []}
    return majority[q]


def summarize(scores: list[tuple[dict, float]]) -> dict:
    """scores: [(task, score)]. Returns mean, per-family mean, problem/clean subset means, balanced."""
    out = {"n": len(scores), "mean": sum(s for _, s in scores) / max(len(scores), 1)}
    fam = defaultdict(list)
    for t, s in scores:
        fam[t["qtype"]].append((t, s))
    bal = []
    for q in FAMILIES:
        xs = fam.get(q, [])
        if not xs:
            continue
        m = sum(s for _, s in xs) / len(xs)
        out[f"{q}"] = m
        out[f"{q}_n"] = len(xs)
        if q in FLAGGED:
            pr = [s for t, s in xs if is_problem(t)]
            cl = [s for t, s in xs if not is_problem(t)]
            mp = sum(pr) / len(pr) if pr else float("nan")
            mc = sum(cl) / len(cl) if cl else float("nan")
            out[f"{q}_problem"], out[f"{q}_clean"] = mp, mc
            out[f"{q}_problem_n"], out[f"{q}_clean_n"] = len(pr), len(cl)
            out[f"{q}_balanced"] = (mp + mc) / 2
            bal.append((mp + mc) / 2)
        else:
            out[f"{q}_balanced"] = m
            bal.append(m)
    out["macro_balanced"] = sum(bal) / len(bal) if bal else float("nan")
    prob = [s for t, s in scores if is_problem(t)]
    out["problem_subset"] = sum(prob) / len(prob) if prob else float("nan")
    out["problem_subset_n"] = len(prob)
    return out


def detection(scored: list[dict], tasks: dict) -> dict:
    """Binary detection of the flag (problem yes/no) for Q3/Q4/Q7: sensitivity, specificity."""
    res = {}
    for q, (key, bad) in FLAGGED.items():
        tp = fn = tn = fp = 0
        for x in scored:
            if x["qtype"] != q:
                continue
            a = x.get("answer")
            pred = a.get(key) if isinstance(a, dict) else None
            pred_bad = (pred == bad) if isinstance(pred, bool) else (not bad if False else None)
            gold_bad = tasks[x["task_id"]]["gold"][key] == bad
            if pred_bad is None:
                pred_bad = False  # unparseable counts as "no problem reported"
            if gold_bad:
                tp += pred_bad; fn += not pred_bad
            else:
                fp += pred_bad; tn += not pred_bad
        res[q] = {"sens": tp / max(tp + fn, 1), "spec": tn / max(tn + fp, 1), "tp": tp, "fn": fn, "tn": tn, "fp": fp}
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="real-full")
    ap.add_argument("--random-run", default="mock-e2e")
    ap.add_argument("--out", default=str(ROOT / "analysis"))
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    tasks = {t["id"]: t for t in load_jsonl(ROOT / "tasks" / "tasks.jsonl")}
    scored = [x for x in load_jsonl(run_dir(args.run) / "scored.jsonl") if x["task_id"] in tasks]
    # majority answers for families without a "no problem" answer
    majority = {}
    for q in ("Q6_coordination", "Q8_compare"):
        c = Counter(json.dumps(t["gold"], sort_keys=True) for t in tasks.values() if t["qtype"] == q)
        majority[q] = json.loads(c.most_common(1)[0][0])
    rows = {}
    groups = defaultdict(list)
    for x in scored:
        groups[(x["model"], x["channel"])].append((tasks[x["task_id"]], x["score"]))
    for k, v in groups.items():
        rows[k] = summarize(v)
    rows[("baseline", "no-problem/majority")] = summarize(
        [(t, score_answer(t, no_problem_answer(t, majority))[0]) for t in tasks.values()])
    rp = run_dir(args.random_run) / "scored.jsonl"
    if rp.exists():
        rnd = [x for x in load_jsonl(rp) if x["model"] == "mock-random" and x["task_id"] in tasks]
        rows[("baseline", "random")] = summarize([(tasks[x["task_id"]], x["score"]) for x in rnd])
    det = {k: detection([x for x in scored if (x["model"], x["channel"]) == k], tasks) for k in groups}

    # ---------------- CSV
    cols = ["model", "channel", "n", "mean", "macro_balanced", "problem_subset", "problem_subset_n"]
    for q in FAMILIES:
        cols += [q, f"{q}_balanced"] + ([f"{q}_problem", f"{q}_clean"] if q in FLAGGED else [])
    with (out / "results.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for (m, c), r in sorted(rows.items(), key=lambda kv: (kv[0][0] == "baseline", kv[0][0], CHANNEL_ORDER.index(kv[0][1]) if kv[0][1] in CHANNEL_ORDER else 9)):
            w.writerow([m, c] + [round(r.get(k), 4) if isinstance(r.get(k), float) else r.get(k) for k in cols[2:]])
    with (out / "detection.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["model", "channel", "family", "sensitivity", "specificity", "tp", "fn", "tn", "fp"])
        for (m, c), d in sorted(det.items()):
            for q, v in d.items():
                w.writerow([m, c, q, round(v["sens"], 3), round(v["spec"], 3), v["tp"], v["fn"], v["tn"], v["fp"]])
    (out / "results.json").write_text(json.dumps({f"{m}|{c}": r for (m, c), r in rows.items()}, indent=1), encoding="utf-8")

    # ---------------- failure cases
    by_key = {(x["model"], x["channel"], x["task_id"]): x for x in scored}
    cases = []
    def pick(model, channel, pred_fn, n=2):
        got = []
        for x in scored:
            if x["model"] == model and x["channel"] == channel and pred_fn(x, tasks[x["task_id"]]):
                got.append(x)
        return got[:n]
    cases += [("TUI misses disorder that the CIF text reveals", x) for x in pick(
        "deepseek-v4-flash", "tui", lambda x, t: t["qtype"] == "Q4_disorder" and t["gold"]["disordered"] and x["score"] < 0.34
        and by_key.get((x["model"], "cif", x["task_id"]), {}).get("score", 0) > 0.6)]
    cases += [("Image: wrong coordination number", x) for x in pick(
        "gemini-2.5-flash", "image", lambda x, t: t["qtype"] == "Q6_coordination" and isinstance(x.get("answer"), dict)
        and x["answer"].get("cn") != t["gold"]["cn"])]
    cases += [("Image/TUI: false alarm on missing H", x) for x in pick(
        "gemini-2.5-flash", "tui", lambda x, t: t["qtype"] == "Q3_hydrogen" and not t["gold"]["missing_h"] and x["score"] == 0, 1)]
    cases += [("Comparison answered wrongly from pictures", x) for x in pick(
        "gemini-2.5-flash", "image", lambda x, t: t["qtype"] == "Q8_compare" and x["score"] == 0, 1)]
    (out / "failure_cases.json").write_text(json.dumps([{"title": a, **{k: x[k] for k in ("model", "channel", "task_id", "answer", "gold", "score")}} for a, x in cases], indent=1), encoding="utf-8")

    # ---------------- markdown
    def f(v):
        return "-" if v is None or (isinstance(v, float) and v != v) else f"{v:.3f}"
    order = sorted(rows, key=lambda k: (k[0] == "baseline", k[1] == "tools", -rows[k]["macro_balanced"]))
    L = [f"# CrystalSight results ({args.run})", "",
         f"Tasks: {len(tasks)} questions ({', '.join(f'{q} {sum(t['qtype']==q for t in tasks.values())}' for q in FAMILIES)}); "
         f"{len({t['structure_id'] for t in tasks.values() if '|' not in t['structure_id']})} structures. Scores are partial-credit means in [0, 1] (see crystalsight/score.py).",
         "", "**Balanced** = per family, the mean of the score on structures that have the problem and on those that do not "
         "(Q3 missing H, Q4 disordered, Q7 not usable); Q6/Q8 use the plain mean. **Macro** = average over the 5 families. "
         "**Problem subset** = mean score on the flagged-problem questions only (Q3/Q4/Q7, n=" + str(rows[order[0]]["problem_subset_n"]) + ").",
         "", "## Leaderboard", "", "| model | channel | mean | macro balanced | problem subset | " + " | ".join(q.split("_")[0] for q in FAMILIES) + " |",
         "|---|---|---|---|---|" + "---|" * len(FAMILIES)]
    for k in order:
        r = rows[k]
        tag = " (reference upper bound)" if k[1] == "tools" else " (leakage control)" if k[1] == "cif_raw" else ""
        L.append(f"| {k[0]} | {k[1]}{tag} | {f(r['mean'])} | {f(r['macro_balanced'])} | {f(r['problem_subset'])} | "
                 + " | ".join(f(r.get(f'{q}_balanced')) for q in FAMILIES) + " |")
    L += ["", "Per-family columns show the balanced score.", "", "## Problem vs clean subsets (Q3 / Q4 / Q7)", "",
          "| model | channel | " + " | ".join(f"{q.split('_')[0]} problem | {q.split('_')[0]} clean" for q in FLAGGED) + " |",
          "|---|---|" + "---|---|" * len(FLAGGED)]
    for k in order:
        r = rows[k]
        L.append(f"| {k[0]} | {k[1]} | " + " | ".join(f"{f(r.get(q + '_problem'))} | {f(r.get(q + '_clean'))}" for q in FLAGGED) + " |")
    L += ["", "## Detection of the problem flag (sensitivity / specificity)", "", "| model | channel | " + " | ".join(FLAGGED) + " |", "|---|---|" + "---|" * len(FLAGGED)]
    for k in sorted(det, key=lambda k: (k[1] == "tools", k)):
        L.append(f"| {k[0]} | {k[1]} | " + " | ".join(f"{det[k][q]['sens']:.2f} / {det[k][q]['spec']:.2f}" for q in FLAGGED) + " |")
    L += ["", "## Leakage control: stripped CIF (cif) vs raw CIF (cif_raw)", "", "| model | " + " | ".join(q.split("_")[0] for q in FAMILIES) + " | mean | macro |", "|---|" + "---|" * (len(FAMILIES) + 2)]
    for m in sorted({k[0] for k in rows if k[0] != "baseline"}):
        a, b = rows.get((m, "cif")), rows.get((m, "cif_raw"))
        if a and b:
            L.append(f"| {m} (raw - stripped) | " + " | ".join(f"{b[q] - a[q]:+.3f}" for q in FAMILIES) + f" | {b['mean'] - a['mean']:+.3f} | {b['macro_balanced'] - a['macro_balanced']:+.3f} |")
    L += ["", "## Illustrative failure cases", ""]
    for title, x in cases:
        t = tasks[x["task_id"]]
        L.append(f"- **{title}** - {x['model']} / {x['channel']} on `{x['task_id']}`: answered `{json.dumps(x['answer'])}`, gold `{json.dumps(x['gold'])}` (score {x['score']:.2f}).")
    L += ["", f"Baselines: *no-problem/majority* answers 'no missing H', 'not disordered', 'usable' for Q3/Q4/Q7 and the majority "
          f"gold for Q6 ({json.dumps(majority['Q6_coordination'])}) and Q8 ({json.dumps(majority['Q8_compare'])}); *random* is a seeded "
          "type-correct random answer (mock-random, averaged over channels).", ""]
    (out / "results.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
