"""Recompute Q6 metal shells from MolCrysKit bonds for every GT file that contains a metal."""
import json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, ".")
from crystalsight.paths import DATA, ROOT, SUBPROCESS_ENV
from crystalsight.gt import METALS

def one(f):
    g = json.loads(f.read_text(encoding="utf-8"))
    els = {e for c in g.get("components") or [] for e in c.get("elements", [])}
    if "error" in g or not (els & METALS):
        return f.stem, "skip"
    p = subprocess.Popen([sys.executable, "-m", "crystalsight.gt", str(ROOT / g["path"]), "--metals-only"], cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", env=SUBPROCESS_ENV)
    try:
        so, se = p.communicate(timeout=300)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
        return f.stem, "timeout (kept covalent-radius shell)"
    lines = [l for l in so.splitlines() if l.startswith("{")]
    if not lines:
        return f.stem, "error " + se[-200:]
    g["metals_covalent"] = g.get("metals")
    g["metals"] = json.loads(lines[-1])["metals"]
    f.write_text(json.dumps(g, indent=1), encoding="utf-8")
    return f.stem, json.dumps({k: (v.get("cn"), v.get("geometry"), round(v["cshm"], 2) if v.get("cshm") is not None else None) for k, v in g["metals"].items()})

with ThreadPoolExecutor(6) as ex:
    for sid, msg in ex.map(one, sorted((DATA / "gt").glob("*.json"))):
        if msg != "skip":
            print(sid, msg, flush=True)
print("METALS_DONE")
