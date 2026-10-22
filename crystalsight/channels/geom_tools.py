"""Ad hoc geometry tools for the tools channel (built for the CrystalSight spatial benchmark, v4).

Generic primitives over the expanded crystal (crystalsight.gt_spatial on top of numpy/pymatgen; disorder
components selected from the CIF PART/occupancy columns).  They return raw geometric data - lists of contacts,
neighbours, paths, ring members - and the model must still choose criteria/cutoffs and interpret/count.
Atom naming is the copy-aware label used by the gold answers and by MatterVis label_sym:
SITE#k[i,j,k] = copy of CIF site SITE from symmetry operation k (1-based, CIF order; '#1' may be omitted),
wrapped into [0,1) and shifted by [i,j,k] ('[0,0,0]' may be omitted).
"""
from __future__ import annotations

import re
from collections import deque
from functools import lru_cache
from pathlib import Path

import numpy as np

from .. import gt_spatial as G

GEOM_TOOLS = {
    "geom_hbond_list": "H-bond candidates donated by one molecule: D-H...A with copy-aware labels, H...A, D...A (A), angle (deg). "
                       "arguments {\"atom\": \"O1\" (molecule containing the home copy), \"max_ha\": 2.9, \"min_angle\": 100, \"component\": \"all\"}",
    "geom_nearest_atoms": "nearest atoms to one atom copy: label, element, distance, same_molecule. arguments {\"atom\": \"H2\" or "
                          "\"O3#3[0,1,0]\", \"elements\": [\"N\",\"O\"] (optional filter), \"n\": 10, \"other_molecules_only\": false, \"component\": \"all\"}",
    "geom_hbond_path": "shortest chain of H-bonded molecules from the molecule of an atom to its copy translated by a lattice vector; "
                       "returns the H-bonds along the chain (or that none exists within 12 steps). arguments {\"atom\": \"O1\", "
                       "\"translation\": [0,1,1], \"max_ha\": 2.5, \"min_angle\": 120, \"component\": \"all\"}",
    "geom_hbond_ring": "smallest closed ring of covalent bonds + H-bonds through one H-bond; returns the ring members in order "
                       "(copy-aware labels, each with its molecule). arguments {\"h_atom\": \"H5\" (home copy), \"acceptor\": \"O2#8\", "
                       "\"max_ha\": 2.5, \"min_angle\": 120, \"component\": \"all\"}",
    "geom_neighbours": "molecules around the molecule of an atom, sorted by distance: representative copy label, formula, distance. "
                       "arguments {\"atom\": \"C1\", \"cutoff\": 6.0, \"mode\": \"any_atom\" | \"centroid\", \"component\": \"all\"}",
    "geom_disorder_components": "disorder groups (PART) with site count, mean occupancy and major/minor role; the other geom_* "
                                "tools accept \"component\": \"major\" | \"minor\" | \"all\" to work on that ordered model. arguments {}",
}
_LBL = re.compile(r"^(.+?)(?:#(\d+))?(?:\[(-?\d+),(-?\d+),(-?\d+)\])?$")
MAX_ROWS = 120


@lru_cache(maxsize=32)
def _load(path: str, component: str):
    cr = G.load(path)
    if component in ("major", "minor"):
        comp = G.disorder_components(cr)
        if not comp:
            raise ValueError("structure has no disorder groups; use component 'all'")
        keep = {g for g, o in comp.items() if (o >= 0.5) == (component == "major")}
        cr = G.subset(cr, [g in (".", "0", "?") or g in keep for g in cr.dgroup])
    return cr


def _atom(cr, label):
    """copy-aware label -> (expanded atom index, absolute lattice shift n)."""
    m = _LBL.match(re.sub(r"\s+", "", str(label)))
    if not m:
        raise ValueError(f"bad atom label {label!r}")
    site, k, *sh = m.groups()
    op = int(k or 1) - 1
    cand = [a for a in range(len(cr.c_frac)) if cr.c_label[a] == site and cr.c_op[a] == op]
    if not cand:
        raise ValueError(f"no atom {label!r} (site unknown, or operation {op + 1} does not generate a distinct copy of it)")
    return cand[0], np.array([int(x or 0) for x in sh])


