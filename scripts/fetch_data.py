"""Fetch the public CrystalSight structure set.

Sources (public / open where noted):
  * COD (Crystallography Open Database, CC0-like open data): a fixed seed list
    (the 14 IDs used in MatterVis cod_test) plus a reproducible random sample
    of IDs from the 2xxxxxx (IUCr Acta Cryst.) range, which is dominated by
    small-molecule / molecular crystals.
  * A subset of MolCrysKit `examples/` that are safe to redistribute (MIT /
    non-CSD). Many other MolCrysKit example CIFs are CSD/CCDC downloads and
    must NOT be fetched or committed; see data/structures/README.md.

No CSD/CCDC crystal data is redistributed. No data from any unpublished
benchmark is used.
Stdlib only, so it can run before the venv is ready.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "structures"
MANIFEST = ROOT / "data" / "manifest.json"

COD_SEED = [
    "1000022", "1000043", "1008775", "1011185", "1501794", "1530150", "2013196",
    "2013465", "4002052", "4501702", "9000629", "9001364", "9002348", "9008789",
]
MCK_RAW = "https://raw.githubusercontent.com/SchrodingersCattt/MolCrysKit/main/examples/"
MCK_EXAMPLES = [
    # Non-CSD / redistributable MolCrysKit examples only (see data/structures/README.md).
    "anhydrousCaffeine2_CGD_2007_7_1406.cif",
    "anhydrousCaffeine_CGD_2007_7_1406.cif",
    "MAP_H.cif", "NaCl.cif", "Diamond.cif", "DAP-4_order.cif", "368K.cif",
]
UA = {"User-Agent": "CrystalSight/0.1 (OSI hackathon 2026; research use)"}


def get(url: str, timeout: float = 45.0, retries: int = 3) -> bytes | None:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as exc:  # noqa: BLE001 - record and retry
            status = getattr(exc, "code", None)
            if status == 404:
                return None
            time.sleep(2 * (attempt + 1))
    return None


def looks_molecular(text: str, max_cell_volume: float = 3000.0) -> bool:
    if "_atom_site_fract_x" not in text and "_atom_site_Cartn_x" not in text:
        return False
    m = re.search(r"^_chemical_formula_sum\s+'?([^'\n]+)'?", text, re.M)
    if not m or not re.search(r"\bC\d*\b", m.group(1)) or not re.search(r"\bH[\d.]*\b", m.group(1)):
        return False
    v = re.search(r"^_cell_volume\s+([\d.]+)", text, re.M)
    if not v or float(v.group(1)) > max_cell_volume:
        return False
    return True


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-random", type=int, default=40, help="target accepted random COD structures")
    ap.add_argument("--max-tries", type=int, default=120)
    ap.add_argument("--seed", type=int, default=20261021)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {"structures": {}, "rejected": {}}
    S, R = manifest["structures"], manifest["rejected"]

    def store(sid: str, source: str, url: str, blob: bytes, sub: str) -> None:
        path = DATA / sub / f"{sid}.cif"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        S[sid] = {"source": source, "url": url, "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                  "sha256": sha(blob), "bytes": len(blob)}

    for name in MCK_EXAMPLES:
        sid = "mck_" + Path(name).stem
        if sid in S:
            continue
        url = MCK_RAW + name
        blob = get(url)
        if blob:
            store(sid, "MolCrysKit non-CSD examples (MIT)", url, blob, "mck")
            print("ok", sid, flush=True)
        else:
            R[sid] = "download failed"

    for cid in COD_SEED:
        sid = "cod_" + cid
        if sid in S:
            continue
        url = f"https://www.crystallography.net/cod/{cid}.cif"
        blob = get(url)
        if blob:
            store(sid, "COD seed (MatterVis cod_test list)", url, blob, "cod")
            print("ok", sid, flush=True)
        else:
            R[sid] = "download failed"
        MANIFEST.write_text(json.dumps(manifest, indent=1), encoding="utf-8")

    # Fallback for seed IDs COD did not serve in time: the identical public COD
    # files from a local directory of COD CIFs (e.g. a MatterVis checkout's cod_test/),
    # given via the optional CRYSTALSIGHT_LOCAL_COD environment variable.
    local_cod = Path(os.environ.get("CRYSTALSIGHT_LOCAL_COD", "__none__"))
    for cid in COD_SEED:
        sid = "cod_" + cid
        if sid in S or not (local_cod / f"{cid}.cif").exists():
            continue
        blob = (local_cod / f"{cid}.cif").read_bytes()
        store(sid, "COD seed (local copy of MatterVis cod_test; COD timed out)",
              f"https://www.crystallography.net/cod/{cid}.cif", blob, "cod")
        R.pop(sid, None)
        print("ok(local)", sid, flush=True)

    from concurrent.futures import ThreadPoolExecutor, as_completed

    rng = random.Random(args.seed)
    candidates = []
    seen = set(S) | set(R)
    while len(candidates) < args.max_tries:
        cid = str(rng.randint(2000000, 2242000))
        if "cod_" + cid not in seen:
            seen.add("cod_" + cid)
            candidates.append(cid)
    accepted = sum(1 for k, v in S.items() if v["source"].startswith("COD random"))

    def probe(cid: str):
        url = f"https://www.crystallography.net/cod/{cid}.cif"
        return cid, url, get(url, timeout=60, retries=2)

    with ThreadPoolExecutor(args.workers) as ex:
        futs = [ex.submit(probe, c) for c in candidates]
        for fut in as_completed(futs):
            cid, url, blob = fut.result()
            sid = "cod_" + cid
            if accepted >= args.n_random:
                continue
            if not blob:
                R[sid] = "missing/timeout"
                continue
            if not looks_molecular(blob.decode("utf-8", "replace")):
                R[sid] = "filtered (not organic/molecular or cell > 3000 A^3)"
                continue
            store(sid, f"COD random sample seed={args.seed}", url, blob, "cod")
            accepted += 1
            print("ok", sid, accepted, flush=True)
            MANIFEST.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    tries = len(candidates)
    MANIFEST.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"structures={len(S)} rejected={len(R)} random_accepted={accepted} tries={tries}")


if __name__ == "__main__":
    main()
