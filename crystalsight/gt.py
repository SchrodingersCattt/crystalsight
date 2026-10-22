"""Deterministic per-structure ground truth for the crystallographer question families.

Everything here is computed from the CIF via MolCrysKit (pip dependency) plus
small, documented rules of our own. One call = one structure; taskgen runs it
in a child process with a timeout.

Output (JSON-safe dict):
  components : list of species {formula, heavy_formula, n_heavy, count, role, disordered}
               role in {main, solvent, counterion, other_component}
  hydrogen   : {has_any_h, n_added, added_by_element, missing_h, elements}
  disorder   : {disordered, components (roles), types}
  metals     : {metal: {cns: [...], cn, geometry, cshm, n_sites}}
"""

from __future__ import annotations

import sys
import warnings
from collections import Counter, defaultdict

import numpy as np

warnings.filterwarnings("ignore")

# Solvents: MolCrysKit COMMON_SOLVENTS plus a few frequent lattice solvents (heavy-atom formulas).
EXTRA_SOLVENTS_HEAVY = {
    "O": "water", "CO": "methanol", "C2O": "ethanol", "C3O": "acetone/propanol", "CCl2": "dichloromethane",
    "CCl3": "chloroform", "CCl4": "tetrachloromethane", "C3NO": "DMF", "C2N": "acetonitrile", "C4O": "THF/diethyl ether",
    "C7": "toluene", "C6": "benzene/cyclohexane/hexane", "C2OS": "DMSO", "C5N": "pyridine", "C4O2": "dioxane/ethyl acetate",
    "CNO2": "nitromethane", "C2Cl2": "dichloroethane", "C6Cl": "chlorobenzene", "C4NO": "DMA", "C2O2": "acetic acid",
    "C3NO2": "nitro-propane",
}
# Common counter-ions (heavy-atom formulas). Monoatomic metal/halide ions are handled by rule.
COUNTERIONS_HEAVY = {"ClO4", "NO3", "BF4", "F6P", "O4S", "CF3O3S", "F6Sb", "AsF6", "O4P", "CO3", "CN", "CNS", "N3",
                     "O4Re", "BrO3", "IO3", "Cl4Zn", "Cl4Cu", "Cl4Co", "Br4Zn", "N", "F6Si", "BC24"}
HALIDES = {"F", "Cl", "Br", "I"}
METALS = {"Li", "Na", "K", "Rb", "Cs", "Be", "Mg", "Ca", "Sr", "Ba", "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni",
          "Cu", "Zn", "Y", "Zr", "Nb", "Mo", "Ru", "Rh", "Pd", "Ag", "Cd", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt",
          "Au", "Hg", "Al", "Ga", "In", "Tl", "Sn", "Pb", "Bi", "La", "Ce", "Pr", "Nd", "Sm", "Eu", "Gd", "Tb", "Dy",
          "Ho", "Er", "Tm", "Yb", "Lu", "U"}
# Q3 rule: H counted as missing when mck add_hydrogens adds >= 5 % of the completed H count
# (or the model has no H at all). Below that, additions are treated as placement noise
# (e.g. ambiguous protonation in large disordered frameworks).
MISSING_H_FRACTION = 0.05
GEOMETRIES = ["tetrahedron", "square_planar", "trigonal_bipyramid", "square_pyramid", "octahedron", "trigonal_prism",
              "pentagonal_bipyramid", "capped_octahedron", "cube", "square_antiprism", "dodecahedron"]


def heavy_formula(symbols) -> str:
    c = Counter(s for s in symbols if s != "H")
    order = sorted(c, key=lambda e: (e != "C", e))
    return "".join(f"{e}{c[e] if c[e] > 1 else ''}" for e in order)


def full_formula(symbols) -> str:
    c = Counter(symbols)
    order = sorted(c, key=lambda e: (e != "C", e != "H", e))
    return "".join(f"{e}{c[e] if c[e] > 1 else ''}" for e in order)


