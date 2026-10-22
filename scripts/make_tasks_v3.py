"""Generate CrystalSight v3 spatial-reasoning tasks (tasks_v3/tasks_v3.jsonl + TASKS_v3.md).

All gold answers are computed deterministically from geometry (crystalsight.gt_spatial).
No model / LLM is called.  Run:  python scripts/make_tasks_v3.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from crystalsight import gt_spatial as g  # noqa: E402

OUT = ROOT / "tasks_v3"
FRAGILE = 0.05  # relative margin below which an answer is considered fragile
REL_OPTIONS = ["translation", "inversion", "2-fold rotation", "2_1 screw", "mirror", "glide"]
DIM_OPTIONS = ["0D", "1D_a", "1D_b", "1D_c", "1D_other", "2D_ab", "2D_ac", "2D_bc", "2D_other", "3D"]
DIST_BINS = [("lt4.0", 0, 4.0), ("4.0-5.0", 4.0, 5.0), ("5.0-6.0", 5.0, 6.0), ("gt6.0", 6.0, 1e9)]
STACK_TYPES = ["face_to_face", "offset_parallel", "non_parallel"]
ANG_BINS = [("parallel", 0, 15.0), ("inclined", 15.0, 45.0), ("herringbone_T", 45.0, 90.01)]
PAR_ANG, F2F_OFF = 15.0, 1.5
HB_HA, HB_ANG = 2.50, 120.0

REF_TXT = ("The reference molecule is the molecule that contains atom {ref} at exactly the fractional "
           "coordinates listed in the CIF (symmetry operation x,y,z, no lattice translation); build the "
           "complete molecule from covalent bonds, using symmetry/periodic images where needed.")
_cache: dict = {}


def load(path):
    if path not in _cache:
        _cache[path] = g.load(ROOT / path)
    return _cache[path]


def rel_margin(x, edges):
    """Smallest relative distance |x-e|/e of value x to any threshold e."""
    return min(abs(x - e) / e for e in edges if 0 < e < 1e8)


def ring_by_labels(cr, inst, labels):
    for r in g.rings(cr, inst):
        if sorted(r["labels"]) == sorted(labels):
            return r
    raise KeyError(labels)


def same_ring_copies(cr, inst, labels, cutoff=12.0):
    r0 = ring_by_labels(cr, inst, labels)
    rows = []
    for d, m, S in g.neighbor_molecules(cr, inst, cutoff=cutoff, heavy_only=True):
        for r in g.rings(cr, (m, S)):
            if sorted(r["labels"]) != sorted(labels):
                continue
            v = r["centroid"] - r0["centroid"]
            cc = float(np.linalg.norm(v))
            perp = abs(float(np.dot(v, r0["normal"])))
            rows.append(dict(cc=cc, angle=g.acute(r0["normal"], r["normal"]), perp=perp,
                             offset=float(np.sqrt(max(cc * cc - perp * perp, 0.0))), inst=(m, S)))
    return r0, sorted(rows, key=lambda x: x["cc"])


# ------------------------------------------------------------------ family 1
def gold_F1(sp):
    cr = load(sp["path"]); ref = g.ref_instance(cr, sp["ref"])
    hb = [h for h in g.hbonds(cr, ref) if h["H"] == sp["H"]]
    best = hb[0]
    second = next((h for h in hb[1:] if (h["A"], h["inst"]) != (best["A"], best["inst"])), None)
    inst1 = (best["inst"][0], np.array(best["inst"][1]))
    rel = g.relation(cr, ref, inst1)
    kinds = sorted({r["kind"] for r in rel})
    assert len(kinds) == 1 and kinds[0] in REL_OPTIONS, kinds
    marg = ((second["HA"] - best["HA"]) / best["HA"]) if second else 9.99  # gap to 2nd-best acceptor
    numeric = dict(donor=best["D"], HA=best["HA"], DA=best["DA"], DHA_angle=best["angle"], symop=rel[0]["xyz"],
                   lattice_shift=rel[0]["t"], intrinsic_translation=rel[0]["intrinsic"],
                   second_acceptor=(second and dict(A=second["A"], HA=second["HA"])))
    return dict(acceptor_label=best["A"], relation=kinds[0]), numeric, marg, (marg < FRAGILE or best["HA"] > HB_HA * (1 - FRAGILE))


# ------------------------------------------------------------------ family 2
def _dim_label(comp):
    d, B = comp["dim"], comp["basis"]
    if d == 0:
        return "0D"
    if d == 3:
        return "3D"
    if d == 1:
        v = np.abs(np.array(B[0]))
        return {(1, 0, 0): "1D_a", (0, 1, 0): "1D_b", (0, 0, 1): "1D_c"}.get(tuple(v), "1D_other")
    n = np.abs(np.cross(B[0], B[1]))
    n = tuple((n // np.gcd.reduce(n)).tolist())
    return {(0, 0, 1): "2D_ab", (0, 1, 0): "2D_ac", (1, 0, 0): "2D_bc"}.get(n, "2D_other")


def network_label(cr, ha, ang):
    net = g.hbond_network(cr, ha_max=ha, ang_min=ang)
    labs = sorted({_dim_label(c) for c in net["components"]})
    return labs, net


def gold_F2(sp):
    cr = load(sp["path"])
    labs, net = network_label(cr, HB_HA, HB_ANG)
    assert len(labs) == 1, labs
    robust = {}
    for ha in (HB_HA * (1 - FRAGILE), HB_HA * (1 + FRAGILE)):
        for ang in (HB_ANG * (1 - FRAGILE), HB_ANG * (1 + FRAGILE)):
            robust[f"HA<={ha:.3f},ang>={ang:.0f}"] = network_label(cr, ha, ang)[0]
    stable = all(v == labs for v in robust.values())
    cand = [h for h in net["candidates"]]
    used = sorted({h["HA"] for h in cand if h["HA"] <= HB_HA and h["angle"] >= HB_ANG})
    near = sorted(cand, key=lambda h: abs(h["HA"] - HB_HA))[0]
    marg = rel_margin(near["HA"], [HB_HA])
    numeric = dict(n_hbond_edges_in_cell=net["n_edges"], hbond_HA_used=used,
                   basis=[c["basis"] for c in net["components"]][:1],
                   closest_candidate_to_threshold=dict(D=near["D"], A=near["A"], HA=near["HA"], angle=near["angle"]),
                   stable_under_pm5pct=stable)
    return dict(network=labs[0]), numeric, marg, not stable


# ------------------------------------------------------------------ family 3
def gold_F3(sp):
    cr = load(sp["path"]); ref = g.ref_instance(cr, sp["ref"])
    nb = g.neighbor_molecules(cr, ref, cutoff=sp["cutoff"] + 1.5)
    ds = [round(d, 3) for d, _, _ in nb]
    n = sum(d < sp["cutoff"] for d in ds)
    inside = [d for d in ds if d < sp["cutoff"]]; outside = [d for d in ds if d >= sp["cutoff"]]
    marg = min(rel_margin(max(inside), [sp["cutoff"]]) if inside else 9.99,
               rel_margin(min(outside), [sp["cutoff"]]) if outside else 9.99)
    k = sp["gold_pos"]  # index (0..4) of the gold option among 5 consecutive integers
    opts = [n - k + i for i in range(5)]
    letters = "ABCDE"
    numeric = dict(count=n, farthest_counted=max(inside), nearest_excluded=(min(outside) if outside else None),
                   min_contact_per_molecule=ds)
    return dict(answer=letters[k]), numeric, marg, marg < FRAGILE, {letters[i]: o for i, o in enumerate(opts)}


# ------------------------------------------------------------------ family 4
def gold_F4_axis(sp):
    cr = load(sp["path"]); ref = g.ref_instance(cr, sp["ref"])
    r = ring_by_labels(cr, ref, sp["ring"])
    aa = g.axis_angles(cr, r["normal"])
    ang = sorted(((aa[k], k) for k in "abc"))
    marg = (ang[1][0] - ang[0][0]) / ang[1][0]
    numeric = dict(angle_normal_a=round(aa["a"], 1), angle_normal_b=round(aa["b"], 1), angle_normal_c=round(aa["c"], 1),
                   ring_rms_dev=round(r["rms"], 3))
    # robust only if winner beats runner-up by >= 10 deg (and >= 5 % relative)
    return dict(axis=ang[0][1]), numeric, marg, (ang[1][0] - ang[0][0] < 10.0 or marg < FRAGILE)


def gold_F4_angle(sp):
    cr = load(sp["path"]); ref = g.ref_instance(cr, sp["ref"])
    r0, rows = same_ring_copies(cr, ref, sp["ring"])
    nn = rows[0]
    lab = next(b for b, lo, hi in ANG_BINS if lo <= nn["angle"] < hi)
    # next copy with a *different* angle bin must be clearly farther (>=5 %) than the nearest
    other = next((x for x in rows if next(b for b, lo, hi in ANG_BINS if lo <= x["angle"] < hi) != lab), None)
    gap = (other["cc"] - nn["cc"]) / nn["cc"] if other else 9.99
    ang_marg = min(abs(nn["angle"] - e) for e in (15.0, 45.0))
    marg = min(gap, ang_marg / 45.0)
    numeric = dict(nn_centroid_distance=round(nn["cc"], 3), interplanar_angle=round(nn["angle"], 1),
                   next_copy_with_other_bin=(other and dict(cc=round(other["cc"], 3), angle=round(other["angle"], 1))),
                   angle_margin_deg=round(ang_marg, 1))
    return dict(packing=lab), numeric, marg, (gap < FRAGILE or ang_marg < 5.0)


# ------------------------------------------------------------------ family 5
def gold_F5(sp):
    cr = load(sp["path"]); ref = g.ref_instance(cr, sp["ref"])
    r0, rows = same_ring_copies(cr, ref, sp["ring"])
    nn = rows[0]
    b = next(b for b, lo, hi in DIST_BINS if lo <= nn["cc"] < hi)
    if nn["angle"] >= PAR_ANG:
        t = "non_parallel"
    else:
        t = "face_to_face" if nn["offset"] < F2F_OFF else "offset_parallel"
    d_m = rel_margin(nn["cc"], [4.0, 5.0, 6.0])
    a_m = abs(nn["angle"] - PAR_ANG) / PAR_ANG
    o_m = abs(nn["offset"] - F2F_OFF) / F2F_OFF if t != "non_parallel" else 9.99
    def _cls(x):
        tt = "non_parallel" if x["angle"] >= PAR_ANG else ("face_to_face" if x["offset"] < F2F_OFF else "offset_parallel")
        return tt, next(bb for bb, lo, hi in DIST_BINS if lo <= x["cc"] < hi)
    other = next((x for x in rows if _cls(x) != (t, b)), None)  # nearest copy that would give a different answer
    gap = (other["cc"] - nn["cc"]) / nn["cc"] if other else 9.99
    marg = min(d_m, a_m, o_m, gap)
    numeric = dict(centroid_distance=round(nn["cc"], 3), interplanar_angle=round(nn["angle"], 1),
                   perpendicular_distance=round(nn["perp"], 2), lateral_offset=round(nn["offset"], 2),
                   nearest_copy_with_other_answer=(other and dict(cc=round(other["cc"], 3), angle=round(other["angle"], 1))),
                   relation=[x["kind"] for x in g.relation(cr, ref, nn["inst"])])
    return dict(distance_bin=b, stacking=t), numeric, marg, marg < FRAGILE


# ------------------------------------------------------------------ specs
# ccdc_local/* are CSD-derived (licensed, gitignored, anonymized ids); never commit them.
HX, BZ, UR = "data/structures/mck/mck_Acetaminophen_HXACAN.cif", "data/structures/cod/cod_4501702.cif", "data/structures/cod/cod_1008775.cif"
C24, CU = "data/structures/cod/cod_2224411.cif", "data/structures/cod/cod_2203991.cif"
C19, C03, C17 = "data/structures/cod/cod_2019279.cif", "data/structures/cod/cod_2003349.cif", "data/structures/cod/cod_2211700.cif"
S01, S02, S03, S04, S05, S06 = (f"data/structures/ccdc_local/ccdc_S0{i}.cif" for i in range(1, 7))
NAMES = {HX: "paracetamol form II (MolCrysKit example file, Pcab)", BZ: "benzene (COD, Pbca)", UR: "urea (COD, P-42_1m)",
         C24: "4-benzenesulfonamidobenzoic acid (COD, P2_1/c)",
         CU: "aqua[N-(2-hydroxy-5-nitrobenzyl)iminodiacetato]copper(II) (COD, P2_1/c)",
         C19: "10-ethynyl-10H-phenothiazine 5-oxide (COD, Pbcn)",
         C03: "2-methyl-2-(2-methylphenylazo)-1,3-indandione (COD, P2_1/a)",
         C17: "N,N'-bis(4-chlorobenzylidene)propane-1,2-diamine (COD, P-1)",
         S01: "small aromatic carboxylic acid with an ester substituent (CSD-derived, P2_1/c)",
         S02: "pyridinecarboxylic acid (CSD-derived, P2_1/c)",
         S03: "primary aromatic amide (CSD-derived, P2_1/c)",
         S04: "methoxy-indole alkyl amide (CSD-derived, P2_1/c)",
         S05: "tricyclic aromatic carboxamide (CSD-derived, P2_1/n)",
         S06: "hydroxycoumarin-type drug molecule (CSD-derived, P2_12_12_1)"}
SPECS = [
    dict(fam="F1", path=HX, ref="O1", D="O1", H="H5"),
    dict(fam="F1", path=S01, ref="C1", D=None, H="H8"),
    dict(fam="F1", path=S02, ref="C1", D=None, H="H5"),
    dict(fam="F1", path=S03, ref="N1", D=None, H="H7"),
    dict(fam="F2", path=S04, ref="C1"),
    dict(fam="F2", path=C24, ref="O5"),
    dict(fam="F2", path=UR, ref="C1"),
    dict(fam="F2", path=S05, ref="C1"),
    dict(fam="F3", path=BZ, ref="C1", cutoff=3.5, gold_pos=2),
    dict(fam="F3", path=CU, ref="Cu1", cutoff=3.5, gold_pos=4),
    dict(fam="F3", path=S05, ref="C1", cutoff=4.0, gold_pos=1),
    dict(fam="F3", path=S02, ref="C1", cutoff=3.0, gold_pos=3),
    dict(fam="F4", kind="axis", path=C19, ref="S1", ring=["C7", "C8", "C9", "C10", "C11", "C12"]),
    dict(fam="F4", kind="axis", path=C03, ref="O1", ring=["C1'", "C2'", "C3'", "C4'", "C5'", "C6'"]),
    dict(fam="F4", kind="axis", path=S06, ref="C1", ring=["C1", "C15", "C16", "C17", "C18", "C19"]),
    dict(fam="F4", kind="angle", path=BZ, ref="C1", ring=["C1", "C2", "C3", "C1", "C2", "C3"]),
    dict(fam="F5", path=C19, ref="S1", ring=["C1", "C2", "C3", "C4", "C5", "C6"]),
    dict(fam="F5", path=HX, ref="O1", ring=["C1", "C2", "C3", "C4", "C5", "C6"]),
    dict(fam="F5", path=C17, ref="C1", ring=["C9", "C10", "C11", "C12", "C13", "C14"]),
    dict(fam="F5", path=S06, ref="C1", ring=["C1", "C15", "C16", "C17", "C18", "C19"]),
]
F1_W = {"acceptor_label": 0.3, "relation": 0.7}
F5_W = {"distance_bin": 0.5, "stacking": 0.5}

HARD = {
    "F1": "The CIF lists only the asymmetric unit; the acceptor sits in a symmetry-generated molecule, so the model must apply every symmetry operation plus lattice translations to candidate N/O atoms, compute H...A distances in a non-orthogonal metric, and then classify the operation (rotation part + intrinsic translation) that maps the molecules.",
    "F2": "No H-bond list is given in the CIF; the model must find all intermolecular D-H...A contacts across symmetry copies and then track which lattice translations the closed H-bond paths accumulate (periodic-graph rank) to get 0D/1D/2D/3D and the propagation direction.",
    "F3": "Requires generating all symmetry/translation images around one molecule and computing hundreds of interatomic distances in the cell metric, then de-duplicating by molecule; nothing in the CIF text states contact counts.",
    "F4": "Requires converting fractional to Cartesian coordinates, fitting a ring plane and comparing its normal with the lattice vectors (or with the symmetry-rotated plane of a neighbouring molecule); not stated anywhere in the CIF.",
    "F5": "Requires locating the nearest symmetry-equivalent copy of a ring (over all operations and translations), then computing centroid distance, interplanar angle and lateral offset in Cartesian space.",
}


# ------------------------------------------------------------------ question text
def ring_txt(r):
    return "the ring formed by atoms " + ", ".join(dict.fromkeys(r)) + (
        " (a six-membered ring; labels repeat because half of the ring is generated by symmetry)" if len(set(r)) < len(r) else "")


def build(sp, idx):
    fam, cr = sp["fam"], load(sp["path"])
    ref = REF_TXT.format(ref=sp["ref"])
    heavy = sorted({l for l, e in zip(cr.labels, cr.elems) if e in ("N", "O")})
    if fam == "F1":
        gold, num, marg, frag = gold_F1(sp)
        if not sp.get("D"):
            sp = dict(sp, D=num["donor"])
        q = (f"{ref}\nAtom {sp['D']} of the reference molecule donates a hydrogen bond through its hydrogen atom {sp['H']} "
             f"to an N or O acceptor atom of a DIFFERENT molecule (the acceptor is the N/O atom of any other molecule "
             f"with the shortest {sp['H']}...acceptor distance). (1) Give the atom label of the acceptor (as written in the CIF). "
             f"(2) Which kind of space-group symmetry operation maps the reference molecule onto the acceptor molecule? "
             f"Choose one of: {', '.join(REL_OPTIONS)} (a pure lattice translation counts as 'translation'; "
             f"a rotation or mirror combined with a non-lattice translation along the axis/plane is '2_1 screw' or 'glide').\n"
             f'Answer with JSON only: {{"acceptor_label": "<atom label>", "relation": "<one of the listed options>"}}')
        opts = dict(acceptor_label=f"any atom label of the structure (N/O candidates: {heavy})", relation=REL_OPTIONS)
        nl = len(heavy)
        chance = dict(exact=round(1 / (nl * len(REL_OPTIONS)), 4),
                      weighted_expected=round(F1_W["acceptor_label"] / nl + F1_W["relation"] / len(REL_OPTIONS), 4),
                      note=f"label chance taken over the {nl} N/O atoms of the asymmetric unit")
        metric = "weighted: 0.3 x acceptor_label exact + 0.7 x relation exact (crystalsight.score_v3); strict exact match also reported"
        how = "Shortest intermolecular H...A (A in N,O; D-H...A >= 120 deg) from the given H over all symmetry/translation images; the mapping operation found by matching all labelled atoms of the two molecules, classified by rotation part and intrinsic translation (W+I)t/2."
    elif fam == "F2":
        gold, num, marg, frag = gold_F2(sp)
        q = (f"Consider the intermolecular hydrogen-bond network of this crystal. Count an H-bond D-H...A when D and A are N or O, "
             f"the H atom is covalently bonded to D, H...A <= {HB_HA:.2f} A and the D-H...A angle >= {HB_ANG:.0f} deg, and D and A "
             f"belong to different molecules. Treat every molecule as a node and every such H-bond as an edge, in the infinite crystal. "
             f"What is the dimensionality of the connected H-bonded aggregates, and along which lattice direction(s) do they extend? "
             f"Options: 0D (finite clusters, e.g. dimers), 1D_a / 1D_b / 1D_c (infinite chains running along a, b or c), "
             f"1D_other (chains along another direction), 2D_ab / 2D_ac / 2D_bc (infinite layers parallel to that lattice plane), "
             f"2D_other (layers parallel to another plane), 3D (a framework).\n"
             f'Answer with JSON only: {{"network": "<one of {"|".join(DIM_OPTIONS)}>"}}')
        opts = dict(network=DIM_OPTIONS)
        chance = dict(exact=round(1 / len(DIM_OPTIONS), 4))
        metric = "exact match"
        how = "Periodic quotient graph of molecules with the stated H-bond criteria; dimensionality = rank of the lattice translations accumulated around closed paths; direction from the shortest generating vectors (1D) or their cross product (2D)."
    elif fam == "F3":
        gold, num, marg, frag, letters = gold_F3(sp)
        q = (f"{ref}\nHow many distinct OTHER molecules have at least one atom (hydrogen atoms included, at the positions given in "
             f"the CIF) closer than {sp['cutoff']:.2f} A to at least one atom of the reference molecule? Count every symmetry- or "
             f"translation-generated copy as a separate molecule.\n"
             + "Options: " + "; ".join(f"{k}) {v}" for k, v in letters.items()) +
             f'\nAnswer with JSON only: {{"answer": "<A|B|C|D|E>"}}')
        opts = dict(answer=letters)
        chance = dict(exact=0.2)
        metric = "exact match"
        how = f"Minimum interatomic distance between the reference molecule and every molecule image within +-2 cells; count those < {sp['cutoff']} A."
    elif fam == "F4" and sp["kind"] == "axis":
        gold, num, marg, frag = gold_F4_axis(sp)
        q = (f"{ref}\nConsider {ring_txt(sp['ring'])} in the reference molecule. Which unit-cell axis (the direct lattice vectors "
             f"a, b, c) makes the smallest angle with the normal to the mean plane of that ring?\n"
             f'Answer with JSON only: {{"axis": "<a|b|c>"}}')
        opts = dict(axis=["a", "b", "c"]); chance = dict(exact=round(1 / 3, 4)); metric = "exact match"
        how = "Least-squares plane of the ring atoms (SVD) in Cartesian coordinates; acute angle of the plane normal to each direct lattice vector."
    elif fam == "F4":
        gold, num, marg, frag = gold_F4_angle(sp)
        q = (f"{ref}\nConsider {ring_txt(sp['ring'])}. Among all OTHER molecules, take the copy of this same ring whose centroid is "
             f"closest to the centroid of the reference molecule's ring. What is the acute angle between the two ring planes? "
             f"Options: parallel (< 15 deg), inclined (15-45 deg), herringbone_T (> 45 deg, edge-to-face / herringbone).\n"
             f'Answer with JSON only: {{"packing": "<parallel|inclined|herringbone_T>"}}')
        opts = dict(packing=[b for b, _, _ in ANG_BINS]); chance = dict(exact=round(1 / 3, 4)); metric = "exact match"
        how = "Nearest symmetry copy of the ring by centroid-centroid distance; acute angle between least-squares ring normals."
    else:
        gold, num, marg, frag = gold_F5(sp)
        q = (f"{ref}\nConsider {ring_txt(sp['ring'])}. Among all OTHER molecules, find the copy of this same ring whose centroid is "
             f"closest to the centroid of the reference molecule's ring. (1) Centroid-centroid distance bin: lt4.0 (< 4.0 A), "
             f"4.0-5.0, 5.0-6.0, gt6.0 (> 6.0 A). (2) Stacking geometry of that pair: face_to_face (interplanar angle < 15 deg and "
             f"lateral offset < 1.5 A), offset_parallel (angle < 15 deg, offset >= 1.5 A), non_parallel (angle >= 15 deg). The lateral "
             f"offset is the component of the centroid-centroid vector parallel to the reference ring plane.\n"
             f'Answer with JSON only: {{"distance_bin": "<lt4.0|4.0-5.0|5.0-6.0|gt6.0>", "stacking": "<face_to_face|offset_parallel|non_parallel>"}}')
        opts = dict(distance_bin=[b for b, _, _ in DIST_BINS], stacking=STACK_TYPES)
        chance = dict(exact=round(1 / 12, 4), weighted_expected=round(0.5 / 4 + 0.5 / 3, 4))
        metric = "weighted: 0.5 x distance_bin exact + 0.5 x stacking exact (crystalsight.score_v3); strict exact match also reported"
        how = "Nearest symmetry copy of the same ring by centroid distance; interplanar angle from SVD normals; offset = sqrt(d^2 - (d.n)^2)."
    sid = Path(sp["path"]).stem
    return dict(id=f"v3_{fam}_{idx:02d}_{sid}", family=fam, structure_id=sid, structure_name=NAMES[sp["path"]],
                path=sp["path"], ref_atom=sp["ref"], question=q,
                options=opts, gold=gold, score_weights=({"F1": F1_W, "F5": F5_W}.get(fam) or {k: 1.0 / len(gold) for k in gold}), gold_method=how, numeric=num, margin=round(float(marg), 4),
                fragile=bool(frag), metric=metric, chance=chance, why_hard_from_cif_text=HARD[fam],
                space_group_ops=len(cr.ops), molecules_in_cell=len(cr.mols),
                h_atoms_present=any(e == "H" for e in cr.elems),
                disorder_present=bool(any(o < 0.999 for o in cr.occ) or any(x not in (".", "0") for x in cr.dgroup)),
                licensed_source=("CSD-derived (local only, not redistributable)" if "ccdc_local" in sp["path"] else None))


# ------------------------------------------------------------------ runner fields
QTYPE = {"F1": "v3_F1_symrel", "F2": "v3_F2_hbnet", "F3": "v3_F3_neighbors", "F4": "v3_F4_orientation", "F5": "v3_F5_stacking"}
# TUI scene per family: copy-aware labels + axis triad always; periodic images grown around the cell
# (mat-vis load-time transform) wherever the answer involves a neighbouring molecule.
TUI_GROW = {"F1": 3.0, "F2": 3.0, "F3": 3.0, "F4": 3.0, "F5": 3.0}


def runner_fields(t):
    """Fields the crystalsight runner / channels / scorer need (benchmark, qtype, answer schema, TUI scene)."""
    schema = {}
    for k in t["gold"]:
        o = t["options"][k]
        if isinstance(o, dict):
            schema[k] = {"type": "choice", "options": list(o)}
        elif isinstance(o, list):
            schema[k] = {"type": "choice", "options": list(o)}
        else:  # free atom label; candidates only feed the mock model
            schema[k] = {"type": "label", "hint": "atom label as written in the CIF", "candidates": t["numeric"].get("candidates")
                         or sorted(set(str(o).split("[", 1)[1].rstrip(")]").replace("'", "").replace(" ", "").split(",")))}
    grow = TUI_GROW.get(t["family"])
    if t["family"] == "F4" and t["id"] and "axis" in t["gold"]:
        grow = None  # orientation of the reference ring only: the plain unit cell is enough
    tui = {"label_mode": "label_sym", "display_level": "atom", "show_axes": True}
    if grow:
        tui["grow_radius"] = grow
    return dict(benchmark="v3", qtype=QTYPE[t["family"]], answer_type="object", schema=schema, tui=tui)


# ------------------------------------------------------------------ main
def _json(o):
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def _short(num):
    keep = {k: v for k, v in num.items() if k not in ("min_contact_per_molecule",)}
    return json.dumps(keep, default=_json)


def main():
    OUT.mkdir(exist_ok=True)
    tasks = []
    counters = {}
    vf = OUT / "tui_check" / "tui_verdicts.json"  # written by the manual TUI feasibility check
    verdicts = json.loads(vf.read_text(encoding="utf-8")) if vf.exists() else {}
    for sp in SPECS:
        counters[sp["fam"]] = counters.get(sp["fam"], 0) + 1
        t = build(sp, counters[sp["fam"]])
        t.update(runner_fields(t))
        if t["id"] in verdicts:
            t["tui_feasibility"] = dict(verdict=verdicts[t["id"]][0], reason=verdicts[t["id"]][1])
        tasks.append(t)
        print(t["id"], json.dumps(t["gold"]), "margin", t["margin"], "FRAGILE" if t["fragile"] else "ok", flush=True)
    with open(OUT / "tasks_v3.jsonl", "w", encoding="utf-8") as f:
        for t in tasks:
            f.write(json.dumps(t, default=_json, ensure_ascii=False) + "\n")
    md = ["# CrystalSight v3 - 3D spatial-reasoning tasks", "",
          "Generated by `scripts/make_tasks_v3.py` (geometry in `crystalsight/gt_spatial.py`; numpy + pymatgen CIF parser + ASE radii; no model calls).",
          f"{len(tasks)} questions, {len({t['structure_id'] for t in tasks})} structures. Fragility rule: an answer is fragile when the deciding quantity is within 5 % of a threshold/bin edge (or, for categorical choices, the runner-up is within 5 % / 10 deg).", "",
          "| id | family | structure | path | gold | key numeric | margin | fragile | metric | chance (exact) | TUI |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for t in tasks:
        md.append(f"| {t['id']} | {t['family']} | {t['structure_name']} | `{t['path']}` | `{json.dumps(t['gold'])}` | "
                  f"{_short(t['numeric']).replace('|', '/')} | {t['margin']} | {t['fragile']} | {t['metric'].split(';')[0]} | {t['chance']['exact']} | {t.get('tui_feasibility', {}).get('verdict', '-')} |")
    md += ["", "## Question texts", ""]
    for t in tasks:
        md += [f"### {t['id']}", "", f"Structure: {t['structure_name']}  ", f"File: `{t['path']}`", "",
               "```text", t["question"], "```", "", f"- Options: `{json.dumps(t['options'], ensure_ascii=False)}`",
               f"- Gold: `{json.dumps(t['gold'])}`", f"- Gold method: {t['gold_method']}",
               f"- Key numbers: `{_short(t['numeric'])}`", f"- Margin: {t['margin']} (fragile: {t['fragile']})",
               f"- Metric: {t['metric']}; chance: `{json.dumps(t['chance'])}`",
               f"- Why raw CIF text is hard: {t['why_hard_from_cif_text']}",
               f"- TUI feasibility: {t.get('tui_feasibility', {}).get('verdict', '-')} - {t.get('tui_feasibility', {}).get('reason', '')}", ""]
    (OUT / "TASKS_v3.md").write_text("\n".join(md), encoding="utf-8")
    print("wrote", OUT / "tasks_v3.jsonl", "and TASKS_v3.md;", sum(t["fragile"] for t in tasks), "fragile")


if __name__ == "__main__":
    main()