def _inst(cr, a, n):
    return int(cr.mol_of[a]), np.asarray(n) - cr.img_of[a]


def _mol_label(cr, inst):
    a = min(cr.mols[inst[0]])
    return G.copy_label(cr, a, inst[1])


def _formula(cr, m):
    from collections import Counter
    c = Counter(cr.c_elem[a] for a in cr.mols[m])
    return "".join(f"{e}{c[e] if c[e] > 1 else ''}" for e in sorted(c, key=lambda e: (e != "C", e != "H", e)))


def _hb_rows(cr, inst, max_ha, min_angle):
    return [dict(donor=G.copy_label(cr, h["d"], inst[1]), H=h["h_label"], acceptor=h["a_label"],
                 acceptor_molecule=_mol_label(cr, h["inst"]), HA=round(h["HA"], 3), DA=round(h["DA"], 3), angle=round(h["angle"], 1))
            for h in G.hb_contacts(cr, inst, max_ha, min_angle)]


def call_geom(name: str, args: dict, path: Path):
    comp = str(args.get("component", "all")).lower()
    try:
        cr = _load(str(path), comp)
        if name == "geom_disorder_components":
            full = _load(str(path), "all")
            comps = G.disorder_components(full)
            return {"groups": [dict(group=g, sites=sum(x == g for x in full.dgroup), mean_occupancy=round(o, 3),
                                    role="major" if o >= 0.5 else "minor") for g, o in sorted(comps.items())]} if comps \
                else {"groups": [], "note": "no disorder groups in this CIF"}
        if name == "geom_hbond_list":
            a, n = _atom(cr, args.get("atom", ""))
            inst = _inst(cr, a, n)
            rows = _hb_rows(cr, inst, float(args.get("max_ha", 2.9)), float(args.get("min_angle", 100)))
            return {"molecule": _mol_label(cr, inst), "hbonds": rows}
        if name == "geom_nearest_atoms":
            a, n = _atom(cr, args.get("atom", ""))
            inst0 = _inst(cr, a, n)
            p0 = (cr.c_frac[a] + n) @ cr.M
            els = {str(e).capitalize() for e in (args.get("elements") or [])}
            other = bool(args.get("other_molecules_only", False))
            out = []
            for b in range(len(cr.c_frac)):
                if els and cr.c_elem[b] not in els:
                    continue
                for S in G.itertools.product(range(-2, 3), repeat=3):
                    S = np.array(S) + np.rint(n).astype(int)
                    d = float(np.linalg.norm((cr.c_frac[b] + S) @ cr.M - p0))
                    if d < 1e-3 or d > 8.0:
                        continue
                    same = G.same(_inst(cr, b, S), inst0)
                    if other and same:
                        continue
                    out.append((d, G.copy_label(cr, b, S - cr.img_of[b]), cr.c_elem[b], same))
            out.sort()
            k = max(1, min(int(args.get("n", 10)), 50))
            return [dict(atom=l, element=e, distance=round(d, 3), same_molecule=s) for d, l, e, s in out[:k]]
        if name == "geom_hbond_path":
            a, n = _atom(cr, args.get("atom", ""))
            inst0 = _inst(cr, a, n)
            t = np.array([int(x) for x in args.get("translation", [0, 0, 0])])
            E = G.hb_graph(cr, float(args.get("max_ha", 2.5)), float(args.get("min_angle", 120)))
            s0 = (inst0[0], tuple(int(x) for x in inst0[1]))
            s1 = (inst0[0], tuple(int(x) for x in inst0[1] + t))
            prev, q = {s0: None}, deque([s0])
            while q and s1 not in prev:
                u = q.popleft()
                if len(_chain(prev, u)) > 12:
                    continue
                for m2, S2, rec in E[u[0]]:
                    v = (m2, tuple(int(x) for x in np.asarray(u[1]) + S2))
                    if v not in prev:
                        prev[v] = (u, rec)
                        q.append(v)
            if s1 not in prev:
                return {"from": _mol_label(cr, inst0), "to": _mol_label(cr, (inst0[0], inst0[1] + t)),
                        "result": "no H-bond chain found within 12 steps"}
            steps = []
            for v in _chain(prev, s1):
                u, rec = prev[v]
                Su, Sv = np.array(u[1]), np.array(v[1])
                fwd = rec["h"] in cr.mols[u[0]] and v[0] == rec["inst"][0] and np.array_equal(Sv - Su, rec["inst"][1])
                Sh, Sa = (Su, Sv) if fwd else (Sv, Su)
                steps.append(dict(from_molecule=_mol_label(cr, (u[0], Su)), to_molecule=_mol_label(cr, (v[0], Sv)),
                                  hbond=f"{G.copy_label(cr, rec['h'], Sh)}...{G.copy_label(cr, rec['b'], Sa)}", HA=round(rec["HA"], 3)))
            return {"from": _mol_label(cr, inst0), "to": _mol_label(cr, (inst0[0], inst0[1] + t)), "chain": steps}
        if name == "geom_hbond_ring":
            r = G.hb_ring(cr, str(args.get("h_atom", "")), re.sub(r"\s+", "", str(args.get("acceptor", ""))),
                          float(args.get("max_ha", 2.5)), float(args.get("min_angle", 120)), depth=4)
            if r is None:
                return {"result": "no closed ring through this H-bond among molecules within 4 H-bond steps"}
            members = []
            for lab in r["path"]:
                b, nn = _atom(cr, lab)
                members.append(dict(atom=lab, molecule=_mol_label(cr, _inst(cr, b, nn))))
            return {"ring_members_in_order": members, "note": "the ring closes from the last member back to the first"}
        if name == "geom_neighbours":
            a, n = _atom(cr, args.get("atom", ""))
            inst0 = _inst(cr, a, n)
            cut = min(float(args.get("cutoff", 6.0)), 16.0)
            mode = str(args.get("mode", "any_atom"))
            rows = []
            if mode == "centroid":
                c0 = (G.mol_frac(cr, *inst0)[1] @ cr.M).mean(0)
                R = cr.lattice.reciprocal_lattice_crystallographic.matrix
                rng = [int(np.ceil(cut * np.linalg.norm(R[i]))) + 2 for i in range(3)]
                for m in range(len(cr.mols)):
                    cm = G.mol_frac(cr, m, (0, 0, 0))[1].mean(0)
                    for S in G.itertools.product(*(range(-k, k + 1) for k in rng)):
                        S = np.array(S)
                        if m == inst0[0] and np.array_equal(S, inst0[1]):
                            continue
                        d = float(np.linalg.norm((cm + S) @ cr.M - c0))
                        if d <= cut:
                            rows.append((d, m, S))
            elif mode == "any_atom":
                rows = [(d, m, S) for d, m, S in G.neighbor_molecules(cr, inst0, cutoff=cut, rng=3)]
            else:
                return {"error": "mode must be centroid or any_atom"}
            rows.sort(key=lambda x: x[0])
            res = [dict(molecule=_mol_label(cr, (m, S)), formula=_formula(cr, m), distance=round(d, 3)) for d, m, S in rows]
            out = {"reference": _mol_label(cr, inst0), "mode": mode, "cutoff": cut, "neighbours": res[:MAX_ROWS]}
            if len(res) > MAX_ROWS:
                out["truncated"] = f"{len(res) - MAX_ROWS} more beyond the first {MAX_ROWS}"
            return out
    except (ValueError, KeyError, IndexError) as exc:
        return {"error": str(exc)[:300]}
    return {"error": f"unknown tool {name}"}


def _chain(prev, v):
    out = []
    while prev[v] is not None:
        out.append(v)
        v = prev[v][0]
    return out[::-1]