def classify_roles(species: list[dict]) -> None:
    """Rule: main = species with most heavy atoms (tie: higher count). Among the rest:
    solvent if heavy formula is a known solvent; counterion if monoatomic halide/metal ion
    or a listed inorganic anion; otherwise other_component (co-former, second ligand...)."""
    if not species:
        return
    main = max(species, key=lambda s: (s["n_heavy"], s["count"]))
    for s in species:
        hf = s["heavy_formula"]
        if s["n_heavy"] == 0:
            s["role"] = "isolated_H"  # loose/disordered H sites with no heavy-atom partner; ignored for location
        elif s is main:
            s["role"] = "main"
        elif (hf in EXTRA_SOLVENTS_HEAVY or set(s["elements"]) <= {"O", "H"}) and not any(e in METALS for e in s["elements"]):
            s["role"] = "solvent"
        elif (s["n_heavy"] == 1 and (hf in HALIDES or hf in METALS)) or hf in COUNTERIONS_HEAVY:
            s["role"] = "counterion"
        else:
            s["role"] = "other_component"


def analyze(path: str) -> dict:
    from molcrys_kit.cli._common import load_crystal

    crystal = load_crystal(path)
    mols = crystal.molecules
    # ---------------- components + disorder per molecule
    groups: dict[str, dict] = {}
    alt_pairs = False
    partial_any = False
    partial_unpaired = False
    for m in mols:
        sym = m.get_chemical_symbols()
        occ = np.asarray(m.arrays.get("occupancy", np.ones(len(sym))), dtype=float)
        dg = m.arrays.get("disorder_group")
        dgs = set()
        if dg is not None:
            for g in dg:
                gs = str(g).strip()
                if gs not in ("", ".", "0", "None", "nan", "-1"):
                    dgs.add(gs)
        part = occ < 0.995
        dis = bool(part.any() or dgs)
        if dis:
            partial_any = True
            pos = m.get_positions()
            idx = np.where(part)[0]
            paired = set()
            for a in range(len(idx)):
                for b in range(a + 1, len(idx)):
                    i, j = idx[a], idx[b]
                    if sym[i] == sym[j] and np.linalg.norm(pos[i] - pos[j]) < 1.0:
                        paired.update((i, j))
            if paired or len(dgs) >= 2:
                alt_pairs = True
            if len(set(idx) - paired) > 0 and len(dgs) < 2:
                partial_unpaired = True
        hf = heavy_formula(sym)
        g = groups.setdefault(hf, {"heavy_formula": hf, "formula": full_formula(sym), "n_heavy": sum(s != "H" for s in sym),
                                   "elements": sorted(set(sym)), "count": 0, "disordered": False})
        g["count"] += 1
        g["disordered"] = g["disordered"] or dis
    species = sorted(groups.values(), key=lambda s: -s["n_heavy"])
    classify_roles(species)
    dis_roles = sorted({s["role"] for s in species if s["disordered"] and s["role"] != "isolated_H"})
    types = []
    if partial_any:
        if alt_pairs:
            types.append("alternative_positions")
        if partial_unpaired or not alt_pairs:
            types.append("partial_occupancy")
    disorder = {"disordered": bool(partial_any), "components": dis_roles, "types": sorted(types)}

    # ---------------- hydrogen completeness (mck add_hydrogens; count new H per parent element)
    hydrogen: dict = {"has_any_h": any("H" in s["elements"] for s in species)}
    try:
        from molcrys_kit.operations import add_hydrogens

        before_atoms = crystal.to_ase()
        res = add_hydrogens(crystal)
        after = res.to_ase()
        cell = np.asarray(after.cell)
        sb, sa = before_atoms.get_chemical_symbols(), after.get_chemical_symbols()
        before = sb.count("H")
        n_after = sa.count("H")
        fb = before_atoms.get_scaled_positions(wrap=True)
        fa = after.get_scaled_positions(wrap=True)
        h_old = fb[[i for i, x in enumerate(sb) if x == "H"]]
        heavy = [i for i, x in enumerate(sa) if x != "H"]
        added = Counter()
        for i, x in enumerate(sa):
            if x != "H":
                continue
            if len(h_old):
                d = h_old - fa[i]; d -= np.round(d)
                if np.min(np.linalg.norm(d @ cell, axis=1)) < 0.05:
                    continue
            d = fa[heavy] - fa[i]; d -= np.round(d)
            added[sa[heavy[int(np.argmin(np.linalg.norm(d @ cell, axis=1)))]]] += 1
        n_added = n_after - before
        total = before + max(n_added, 0)
        frac = (n_added / total) if total else 0.0
        missing = n_added > 0 and (before == 0 or frac >= MISSING_H_FRACTION)
        elements = sorted(e for e, k in added.items() if missing and k >= 0.1 * max(n_added, 1))
        hydrogen.update({"n_before": before, "n_added": int(n_added), "added_by_element": dict(added),
                         "missing_fraction": round(frac, 4), "missing_h": bool(missing), "elements": elements})
    except Exception as e:  # noqa: BLE001
        hydrogen["error"] = f"{type(e).__name__}: {str(e)[:200]}"

    # ---------------- metal coordination (own donor shell + mck CShM classify_shell)
    metals: dict = {}
    try:
        from ase.data import covalent_radii
        from ase.neighborlist import neighbor_list
        from molcrys_kit.analysis.shape import classify_shell

        atoms = crystal.to_ase()
        sym = atoms.get_chemical_symbols()
        cutoffs = [covalent_radii[n] * 1.15 for n in atoms.numbers]
        ii, jj, dd, DD = neighbor_list("ijdD", atoms, cutoffs)
        by_metal = defaultdict(list)
        for i in sorted(set(ii)):
            if sym[i] not in METALS:
                continue
            mask = (ii == i)
            vecs = [DD[k] for k in np.where(mask)[0] if sym[jj[k]] not in METALS and sym[jj[k]] != "H"]
            by_metal[sym[i]].append(vecs)
        for el, shells in by_metal.items():
            cns = [len(v) for v in shells]
            info = {"n_sites": len(shells), "cns": dict(Counter(cns))}
            if len(set(cns)) == 1 and 4 <= cns[0] <= 8:
                r = classify_shell(np.asarray(shells[0]), np.zeros(3), cn=cns[0])
                info.update({"cn": cns[0], "geometry": r.get("primary_label"), "cshm": r.get("cshm_value"),
                             "best_match": str(r.get("best_match"))[:200], "label_source": r.get("label_source"),
                             "label_modifier": r.get("label_modifier")})
            metals[el] = info
    except Exception as e:  # noqa: BLE001
        metals = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
    return {"components": species, "disorder": disorder, "hydrogen": hydrogen, "metals": metals}


