"""Tiny real-API smoke test: one text call and one image call per model.

Prints only model name, status, latency, token usage and the parsed reply;
never prints keys or base URLs.
"""

from __future__ import annotations

import argparse
import base64
import json

from .models import extract_json, load_models
from .paths import DATA


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["deepseek-v4-flash", "gpt-4o-2024-08-06"])
    ap.add_argument("--image", default=None, help="PNG to use for the vision probe")
    args = ap.parse_args()
    out = {}
    for m in load_models(args.models):
        res = {}
        r = m.complete([{"role": "user", "content": 'Reply with exactly this JSON and nothing else: {"answer": 42}'}])
        res["text"] = {"ok": r.error is None and (extract_json(r.text) or {}).get("answer") == 42,
                       "error": r.error, "latency_ms": round(r.latency_ms), "usage": r.usage,
                       "reply": (r.text or "")[:120]}
        png = args.image or next(iter(sorted((DATA / "renders").glob("*.png"))), None)
        if png and not m.supports_vision:
            res["image"] = {"ok": None, "skipped": "vision=false in models.toml"}
        elif png:
            b64 = base64.b64encode(open(png, "rb").read()).decode()
            r = m.complete([{"role": "user", "content": [
                {"type": "text", "text": 'This is a ball-and-stick render of a crystal. Reply only JSON {"answer": <number of distinct atom colours you see>}.'},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}])
            res["image"] = {"ok": r.error is None and isinstance((extract_json(r.text) or {}).get("answer"), (int, float)),
                            "error": r.error, "latency_ms": round(r.latency_ms), "usage": r.usage,
                            "reply": (r.text or "")[:160]}
        out[m.name] = res
        print(m.name, json.dumps(res, ensure_ascii=False), flush=True)
    (DATA.parent / "_scratch").mkdir(exist_ok=True)
    (DATA.parent / "_scratch" / "smoke_result.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()