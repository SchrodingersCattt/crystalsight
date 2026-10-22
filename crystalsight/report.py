"""Static HTML report: leaderboard, per-question-type matrix, trajectory replays."""

from __future__ import annotations

import argparse
import html
import json
import os
from collections import defaultdict
from pathlib import Path

from .paths import REPORTS, ROOT, RUNS, TASKS

CSS = """
body{font-family:system-ui,Segoe UI,sans-serif;margin:24px;max-width:1400px;color:#222}
h1{margin-bottom:0}.sub{color:#666;margin-top:4px}
table{border-collapse:collapse;margin:12px 0}td,th{border:1px solid #ccc;padding:4px 8px;text-align:right}
th{background:#f3f3f3}td.l,th.l{text-align:left}
.acc{font-variant-numeric:tabular-nums}
.case{border:1px solid #ddd;border-radius:6px;padding:10px;margin:16px 0}
.ch{display:inline-block;vertical-align:top;width:48%;margin:4px;border-top:3px solid #888;padding-top:4px}
pre{font-size:9px;line-height:1.0;background:#111;color:#ddd;padding:6px;overflow:auto;max-height:420px}
img{width:200px;border:1px solid #ccc;margin:2px}
.ok{color:#0a7d22;font-weight:600}.bad{color:#b00020;font-weight:600}
.warn{background:#fff6d6;border:1px solid #e6c200;padding:6px 10px;border-radius:4px}
"""


