"""Run models x channels x tasks; write one JSON record per attempt."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from .channels import CHANNELS
from .models import load_models
from .paths import RUNS, TASKS


def load_tasks(path: Path, qtypes: list[str] | None, limit: int, structures: list[str] | None) -> list[dict]:
    tasks = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if qtypes:
        tasks = [t for t in tasks if t["qtype"] in qtypes]
    if structures:  # pair tasks are kept when both members are listed
        keep = set(structures)
        tasks = [t for t in tasks if t["structure_id"] in keep
                 or (t.get("structures") and all(x["structure_id"] in keep for x in t["structures"]))]
    if limit:
        tasks = tasks[:limit]
    return tasks


def run_one(model, channel_name: str, task: dict) -> dict:
    ch = CHANNELS[channel_name]()
    t0 = time.monotonic()
    base = {"model": model.name, "channel": channel_name, "task_id": task["id"], "qtype": task["qtype"],
            "structure_id": task["structure_id"]}
    try:
        rec = ch.run(task, model)
    except Exception as exc:  # noqa: BLE001 - infra error is a record, not a crash
        rec = {"channel": channel_name, "answer": None, "error": f"{type(exc).__name__}: {exc}",
               "traceback": traceback.format_exc()[-1500:]}
    rec.update(base)
    rec["wall_s"] = round(time.monotonic() - t0, 2)
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["mock-random"])
    ap.add_argument("--channels", nargs="+", default=["cif", "image", "tui", "tools"])
    ap.add_argument("--tasks", default=str(TASKS / "tasks.jsonl"))
    ap.add_argument("--qtypes", nargs="*")
    ap.add_argument("--structures", nargs="*")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--resume", action="store_true", help="skip (model,channel,task) already in records.jsonl")
    ap.add_argument("--max-tokens", type=int, default=0, help="override max_output_tokens for every model (recorded in run_meta)")
    ap.add_argument("--timeout", type=float, default=0, help="override per-request timeout_s for every model (recorded in run_meta)")
    args = ap.parse_args()

    tasks = load_tasks(Path(args.tasks), args.qtypes, args.limit, args.structures)
    models = load_models(args.models)
    overrides = {}
    for m in models:
        if args.max_tokens and hasattr(m, "max_tokens"):
            m.max_tokens = args.max_tokens
            overrides.setdefault("max_tokens", args.max_tokens)
        if args.timeout and hasattr(m, "timeout"):
            m.timeout = args.timeout
            overrides.setdefault("timeout_s", args.timeout)
    run_id = args.run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = RUNS / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    rec_path = out_dir / "records.jsonl"
    done = set()
    if args.resume and rec_path.exists():
        for l in rec_path.read_text(encoding="utf-8").splitlines():
            r = json.loads(l)
            if not r.get("error"):
                done.add((r["model"], r["channel"], r["task_id"]))
    jobs = []
    for m in models:
        for c in args.channels:
            if CHANNELS[c]().needs_vision and not m.supports_vision:
                print(f"skip {m.name}/{c}: model has no vision")
                continue
            for t in tasks:
                if (m.name, c, t["id"]) not in done:
                    jobs.append((m, c, t))
    meta = {"run_id": run_id, "started_utc": datetime.now(timezone.utc).isoformat(), "models": [m.name for m in models],
            "channels": args.channels, "n_tasks": len(tasks), "n_jobs": len(jobs),
            "tasks_sha256": hashlib.sha256(Path(args.tasks).read_bytes()).hexdigest()}
    if overrides:
        meta["overrides"] = overrides
        meta["notes"] = [f"Command-line override for every model in this run: {overrides} (models.toml values not used)."]
    meta_path = out_dir / "run_meta.json"
    if args.resume and meta_path.exists():  # multi-pass runs: keep the union of channels/models
        old = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["channels"] = list(dict.fromkeys(old.get("channels", []) + meta["channels"]))
        meta["models"] = list(dict.fromkeys(old.get("models", []) + meta["models"]))
        meta["started_utc"] = old.get("started_utc", meta["started_utc"])
        for k in ("overrides", "notes"):
            if k in old and k not in meta:
                meta[k] = old[k]
    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"run {run_id}: {len(jobs)} jobs", flush=True)
    n_err = 0
    with rec_path.open("a", encoding="utf-8") as f, ThreadPoolExecutor(args.workers) as ex:
        # as_completed (not ex.map): one slow job must not hold back writing the others
        futs = [ex.submit(run_one, *j) for j in jobs]
        for i, fut in enumerate(as_completed(futs), 1):
            rec = fut.result()
            n_err += bool(rec.get("error"))
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if i % 10 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} done, errors={n_err}", flush=True)
    meta["finished_utc"] = datetime.now(timezone.utc).isoformat()
    meta["n_errors"] = n_err
    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"records -> {rec_path}")


if __name__ == "__main__":
    main()