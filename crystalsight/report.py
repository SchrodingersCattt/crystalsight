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
body{font-family:Arial,Helvetica,sans-serif;margin:32px auto;max-width:1280px;padding:0 24px;color:#1F2328;background:#fff;line-height:1.45}
h1{font-size:26px;margin:0 0 4px 0;font-weight:700}h2{font-size:18px;margin:28px 0 6px 0;font-weight:700}
.sub{color:#6E7781;margin-top:4px;font-size:14px}
.headline{border:1px solid #D0D7DE;border-left:4px solid #2F6FEB;border-radius:8px;padding:14px 18px;margin:18px 0;font-size:17px}
table{border-collapse:separate;border-spacing:0;margin:12px 0;border:1px solid #D0D7DE;border-radius:8px;overflow:hidden;font-size:13px}
td,th{border-bottom:1px solid #EAEEF2;padding:6px 10px;text-align:right}
th{background:#F6F8FA;color:#57606A;font-weight:600}td.l,th.l{text-align:left}
.acc{font-variant-numeric:tabular-nums}
.case{border:1px solid #D0D7DE;border-radius:8px;padding:14px;margin:18px 0}
.ch{display:inline-block;vertical-align:top;width:48%;margin:4px;border-top:2px solid #D0D7DE;padding-top:6px}
pre{font-size:9px;line-height:1.05;background:#F6F8FA;color:#1F2328;border:1px solid #D0D7DE;border-radius:6px;padding:8px;overflow:auto;max-height:420px}
img{width:200px;border:1px solid #D0D7DE;border-radius:4px;margin:2px}
.ok{color:#1A7F37;font-weight:600}.bad{color:#CF222E;font-weight:600}
.warn{background:#F6F8FA;border:1px solid #D0D7DE;padding:8px 12px;border-radius:6px;color:#57606A;font-size:13px}
"""


def _color(acc: float) -> str:
    """White -> light blue -> accent blue (Cursor-light palette); text turns white on dark cells."""
    acc = max(0.0, min(1.0, acc))
    r, g, b = (int(255 + (47 - 255) * acc), int(255 + (111 - 255) * acc), int(255 + (235 - 255) * acc))
    return f"background:rgb({r},{g},{b});color:{'#fff' if acc > 0.65 else '#1F2328'}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--cases", type=int, default=4, help="number of structures to replay")
    ap.add_argument("--tasks", default=str(TASKS / "tasks.jsonl"))
    ap.add_argument("--headline", default="", help="one-sentence key finding shown at the top")
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
    has_strict = any("strict_accuracy" in r for r in rows)
    pivot = defaultdict(dict)
    for r in rows:
        pivot[(r["model"], r["channel"])][r["qtype"]] = r
    rel_root = os.path.relpath(ROOT, out_dir).replace("\\", "/")

    h = [f"<!doctype html><meta charset='utf-8'><title>CrystalSight {html.escape(args.run_id)}</title><style>{CSS}</style>"]
    spatial = any(t.get("benchmark") in ("v3", "v4") for t in tasks.values())
    if spatial:
        h.append("<h1>CrystalSight: spatial questions</h1><div class='sub'>The same 3D question about the same crystal "
                 "structure, shown as CIF text, rendered images, an interactive ASCII 3D viewer, or with geometry tools. "
                 "Gold answers are computed from geometry and must survive a 5% perturbation of every cutoff.</div>")
    else:
        h.append("<h1>CrystalSight</h1><div class='sub'>Which input modality lets LLMs read crystal structures best? CIF text vs rendered images vs interactive ASCII; MolCrysKit tools as a reference upper bound. "
                 "Gold answers are MolCrysKit outputs; accuracy = agreement with MolCrysKit.</div>")
    if args.headline:
        h.append(f"<div class='headline'>{html.escape(args.headline)}</div>")
    h.append(f"<p>Run <b>{html.escape(args.run_id)}</b> &middot; models: {html.escape(', '.join(meta['models']))} &middot; "
             f"channels: {html.escape(', '.join(meta['channels']))} &middot; tasks: {meta['n_tasks']} &middot; "
             f"tasks sha256 {meta['tasks_sha256'][:12]}</p>")
    for note in meta.get("notes", []):  # run-level setting changes (e.g. approved per-job overrides)
        h.append(f"<p class='warn'>Note: {html.escape(note)}</p>")
    if any(m.startswith("mock") for m in meta["models"]):
        h.append("<p class='warn'>This run includes <b>mock</b> models (pipeline test). mock-oracle reads the gold answer "
                 "and must score 1.0; mock-random is a chance-level floor. Neither is a benchmark result.</p>")
    def table(title, note, keep):
        h.append(f"<h2>{title}</h2><p class='sub'>{note}</p><table><tr><th class='l'>model</th><th class='l'>channel</th><th>overall</th>"
                 + "".join(f"<th>{q}</th>" for q in qtypes) + ("<th>strict</th>" if has_strict else "") + "<th>infra err</th><th>unparseable</th></tr>")
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
            if has_strict:
                h.append(f"<td class='acc'>{a.get('strict_accuracy', 0):.3f}</td>")
            h.append(f"<td>{a.get('infra_errors', 0)}</td><td>{a.get('unparseable', 0)}</td></tr>")
        h.append("</table>")

    table("Main leaderboard (input modalities)",
          "Mean partial-credit score per question family (see score.py). cif = CIF text with answer-stating metadata "
          "stripped; image = 3 rendered views; tui = interactive ASCII viewer. cif_raw (unstripped CIF) is a leakage control.",
          lambda c: c != "tools")
    if spatial:
        table("Tool access: geometry tools",
              "MolCrysKit tools plus small geometry tools built for this benchmark (H-bond list, nearest atoms, H-bond path "
              "and ring, neighbour shells, disorder components). They return raw lists; the model still has to count and "
              "interpret them.", lambda c: c == "tools")
    else:
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