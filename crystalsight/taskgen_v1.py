"""Generate CrystalSight tasks with deterministic MolCrysKit ground truth.

Question types (gold = MolCrysKit output; we measure agreement with mck):
  T1_nmol      int   number of discrete molecules/ions in the unit cell
  T1_nspecies  int   number of chemically distinct molecular species
  T2_moieties  set   Hill formulas of the distinct species
  T3_disorder  bool  does the CIF contain crystallographic disorder
  T4_hydrogen  bool  does the model contain any hydrogen sites
  T5_contacts  set   which of {hydrogen_bond, halogen_bond, pi_stacking} occur
  T6_cn        int   coordination number of metal M by ligand atom L

Eligibility rules are deliberately conservative so the gold is unambiguous;
every exclusion is recorded in tasks/taskgen_log.json.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .mck_cli import run_mck
from .paths import DATA, ROOT, TASKS

METALS = ["Zn", "Cu", "Ag", "Co", "Ni", "Fe", "Mn", "Cd", "Cr", "Pb", "K", "Na", "Ca", "Mg"]
TRANSITION = {"Zn", "Cu", "Ag", "Co", "Ni", "Fe", "Mn", "Cd", "Cr"}
CONTACTS = ["hydrogen_bond", "halogen_bond", "pi_stacking"]
MAX_MOLECULES = 64


def hill(formula: str) -> str:
    return re.sub(r"\s+", "", formula or "")


def build_for_structure(sid: str, meta: dict) -> tuple[list[dict], list[str]]:
    path = ROOT / meta["path"]
    tasks: list[dict] = []
    notes: list[str] = []
    summ = run_mck("summary", path)
    if not summ["ok"]:
        return [], [f"summary failed: {summ.get('error', '')[-160:]}"]
    S = summ["data"]
    comp = S.get("species_counts") or {}
    organic = "C" in comp or "H" in comp  # molecular candidates; extended solids are filtered below
    disordered = bool((S.get("disorder") or {}).get("has_disorder"))
    base = {"structure_id": sid, "path": meta["path"], "source": meta["source"]}

    def add(qtype: str, question: str, answer_type: str, gold, evidence: dict, options=None):
        t = {**base, "id": f"{sid}:{qtype}", "qtype": qtype, "question": question,
             "answer_type": answer_type, "gold": gold, "evidence": evidence}
        if options is not None:
            t["options"] = options
        tasks.append(t)

    add("T3_disorder", "Does this crystal structure contain crystallographic disorder "
        "(sites with partial occupancy or alternative disorder groups)?", "bool", disordered,
        {"mck": "analyze summary", "disorder": S.get("disorder")})

    sc = run_mck("sanity-check", path)
    if sc["ok"]:
        res = {r["name"]: r for r in sc["data"]["frames"][0]["results"]}
        hp = res.get("hydrogen_presence", {}).get("details", {}).get("has_hydrogen")
        if hp is not None:
            add("T4_hydrogen", "Does the structural model contain any hydrogen atom sites?", "bool", bool(hp),
                {"mck": "analyze sanity-check", "hydrogen_presence": res.get("hydrogen_presence")})
    else:
        notes.append("sanity-check failed")

    if not organic:
        notes.append("no C/H (ionic/covalent solid): T1/T2/T5 skipped")
    elif disordered:
        notes.append("disordered: T1/T2/T5 skipped (molecule inventory ambiguous)")
    else:
        mol = run_mck("molecules", path)
        if not mol["ok"]:
            notes.append("molecules failed")
        else:
            M = mol["data"]
            n_atoms = S.get("n_atoms") or 0
            biggest = max((m.get("atom_count", 0) for m in M), default=0)
            if not M or len(M) > MAX_MOLECULES:
                notes.append(f"molecule count {len(M)} outside 1..{MAX_MOLECULES}")
            elif len(M) == 1 and n_atoms and biggest >= n_atoms:
                notes.append("single extended component (framework/polymer): T1/T2 skipped")
            else:
                species = Counter(m["species_id"] for m in M)
                formulas = sorted({hill(m["hill_formula"] or m["formula"]) for m in M})
                ev = {"mck": "io molecules", "n_molecules": len(M),
                      "species": {k: v for k, v in species.items()}, "formulas": formulas}
                add("T1_nmol", "How many discrete molecules or ions (complete connected components) "
                    "are in one unit cell?", "int", len(M), ev)
                add("T1_nspecies", "How many chemically distinct kinds of molecules or ions are present?",
                    "int", len(species), ev)
                add("T2_moieties", "List the Hill formula of each chemically distinct molecule or ion "
                    "(e.g. [\"C8H9NO2\", \"H2O\"]).", "formula_set", formulas, ev)
        inter = run_mck("interactions", path)
        if inter["ok"]:
            I = inter["data"]
            present = sorted(k for k in CONTACTS if (I.get(k) or {}).get("count", 0) > 0)
            add("T5_contacts", "Which of these intermolecular contact types occur in the crystal: "
                "hydrogen_bond, halogen_bond, pi_stacking? Answer with the subset that occurs.",
                "set", present, {"mck": "analyze interactions", "counts": {k: (I.get(k) or {}).get("count") for k in CONTACTS}},
                options=CONTACTS)
        else:
            notes.append("interactions failed")

    metals = [m for m in METALS if m in comp and m in TRANSITION]
    for metal in metals[:1]:
        for lig in ("N", "O"):
            if lig not in comp:
                continue
            poly = run_mck("polyhedra", path, "--central", metal, "--ligand", lig, "--level", "atom")
            if not poly["ok"] or not poly["data"]:
                continue
            cns = Counter(p.get("coordination_number") for p in poly["data"])
            if len(cns) == 1:
                cn = next(iter(cns))
                if cn and cn > 0:
                    add("T6_cn", f"What is the coordination number of each {metal} atom counting only "
                        f"{lig} donor atoms?", "int", int(cn),
                        {"mck": f"analyze polyhedra --central {metal} --ligand {lig}", "cn_histogram": dict(cns)})
                    break
            else:
                notes.append(f"{metal}-{lig}: non-uniform CN {dict(cns)}")
    return tasks, notes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    items = sorted(manifest["structures"].items())
    if args.limit:
        items = items[: args.limit]
    TASKS.mkdir(parents=True, exist_ok=True)
    log: dict[str, list[str]] = {}
    all_tasks: list[dict] = []
    with ThreadPoolExecutor(args.workers) as ex:
        for (sid, _), (tasks, notes) in zip(items, ex.map(lambda kv: build_for_structure(*kv), items)):
            all_tasks.extend(tasks)
            log[sid] = notes
            print(f"{sid}: {len(tasks)} tasks {notes}", flush=True)
    with (TASKS / "tasks.jsonl").open("w", encoding="utf-8") as f:
        for t in all_tasks:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    counts = Counter(t["qtype"] for t in all_tasks)
    (TASKS / "taskgen_log.json").write_text(json.dumps({"n_structures": len(items),
        "n_structures_with_tasks": len({t["structure_id"] for t in all_tasks}),
        "n_tasks": len(all_tasks), "by_qtype": counts, "notes": log}, indent=1), encoding="utf-8")
    print("total", len(all_tasks), dict(counts))


if __name__ == "__main__":
    main()