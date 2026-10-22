"""CrystalSight task generator (v2): questions a crystallographer asks when judging a CIF.

Families (ground truth: MolCrysKit + documented rules in crystalsight/gt.py):
  Q3_hydrogen     are H atoms missing; on which elements                  -> object
  Q4_disorder     is there disorder; on which component; which type       -> object
  Q6_coordination metal CN and coordination geometry (metal structures)   -> object
  Q7_usability    usable directly for DFT/MD; blocking issues (from Q3/Q4/components) -> object
  Q8_compare      two similar structures: which contains solvent / is disordered -> choice A|B|both|neither

Stage 1 (--stage gt) computes data/gt/<sid>.json per structure in child processes with a
timeout; stage 2 (--stage tasks) builds tasks/tasks.jsonl from those files. Default: both.
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .paths import DATA, ROOT, SUBPROCESS_ENV, TASKS

GT_DIR = DATA / "gt"
GT_TIMEOUT_S = 480
ROLES = ["main", "solvent", "counterion", "other_component"]
DIS_TYPES = ["alternative_positions", "partial_occupancy"]
ISSUES = ["disorder", "missing_hydrogen", "solvent_present"]
GEOMETRY_MAX_CSHM = 3.0  # Q6 only when the best CShM fit is unambiguous (<= 3: clean / slightly distorted)
ELEMENT_HINT = "element symbols, e.g. [\"C\", \"N\"]"

ROLE_DEF = ("Component roles: main = the largest molecule, complex or framework; solvent = lattice solvent "
            "(water, methanol, DMF, ...); counterion = a separate charge-balancing ion (e.g. ClO4-, NO3-, Cl-, Na+); "
            "other_component = any other separate species (co-former, second neutral molecule).")


def _kill_tree(p: subprocess.Popen) -> None:
    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)


def compute_gt(sid: str, path: str, force: bool = False) -> dict:
    out = GT_DIR / f"{sid}.json"
    if out.exists() and not force:
        return json.loads(out.read_text(encoding="utf-8"))
    p = subprocess.Popen([sys.executable, "-m", "crystalsight.gt", str(ROOT / path)], cwd=ROOT, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", env=SUBPROCESS_ENV)
    try:
        so, se = p.communicate(timeout=GT_TIMEOUT_S)
        lines = [l for l in so.splitlines() if l.startswith("{")]
        res = json.loads(lines[-1]) if p.returncode == 0 and lines else {"error": (se or "")[-400:]}
    except subprocess.TimeoutExpired:
        _kill_tree(p)
        res = {"error": f"timeout after {GT_TIMEOUT_S}s"}
    res["structure_id"], res["path"] = sid, path
    GT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def _obj(task_fields: dict) -> dict:
    return task_fields


def single_tasks(g: dict, source: str) -> list[dict]:
    sid, path = g["structure_id"], g["path"]
    base = {"structure_id": sid, "path": path, "source": source}
    tasks = []

    def add(qtype, question, schema, gold, evidence):
        tasks.append({**base, "id": f"{sid}:{qtype}", "qtype": qtype, "question": question, "answer_type": "object",
                      "schema": schema, "gold": gold, "evidence": evidence})

    H, D, comps = dict(g.get("hydrogen") or {}), g.get("disorder") or {}, g.get("components") or []
    h_ok = "missing_h" in H
    if h_ok:
        # H "added" to a metal centre is a placement artefact, not a missing H: drop those and re-apply the rule.
        by_el = {e: k for e, k in (H.get("added_by_element") or {}).items() if e not in METALS}
        eff = sum(by_el.values())
        before = H.get("n_before") or 0
        missing = eff > 0 and (before == 0 or eff / (before + eff) >= MISSING_H_FRACTION)
        H.update({"added_by_element": by_el, "n_added": eff, "missing_h": bool(missing),
                  "elements": sorted(e for e, k in by_el.items() if missing and k >= 0.1 * eff)})
    if h_ok:
        add("Q3_hydrogen",
            "Judge the hydrogen atoms in this structural model. Are hydrogen atoms missing (i.e. heavy atoms that "
            "should carry H but have none modelled)? If yes, on atoms of which element(s) are they missing?",
            {"missing_h": {"type": "bool"}, "elements": {"type": "set", "hint": ELEMENT_HINT + "; empty list if none missing"}},
            {"missing_h": H["missing_h"], "elements": H["elements"]},
            {"rule": "mck add_hydrogens; missing if added >= 5% of completed H count or model has no H",
             "n_before": H.get("n_before"), "n_added": H.get("n_added"), "added_by_element": H.get("added_by_element")})
    if "disordered" in D:
        add("Q4_disorder",
            "Judge crystallographic disorder in this structure. Is there disorder? If yes, which component(s) are "
            "disordered and what type of disorder is it? Types: alternative_positions = atoms/groups modelled over two "
            "or more alternative sites (orientational/positional disorder, disorder groups); partial_occupancy = sites "
            "with occupancy < 1 without an alternative partner (e.g. partially occupied solvent). " + ROLE_DEF,
            {"disordered": {"type": "bool"}, "components": {"type": "set", "options": ROLES},
             "types": {"type": "set", "options": DIS_TYPES}},
            {"disordered": D["disordered"], "components": D["components"], "types": D["types"]},
            {"rule": "occupancy<1 or disorder groups per mck molecule; alternative pair = same element <1.0 A apart or >=2 groups",
             "species": [{k: c.get(k) for k in ("formula", "count", "role", "disordered")} for c in comps]})
    metals = g.get("metals") or {}
    if isinstance(metals, dict):
        s_block = {"Li", "Na", "K", "Rb", "Cs", "Be", "Mg", "Ca", "Sr", "Ba"}
        for el in sorted(metals, key=lambda e: (e in s_block, e)):  # prefer d/f/p-block centres over alkali ions
            m = metals[el]
            if not isinstance(m, dict) or "cn" not in m or m.get("cshm") is None or m["cshm"] > GEOMETRY_MAX_CSHM:
                continue
            if m.get("geometry") not in GEOMETRIES:
                continue
            add("Q6_coordination",
                f"Describe the coordination environment of the {el} atoms (all {el} sites in this structure are "
                f"equivalent in coordination). Count the directly bonded donor atoms (coordination number) and give the "
                f"coordination geometry.",
                {"cn": {"type": "int"}, "geometry": {"type": "choice", "options": GEOMETRIES}},
                {"cn": m["cn"], "geometry": m["geometry"]},
                {"rule": "donors = MolCrysKit-perceived bonds of the metal to non-H, non-metal atoms; geometry = mck classify_shell (CShM)",
                 "metal": el, "cshm": m["cshm"], "n_sites": m.get("n_sites")})
            break
    if h_ok and "disordered" in D:
        issues = []
        if D["disordered"]:
            issues.append("disorder")
        if H["missing_h"]:
            issues.append("missing_hydrogen")
        if any(c.get("role") == "solvent" for c in comps):
            issues.append("solvent_present")
        add("Q7_usability",
            "Could this CIF be used directly (as is, without editing the model) as the starting structure for a periodic "
            "DFT or MD simulation? If not, which issue(s) block direct use? Possible issues: disorder (unresolved "
            "disorder/partial occupancies), missing_hydrogen (H atoms missing), solvent_present (lattice solvent "
            "molecules that must be kept, removed or modelled deliberately).",
            {"usable": {"type": "bool"}, "issues": {"type": "set", "options": ISSUES}},
            {"usable": not issues, "issues": issues},
            {"rule": "issues = disorder (Q4) + missing_hydrogen (Q3) + solvent_present (a species with role solvent); usable iff none"})
    return tasks


def props(g: dict) -> dict:
    comps = g.get("components") or []
    main = next((c for c in comps if c.get("role") == "main"), None)
    return {"solvent": any(c.get("role") == "solvent" for c in comps),
            "disorder": bool((g.get("disorder") or {}).get("disordered")),
            "main_hf": main["heavy_formula"] if main else "", "main_n": main["n_heavy"] if main else 0}


def pair_tasks(gts: list[dict], sources: dict, seed: int = 20261022) -> list[dict]:
    """Pairs for Q8: for each property, pair a positive with the most similar negative
    (same main heavy formula first, then closest main-component size), each structure used once
    per property; plus ~1/3 as many same-label pairs (answers both/neither)."""
    rng = random.Random(seed)
    ok = [g for g in gts if "components" in g and g.get("components")]
    P = {g["structure_id"]: props(g) for g in ok}
    tasks = []
    for prop, noun in (("solvent", "contains lattice solvent molecules"), ("disorder", "is crystallographically disordered")):
        pos = sorted([s for s in P if P[s][prop]])
        neg = sorted([s for s in P if not P[s][prop]])
        used = set()
        pairs = []

        def dist(a, b):
            return (P[a]["main_hf"] != P[b]["main_hf"], abs(P[a]["main_n"] - P[b]["main_n"]) / max(P[a]["main_n"], P[b]["main_n"], 1))

        for a in sorted(pos, key=lambda s: P[s]["main_n"]):
            cands = [b for b in neg if b not in used]
            if not cands:
                break
            b = min(cands, key=lambda b: dist(a, b))
            if dist(a, b)[1] > 0.5 and dist(a, b)[0]:
                continue  # nothing similar enough
            used.update((a, b))
            pairs.append((a, b))
        n_same = max(1, len(pairs) // 3)
        for group in (pos, neg):
            pool = [s for s in group]
            rng.shuffle(pool)
            k = 0
            for a in pool:
                if k >= (n_same + 1) // 2:
                    break
                cands = [b for b in group if b != a]
                if not cands:
                    break
                b = min(cands, key=lambda b: dist(a, b))
                if (b, a) in pairs or (a, b) in pairs:
                    continue
                pairs.append((a, b))
                k += 1
        for a, b in pairs:
            if rng.random() < 0.5:
                a, b = b, a
            la, lb = P[a][prop], P[b][prop]
            gold = "both" if la and lb else "neither" if not (la or lb) else ("A" if la else "B")
            sid = f"{a}|{b}"
            tasks.append({"structure_id": sid, "path": ga_path(ok, a), "source": "pair",
                          "structures": [{"label": "A", "structure_id": a, "path": ga_path(ok, a)},
                                         {"label": "B", "structure_id": b, "path": ga_path(ok, b)}],
                          "id": f"{sid}:Q8_{prop}", "qtype": "Q8_compare",
                          "question": f"You are given two similar crystal structures, A and B. Which of them {noun}? "
                                      "Answer A, B, both or neither.",
                          "answer_type": "choice", "options": ["A", "B", "both", "neither"], "gold": gold,
                          "evidence": {"property": prop, "A": {k: P[a][k] for k in (prop, "main_hf")},
                                       "B": {k: P[b][k] for k in (prop, "main_hf")}}})
    return tasks


def is_molecular(g: dict) -> bool:
    """Scope rule: molecular / metal-organic crystals only = contains C plus at least one of H, N, O.
    Purely inorganic solids (oxides, halides, elements such as diamond) are excluded."""
    els = {e for c in g.get("components") or [] for e in c.get("elements", [])}
    return "C" in els and bool(els & {"H", "N", "O"})


def ga_path(gts, sid):
    return next(g["path"] for g in gts if g["structure_id"] == sid)


from .gt import GEOMETRIES, METALS, MISSING_H_FRACTION  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["gt", "tasks", "all"], default="all")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    items = sorted(manifest["structures"].items())
    if args.stage in ("gt", "all"):
        with ThreadPoolExecutor(args.workers) as ex:
            futs = {ex.submit(compute_gt, sid, meta["path"], args.force): sid for sid, meta in items}
            for f in futs:
                r = f.result()
                print(f"{futs[f]}: {'ERROR ' + r['error'][:120] if 'error' in r else 'ok'}", flush=True)
    if args.stage in ("tasks", "all"):
        gts = [json.loads((GT_DIR / f"{sid}.json").read_text(encoding="utf-8")) for sid, _ in items if (GT_DIR / f"{sid}.json").exists()]
        sources = {sid: meta["source"] for sid, meta in items}
        eligible = [g for g in gts if "error" not in g and is_molecular(g)]
        out_of_scope = sorted(g["structure_id"] for g in gts if "error" not in g and not is_molecular(g))
        tasks = []
        for g in eligible:
            tasks.extend(single_tasks(g, sources[g["structure_id"]]))
        tasks.extend(pair_tasks(eligible, sources))
        TASKS.mkdir(parents=True, exist_ok=True)
        with (TASKS / "tasks.jsonl").open("w", encoding="utf-8") as f:
            for t in tasks:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
        counts = Counter(t["qtype"] for t in tasks)
        (TASKS / "taskgen_log.json").write_text(json.dumps({
            "n_structures": len(items), "n_gt_ok": sum("error" not in g for g in gts),
            "gt_errors": {g["structure_id"]: g["error"] for g in gts if "error" in g},
            "out_of_scope_inorganic": out_of_scope, "n_structures_with_tasks": len(eligible),
            "n_tasks": len(tasks), "by_qtype": counts}, indent=1), encoding="utf-8")
        print("total", len(tasks), dict(counts))


if __name__ == "__main__":
    main()