def metals_from_bonds(crystal) -> dict:
    """Q6 gold v2: donors = MolCrysKit's own perceived bonds of each metal atom (non-H, non-metal
    partners, from the molecule bond records); geometry = MolCrysKit classify_shell (CShM)."""
    from molcrys_kit.analysis.shape import classify_shell

    shells = defaultdict(list)
    for m in crystal.molecules:
        sym = m.get_chemical_symbols()
        gidx = list(m.info.get("atom_indices") or range(len(sym)))
        local = {g: i for i, g in enumerate(gidx)}
        vecs = defaultdict(list)
        for rec in m.info.get("bond_records") or []:
            a, b, v = rec["left"], rec["right"], np.asarray(rec["vector"], dtype=float)
            if a not in local or b not in local:
                continue
            ea, eb = sym[local[a]], sym[local[b]]
            if ea in METALS and eb not in METALS and eb != "H":
                vecs[a].append(v)
            if eb in METALS and ea not in METALS and ea != "H":
                vecs[b].append(-v)
        for i, e in enumerate(sym):
            if e in METALS:
                shells[e].append(vecs.get(gidx[i], []))
    out = {}
    for el, sh in shells.items():
        cns = [len(v) for v in sh]
        info = {"n_sites": len(sh), "cns": dict(Counter(cns)), "method": "mck_bonds"}
        if len(set(cns)) == 1 and 4 <= cns[0] <= 8:
            r = classify_shell(np.asarray(sh[0]), np.zeros(3), cn=cns[0])
            info.update({"cn": cns[0], "geometry": r.get("primary_label"), "cshm": r.get("cshm_value"),
                         "label_modifier": r.get("label_modifier")})
        out[el] = info
    return out


if __name__ == "__main__":
    import json

    if len(sys.argv) > 2 and sys.argv[2] == "--metals-only":
        from molcrys_kit.cli._common import load_crystal

        print(json.dumps({"metals": metals_from_bonds(load_crystal(sys.argv[1]))}, default=str))
    else:
        print(json.dumps(analyze(sys.argv[1]), default=str))