def _color(acc: float) -> str:
    g = int(80 + 150 * acc)
    r = int(230 - 150 * acc)
    return f"background:rgb({r},{g},120)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--cases", type=int, default=4, help="number of structures to replay")
    ap.add_argument("--tasks", default=str(TASKS / "tasks.jsonl"))
    args = ap.parse_args()
    run_dir = RUNS / args.run_id
    out_dir = REPORTS / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    rows = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    tasks = {t["id"]: t for t in (json.loads(l) for l in Path(args.tasks).read_text(encoding="utf-8").splitlines() if l.strip())}
    records = {}
    for l in (run_dir / "records.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            records[(r["model"], r["channel"], r["task_id"])] = r
    scored = {(x["model"], x["channel"], x["task_id"]): x for x in
              (json.loads(l) for l in (run_dir / "scored.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}

    qtypes = sorted({r["qtype"] for r in rows if r["qtype"] != "ALL"})
    pivot = defaultdict(dict)
    for r in rows:
        pivot[(r["model"], r["channel"])][r["qtype"]] = r
    rel_root = os.path.relpath(ROOT, out_dir).replace("\\", "/")

    h = [f"<!doctype html><meta charset='utf-8'><title>CrystalSight {html.escape(args.run_id)}</title><style>{CSS}</style>"]
    h.append("<h1>CrystalSight</h1><div class='sub'>Which input modality lets LLMs read crystal structures best? CIF text vs rendered images vs interactive ASCII; MolCrysKit tools as a reference upper bound. "
             "Gold answers are MolCrysKit outputs; accuracy = agreement with MolCrysKit.</div>")
    h.append(f"<p>Run <b>{html.escape(args.run_id)}</b> &middot; models: {html.escape(', '.join(meta['models']))} &middot; "
             f"channels: {html.escape(', '.join(meta['channels']))} &middot; tasks: {meta['n_tasks']} &middot; "
             f"tasks sha256 {meta['tasks_sha256'][:12]}</p>")
    if any(m.startswith("mock") for m in meta["models"]):
        h.append("<p class='warn'>This run includes <b>mock</b> models (pipeline test). mock-oracle reads the gold answer "
                 "and must score 1.0; mock-random is a chance-level floor. Neither is a benchmark result.</p>")
    def table(title, note, keep):
        h.append(f"<h2>{title}</h2><p class='sub'>{note}</p><table><tr><th class='l'>model</th><th class='l'>channel</th><th>overall</th>"
                 + "".join(f"<th>{q}</th>" for q in qtypes) + "<th>infra err</th><th>unparseable</th></tr>")
        for (m, c), d in sorted(pivot.items(), key=lambda kv: -kv[1].get("ALL", {}).get("accuracy", 0)):
            if not keep(c):
                continue
            a = d.get("ALL", {})
            label = c + (" <small>(leakage control)</small>" if c == "cif_raw" else "")
            h.append(f"<tr><td class='l'>{html.escape(m)}</td><td class='l'>{label}</td>"
                     f"<td class='acc' style='{_color(a.get('accuracy', 0))}'>{a.get('accuracy', 0):.3f} <small>(n={a.get('n', 0)})</small></td>")
            for q in qtypes:
                x = d.get(q)
                h.append(f"<td class='acc' style='{_color(x['accuracy'])}'>{x['accuracy']:.2f} <small>({x['n']})</small></td>" if x else "<td>-</td>")
            h.append(f"<td>{a.get('infra_errors', 0)}</td><td>{a.get('unparseable', 0)}</td></tr>")
        h.append("</table>")

    table("Main leaderboard (input modalities)",
          "Mean partial-credit score per question family (see score.py). cif = CIF text with answer-stating metadata "
          "stripped; image = 3 rendered views; tui = interactive ASCII viewer. cif_raw (unstripped CIF) is a leakage control.",
          lambda c: c != "tools")
    table("Reference upper bound: MolCrysKit tools",
          "Not part of the leaderboard: several tools run the same computations that produce the gold answers, so this "
          "measures tool use and reading, not perception.", lambda c: c == "tools")

    by_struct = defaultdict(list)
    for t in tasks.values():
        by_struct[t["structure_id"]].append(t)
    present = {k[2] for k in records}
    chosen = [s for s, ts in sorted(by_struct.items(), key=lambda kv: -len(kv[1])) if any(t["id"] in present for t in ts)][: args.cases]
    h.append("<h2>Replays</h2>")
    for sid in chosen:
        t = next(t for t in sorted(by_struct[sid], key=lambda t: t["qtype"]) if t["id"] in present)
        h.append(f"<div class='case'><h3>{html.escape(sid)} &mdash; {t['qtype']}</h3>"
                 f"<p>{html.escape(t['question'])}<br>gold (MolCrysKit): <code>{html.escape(json.dumps(t['gold']))}</code></p>")
        for (m, c, tid), r in sorted(records.items()):
            if tid != t["id"]:
                continue
            s = scored.get((m, c, tid), {})
            cls = "ok" if s.get("score", 0) >= 0.999 else "bad"
            h.append(f"<div class='ch'><b>{html.escape(m)} / {c}</b> &rarr; answer <code>{html.escape(json.dumps(r.get('answer')))}</code> "
                     f"<span class='{cls}'>score {s.get('score', 0):.2f}</span> &middot; steps {r.get('steps', 0)}")
            if r.get("error"):
                h.append(f"<div class='bad'>error: {html.escape(str(r['error'])[:300])}</div>")
            if c == "image":
                for v in r.get("views", []):
                    h.append(f"<img src='{rel_root}/{v['path']}' title='{v.get('label', '')} view along {v['axis']}'>")
            if c == "tui":
                acts = ", ".join(f"{a.get('action')}{'' if a.get('ok') else '(x)'}" for a in r.get("actions", []))
                h.append(f"<div>actions: {html.escape(acts) or '(none)'}</div>")
                for fr in r.get("frames", [])[-2:]:
                    h.append(f"<pre>{html.escape(fr)}</pre>")
            if c == "tools":
                for tc in r.get("tool_calls", []):
                    h.append(f"<div><code>{html.escape(str(tc.get('tool')))}({html.escape(json.dumps(tc.get('arguments')))})</code> &rarr; {tc.get('result_chars')} chars</div>")
            if c.startswith("cif"):
                h.append(f"<div>CIF text {r.get('input_chars', 0)} chars{' (truncated)' if r.get('truncated') else ''}</div>")
            h.append("</div>")
        h.append("</div>")
    (out_dir / "index.html").write_text("\n".join(h), encoding="utf-8")
    print(f"report -> {out_dir / 'index.html'}")


if __name__ == "__main__":
    main()