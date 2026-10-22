"""Deterministic 3D-geometry ground truth for CrystalSight v3 spatial tasks.

Pure geometry on the expanded crystal (numpy + pymatgen CIF tokenizer + ASE radii).
No MolCrysKit feature is used to define any answer.

Conventions
- Symmetry operations are read verbatim from the CIF (x,y,z first).
- "Reference molecule" = the molecule containing atom <label> at exactly the
  fractional coordinates listed in the CIF.
- Molecule instances are (cell-molecule index m, integer lattice shift S).
"""
from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field

import numpy as np
from ase.data import atomic_numbers, covalent_radii, vdw_radii
from pymatgen.core import Lattice
from pymatgen.core.operations import SymmOp
from pymatgen.io.cif import CifFile

BOND_TOL = 0.45  # A added to sum of covalent radii (0.30 for X-H)
HB_DONORS = {"N", "O"}
HB_ACCEPTORS = {"N", "O"}  # conventional strong-H-bond acceptors used in all v3 prompts


def _num(s: str) -> float:
    s = s.strip()
    if s in ("?", "."):
        return float("nan")
    return float(re.sub(r"\(.*?\)", "", s))


def _elem(label: str, typ) -> str:
    src = typ if typ and typ not in ("?", ".") else label
    m = re.match(r"([A-Z][a-z]?)", src)
    e = m.group(1)
    if e not in atomic_numbers:
        e = e[0]
    return e


@dataclass
class Crystal:
    name: str
    lattice: Lattice
    ops: list  # (W 3x3 int, w 3 float, xyz str)
    labels: list
    elems: list
    frac_asym: np.ndarray
    occ: np.ndarray
    dgroup: list
    c_label: list = field(default_factory=list)
    c_elem: list = field(default_factory=list)
    c_frac: np.ndarray = None
    c_asym: list = field(default_factory=list)
    c_op: list = field(default_factory=list)
    mols: list = field(default_factory=list)
    mol_of: np.ndarray = None
    img_of: np.ndarray = None
    polymeric: list = field(default_factory=list)
    adj: list = None

    @property
    def M(self):
        return self.lattice.matrix  # rows = a, b, c in Cartesian


def load(path, name=None) -> Crystal:
    cf = CifFile.from_file(str(path))
    blk = next(b for b in cf.data.values() if "_atom_site_fract_x" in b.data)
    d = blk.data
    pars = [_num(d[k]) for k in ("_cell_length_a", "_cell_length_b", "_cell_length_c",
                                 "_cell_angle_alpha", "_cell_angle_beta", "_cell_angle_gamma")]
    lat = Lattice.from_parameters(*pars)
    xyzs = next((d[k] for k in ("_symmetry_equiv_pos_as_xyz", "_space_group_symop_operation_xyz") if k in d), None)
    if xyzs is None:
        raise ValueError("no explicit symmetry operations in CIF")
    if isinstance(xyzs, str):
        xyzs = [xyzs]
    ops = []
    for s in xyzs:
        s = s.strip().strip("'\"")
        op = SymmOp.from_xyz_str(s.replace(" ", ""))
        ops.append((np.rint(op.rotation_matrix).astype(int), np.array(op.translation_vector, float), s))
    labels = list(d["_atom_site_label"])
    types = d.get("_atom_site_type_symbol", [None] * len(labels))
    elems = [_elem(l, t) for l, t in zip(labels, types)]
    frac = np.array([[_num(x) for x in d[k]] for k in ("_atom_site_fract_x", "_atom_site_fract_y", "_atom_site_fract_z")]).T
    occ = np.array([1.0 if x in ("?", ".") else _num(x) for x in d.get("_atom_site_occupancy", ["1"] * len(labels))])
    dg = list(d.get("_atom_site_disorder_group", ["."] * len(labels)))
    cr = Crystal(name or str(path), lat, ops, labels, elems, frac, occ, dg)
    _expand(cr)
    _molecules(cr)
    return cr


def _expand(cr: Crystal, tol=0.08):
    fr, lab, el, ai, oi = [], [], [], [], []
    for i, x in enumerate(cr.frac_asym):
        for k, (W, w, _) in enumerate(cr.ops):
            f = W @ x + w
            f0 = f - np.floor(f + 1e-9)
            dup = False
            for j in range(len(fr)):
                if ai[j] != i:
                    continue
                df = f0 - fr[j]
                df -= np.rint(df)
                if np.linalg.norm(df @ cr.M) < tol:
                    dup = True
                    break
            if not dup:
                fr.append(f0); lab.append(cr.labels[i]); el.append(cr.elems[i]); ai.append(i); oi.append(k)
    cr.c_frac = np.array(fr); cr.c_label = lab; cr.c_elem = el; cr.c_asym = ai; cr.c_op = oi


IMAGES = np.array(list(itertools.product((-1, 0, 1), repeat=3)))


def _rcov(e):
    return covalent_radii[atomic_numbers[e]]


def _molecules(cr: Crystal):
    F = cr.c_frac
    n = len(F)
    rc = np.array([_rcov(e) for e in cr.c_elem])
    isH = np.array([e == "H" for e in cr.c_elem])
    dg = [cr.dgroup[a] for a in cr.c_asym]
    adj = [[] for _ in range(n)]
    for t in IMAGES:
        D = np.linalg.norm((F[None, :, :] + t[None, None, :] - F[:, None, :]) @ cr.M, axis=2)
        tol = np.where(isH[:, None] | isH[None, :], 0.30, BOND_TOL)
        B = (D < rc[:, None] + rc[None, :] + tol) & (D > 0.3) & ~(isH[:, None] & isH[None, :])
        for i, j in zip(*np.where(B)):
            if dg[i] not in (".", "0") and dg[j] not in (".", "0") and dg[i] != dg[j]:
                continue
            adj[i].append((int(j), t.copy()))
    cr.adj = adj
    mol_of = -np.ones(n, int); img = np.zeros((n, 3), int); mols, poly = [], []
    for s in range(n):
        if mol_of[s] >= 0:
            continue
        m = len(mols); mol_of[s] = m; stack, members, loops = [s], [s], []
        while stack:
            i = stack.pop()
            for j, t in adj[i]:
                if mol_of[j] < 0:
                    mol_of[j] = m; img[j] = img[i] + t; stack.append(j); members.append(j)
                else:
                    lv = img[i] + t - img[j]
                    if lv.any():
                        loops.append(lv)
        mols.append(sorted(members))
        poly.append(int(np.linalg.matrix_rank(np.array(loops))) if loops else 0)
    cr.mols, cr.mol_of, cr.img_of, cr.polymeric = mols, mol_of, img, poly


# ---------------------------------------------------------------- molecule instances
def mol_frac(cr, m, S):
    idx = cr.mols[m]
    return idx, cr.c_frac[idx] + cr.img_of[idx] + np.asarray(S)


def ref_instance(cr, label):
    """Molecule instance containing `label` at its CIF coordinates (operation x,y,z, no shift)."""
    i_asym = cr.labels.index(label)
    for a in range(len(cr.c_frac)):
        if cr.c_asym[a] == i_asym and cr.c_op[a] == 0:
            S = np.rint(cr.frac_asym[i_asym] - cr.c_frac[a] - cr.img_of[a]).astype(int)
            return int(cr.mol_of[a]), S
    raise KeyError(label)


def same(i0, i1):
    return i0[0] == i1[0] and np.array_equal(np.asarray(i0[1]), np.asarray(i1[1]))


def neighbor_molecules(cr, inst0, cutoff=6.0, heavy_only=False, rng=2):
    """[(min interatomic distance, m, S)] for every other molecule instance closer than cutoff."""
    i0, F0 = mol_frac(cr, *inst0)
    if heavy_only:
        F0 = F0[[k for k, a in enumerate(i0) if cr.c_elem[a] != "H"]]
    C0 = F0 @ cr.M
    lo, hi = C0.min(0) - cutoff, C0.max(0) + cutoff
    out = []
    for m in range(len(cr.mols)):
        i1, F1b = mol_frac(cr, m, (0, 0, 0))
        if heavy_only:
            F1b = F1b[[k for k, a in enumerate(i1) if cr.c_elem[a] != "H"]]
        for S in itertools.product(range(-rng, rng + 1), repeat=3):
            S = np.array(S)
            if m == inst0[0] and np.array_equal(S, np.asarray(inst0[1])):
                continue
            C1 = (F1b + S) @ cr.M
            if (C1.max(0) < lo).any() or (C1.min(0) > hi).any():
                continue
            d = float(np.linalg.norm(C1[None] - C0[:, None], axis=2).min())
            if d < cutoff:
                out.append((d, m, S))
    return sorted(out, key=lambda x: x[0])


# ---------------------------------------------------------------- symmetry relation between two molecules
def relation(cr, inst0, inst1, tol=0.15):
    i0, F0 = mol_frac(cr, *inst0)
    i1, F1 = mol_frac(cr, *inst1)
    L0 = [cr.c_label[a] for a in i0]
    L1 = [cr.c_label[a] for a in i1]
    found = []
    for k, (W, w, s) in enumerate(cr.ops):
        G = (W @ F0.T).T + w
        t, ok = None, True
        for p, lab in zip(G, L0):
            best = None
            for q, l in enumerate(L1):
                if l != lab:
                    continue
                tt = np.rint(F1[q] - p)
                if np.linalg.norm((F1[q] - p - tt) @ cr.M) < tol:
                    best = tt
                    break
            if best is None or (t is not None and (best != t).any()):
                ok = False
                break
            t = best
        if ok:
            found.append(dict(op=k + 1, xyz=s, t=t.astype(int).tolist(), **classify(W, w + t)))
    return found


def classify(W, wt):
    W = np.asarray(W); wt = np.asarray(wt, float)
    det = int(round(np.linalg.det(W))); tr = int(np.trace(W)); I = np.eye(3, dtype=int)
    if (W == I).all():
        return dict(kind="translation" if np.abs(wt).sum() > 1e-6 else "identity", intrinsic=wt.tolist())
    if (W == -I).all():
        return dict(kind="inversion", intrinsic=[0.0, 0.0, 0.0])
    if det == 1 and tr == -1:
        tau = (W + I) @ wt / 2
        if np.abs(tau - np.rint(tau)).max() < 1e-6:
            kind = "2-fold rotation" if np.abs(tau).max() < 1e-6 else "2-fold rotation+lattice translation"
        else:
            kind = "2_1 screw"
        return dict(kind=kind, intrinsic=tau.tolist())
    if det == -1 and tr == 1:
        tau = (W + I) @ wt / 2
        if np.abs(tau - np.rint(tau)).max() < 1e-6:
            kind = "mirror" if np.abs(tau).max() < 1e-6 else "mirror+lattice translation"
        else:
            kind = "glide"
        return dict(kind=kind, intrinsic=tau.tolist())
    return dict(kind=f"other(det={det},tr={tr})", intrinsic=None)


# ---------------------------------------------------------------- hydrogen bonds
def hbonds(cr, inst0, ha_max=2.9, ang_min=100.0):
    """All D-H...A (D in N,O; H bonded to D) from inst0 to acceptors in OTHER molecule instances."""
    i0, F0 = mol_frac(cr, *inst0)
    C0 = F0 @ cr.M
    pos0 = {a: k for k, a in enumerate(i0)}
    neigh = neighbor_molecules(cr, inst0, cutoff=ha_max + 0.1)
    res = []
    for k, a in enumerate(i0):
        if cr.c_elem[a] != "H":
            continue
        dk = [pos0[j] for j, t in cr.adj[a] if cr.c_elem[j] in HB_DONORS and j in pos0]
        if not dk:
            continue
        D, H = C0[dk[0]], C0[k]
        for _, m, S in neigh:
            i1, F1 = mol_frac(cr, m, S)
            C1 = F1 @ cr.M
            for q, b in enumerate(i1):
                if cr.c_elem[b] not in HB_ACCEPTORS:
                    continue
                ha = float(np.linalg.norm(C1[q] - H))
                if ha > ha_max:
                    continue
                v1, v2 = D - H, C1[q] - H
                ang = float(np.degrees(np.arccos(np.clip(np.dot(v1, v2) / np.linalg.norm(v1) / np.linalg.norm(v2), -1, 1))))
                if ang < ang_min:
                    continue
                res.append(dict(D=cr.c_label[i0[dk[0]]], H=cr.c_label[a], A=cr.c_label[b], HA=round(ha, 3),
                                DA=round(float(np.linalg.norm(C1[q] - D)), 3), angle=round(ang, 1),
                                inst=(int(m), [int(x) for x in S])))
    return sorted(res, key=lambda r: r["HA"])


def hbond_network(cr, ha_max=2.5, ang_min=120.0):
    """Periodic quotient graph (vertices = molecules in the cell, edges = H-bonds with
    H...A <= ha_max and D-H...A >= ang_min).  Dimensionality = rank of cycle translation vectors."""
    nm = len(cr.mols)
    edges, cands = [], []
    for m in range(nm):
        for h in hbonds(cr, (m, np.zeros(3, int))):
            cands.append(h)
            if h["HA"] <= ha_max and h["angle"] >= ang_min:
                edges.append((m, h["inst"][0], np.array(h["inst"][1])))
    adj = [[] for _ in range(nm)]
    for u, v, S in edges:
        adj[u].append((v, S)); adj[v].append((u, -S))
    seen = -np.ones(nm, int); img = np.zeros((nm, 3), int); comps = []
    for s in range(nm):
        if seen[s] >= 0:
            continue
        seen[s] = s; st = [s]; lp = []; members = [s]
        while st:
            u = st.pop()
            for v, S in adj[u]:
                if seen[v] < 0:
                    seen[v] = s; img[v] = img[u] + S; st.append(v); members.append(v)
                else:
                    l = img[u] + S - img[v]
                    if l.any():
                        lp.append(l)
        r = int(np.linalg.matrix_rank(np.array(lp))) if lp else 0
        comps.append(dict(members=members, dim=r, basis=_short_basis(lp) if lp else []))
    return dict(dims=sorted({c["dim"] for c in comps}), components=comps, n_edges=len(edges), candidates=cands)


def _short_basis(vecs):
    V = sorted({tuple(int(x) for x in (v if next(x for x in v if x) > 0 else -v)) for v in vecs},
               key=lambda v: (np.abs(v).sum(), v))
    basis = []
    for v in V:
        if np.linalg.matrix_rank(np.array(basis + [list(v)])) > len(basis):
            basis.append(list(v))
    return basis


# ---------------------------------------------------------------- rings / planes
def rings(cr, inst, sizes=(5, 6), planar_rms=0.1):
    import networkx as nx
    idx, F = mol_frac(cr, *inst)
    C = F @ cr.M
    pos = {a: k for k, a in enumerate(idx)}
    g = nx.Graph()
    for a in idx:
        if cr.c_elem[a] == "H":
            continue
        for j, t in cr.adj[a]:
            if j in pos and cr.c_elem[j] != "H" and np.array_equal(cr.img_of[a] + t, cr.img_of[j]):
                g.add_edge(a, j)
    out = []
    for cyc in nx.minimum_cycle_basis(g):
        if len(cyc) not in sizes:
            continue
        sub = g.subgraph(cyc)
        order = [min(cyc, key=lambda a: cr.c_label[a])]
        while len(order) < len(cyc):
            order.append(next(x for x in sub.neighbors(order[-1]) if x not in order))
        P = C[[pos[a] for a in order]]
        cen = P.mean(0)
        nrm = np.linalg.svd(P - cen)[2][2]
        rms = float(np.sqrt(np.mean(((P - cen) @ nrm) ** 2)))
        if rms <= planar_rms:
            out.append(dict(labels=[cr.c_label[a] for a in order], centroid=cen, normal=nrm, rms=rms))
    return out


def acute(n1, n2):
    c = abs(float(np.dot(n1, n2)) / np.linalg.norm(n1) / np.linalg.norm(n2))
    return float(np.degrees(np.arccos(min(1.0, c))))


def axis_angles(cr, n):
    """Acute angles (deg) between a plane normal and the direct axes a,b,c and reciprocal a*,b*,c*."""
    out = {k: acute(n, v) for k, v in zip("abc", cr.M)}
    R = cr.lattice.reciprocal_lattice_crystallographic.matrix
    out.update({k: acute(n, v) for k, v in zip(("a*", "b*", "c*"), R)})
    return out


# ======================================================================== v4 (tasks_v4/): copy-aware labels,
# H-bond graphs over molecule instances, centroid shells, ordered disorder replicas.
# Copy-aware label convention = MatterVis TUI label_sym: <site>#<k>[i,j,k], k = 1-based CIF operation that
# generated the copy (omitted for k=1), [i,j,k] = lattice shift from that copy wrapped into [0,1) (omitted if 0).
def copy_label(cr, a, S=(0, 0, 0)):
    n = cr.img_of[a] + np.asarray(S, int)
    s = cr.c_label[a] + ("" if cr.c_op[a] == 0 else f"#{cr.c_op[a] + 1}")
    return s + ("" if not n.any() else "[%d,%d,%d]" % tuple(int(x) for x in n))


def home_atom(cr, label):
    """Expanded index of the home copy of <label> (operation 1, wrapped into [0,1)) and its molecule instance."""
    W, w, _ = cr.ops[0]
    if not ((np.asarray(W) == np.eye(3, dtype=int)).all() and np.abs(w).max() < 1e-9):
        raise ValueError("first CIF operation is not x,y,z")
    i = cr.labels.index(label)
    a = next(a for a in range(len(cr.c_frac)) if cr.c_asym[a] == i and cr.c_op[a] == 0)
    return a, (int(cr.mol_of[a]), -cr.img_of[a].astype(int))


def hb_contacts(cr, inst0, ha_max=2.9, ang_min=100.0):
    """Intermolecular D-H...A (D, A in N/O) donated by inst0, with expanded atom indices and copy-aware labels."""
    i0, F0 = mol_frac(cr, *inst0)
    C0 = F0 @ cr.M
    pos0 = {a: k for k, a in enumerate(i0)}
    out = []
    neigh = neighbor_molecules(cr, inst0, cutoff=ha_max + 0.1)
    for k, a in enumerate(i0):
        if cr.c_elem[a] != "H":
            continue
        dk = [pos0[j] for j, t in cr.adj[a] if cr.c_elem[j] in HB_DONORS and j in pos0]
        if not dk:
            continue
        D, H = C0[dk[0]], C0[k]
        for _, m, S in neigh:
            i1, F1 = mol_frac(cr, m, S)
            C1 = F1 @ cr.M
            for q, b in enumerate(i1):
                if cr.c_elem[b] not in HB_ACCEPTORS:
                    continue
                ha = float(np.linalg.norm(C1[q] - H))
                if ha > ha_max:
                    continue
                v1, v2 = D - H, C1[q] - H
                ang = float(np.degrees(np.arccos(np.clip(np.dot(v1, v2) / np.linalg.norm(v1) / np.linalg.norm(v2), -1, 1))))
                if ang < ang_min:
                    continue
                out.append(dict(h=int(a), d=int(i0[dk[0]]), b=int(b), inst=(int(m), np.asarray(S, int)), HA=ha,
                                DA=float(np.linalg.norm(C1[q] - D)), angle=ang,
                                h_label=copy_label(cr, a, inst0[1]), a_label=copy_label(cr, b, S)))
    return sorted(out, key=lambda r: r["HA"])


def hb_graph(cr, ha_max=2.5, ang_min=120.0):
    """Undirected molecule-level H-bond graph: m -> [(m2, S2, record)] for the instance (m, 0)."""
    E = {m: [] for m in range(len(cr.mols))}
    for m in range(len(cr.mols)):
        for h in hb_contacts(cr, (m, np.zeros(3, int)), ha_max=ha_max, ang_min=ang_min):
            m2, S2 = h["inst"]
            E[m].append((m2, S2, h))
            E[m2].append((m, -S2, h))
    return E


def hb_hops(cr, inst0, inst1, E, max_depth=12):
    """Minimum number of H-bonds on a path of molecules from inst0 to inst1 (None if not connected within max_depth)."""
    from collections import deque
    s0 = (inst0[0], tuple(int(x) for x in inst0[1]))
    s1 = (inst1[0], tuple(int(x) for x in inst1[1]))
    seen, q = {s0: 0}, deque([s0])
    while q:
        u = q.popleft()
        if u == s1:
            return seen[u]
        if seen[u] >= max_depth:
            continue
        for m2, S2, _ in E[u[0]]:
            v = (m2, tuple(int(x) for x in np.asarray(u[1]) + S2))
            if v not in seen:
                seen[v] = seen[u] + 1
                q.append(v)
    return None


def hb_ring(cr, h_label, a_label, ha_max=2.5, ang_min=120.0, depth=4):
    """Smallest closed H-bond ring (graph-set R) through the H-bond <home copy of h_label> ... <acceptor copy a_label>.
    Atom graph = covalent bonds + H...A bonds over all molecule instances within <depth> H-bond hops of the
    reference.  Returns dict(ring_size, n_molecules, n_hbonds, n_acceptors, alternatives) or None."""
    import networkx as nx
    from collections import deque
    E = hb_graph(cr, ha_max, ang_min)
    h, inst0 = home_atom(cr, h_label)
    s0 = (inst0[0], tuple(int(x) for x in inst0[1]))
    seen, q = {s0: 0}, deque([s0])
    while q:
        u = q.popleft()
        if seen[u] >= depth:
            continue
        for m2, S2, _ in E[u[0]]:
            v = (m2, tuple(int(x) for x in np.asarray(u[1]) + S2))
            if v not in seen:
                seen[v] = seen[u] + 1
                q.append(v)
    g = nx.Graph()
    node = lambda a, S: (int(a), tuple(int(x) for x in cr.img_of[a] + np.asarray(S)))
    for (m, S) in seen:
        for a in cr.mols[m]:
            for j, t in cr.adj[a]:
                g.add_edge(node(a, S), node(j, np.asarray(S) + t + cr.img_of[a] - cr.img_of[j]), kind="cov")
    for (m, S) in seen:
        for m2, S2, rec in E[m]:
            if rec["h"] in cr.mols[m] and rec["inst"][0] == m2 and np.array_equal(rec["inst"][1], S2):
                v = (m2, tuple(int(x) for x in np.asarray(S) + S2))
                if v in seen:
                    g.add_edge(node(rec["h"], S), node(rec["b"], v[1]), kind="hb")
    hn = node(h, inst0[1])
    an = next((n for n in g.neighbors(hn) if g.edges[hn, n]["kind"] == "hb" and copy_label(cr, n[0], np.asarray(n[1]) - cr.img_of[n[0]]) == a_label), None)
    if an is None:
        raise ValueError(f"no H-bond {h_label}...{a_label} at this cutoff")
    g.remove_edge(hn, an)
    try:
        paths = list(nx.all_shortest_paths(g, an, hn))
    except nx.NetworkXNoPath:
        return None
    inst_of = lambda n: (int(cr.mol_of[n[0]]), tuple(int(x) for x in np.asarray(n[1]) - cr.img_of[n[0]]))
    alts = set()
    for p in paths:
        nh = 1 + sum(g.edges[p[i], p[i + 1]]["kind"] == "hb" for i in range(len(p) - 1))
        acc = {p[i + 1] if cr.c_elem[p[i][0]] == "H" else p[i] for i in range(len(p) - 1) if g.edges[p[i], p[i + 1]]["kind"] == "hb"}
        acc.add(an)
        alts.add((len(p), len({inst_of(n) for n in p}), nh, len(acc)))
    best = sorted(alts)[0]
    return dict(ring_size=best[0], n_molecules=best[1], n_hbonds=best[2], n_acceptors=best[3], alternatives=sorted(alts),
                path=[copy_label(cr, n[0], np.asarray(n[1]) - cr.img_of[n[0]]) for n in paths[0]])


def centroid_shell(cr, inst0, rmax=16.0):
    """Sorted centroid-centroid distances (A) from inst0 to every other molecule/ion instance within rmax."""
    c0 = (mol_frac(cr, *inst0)[1] @ cr.M).mean(0)
    R = cr.lattice.reciprocal_lattice_crystallographic.matrix
    n = [int(np.ceil(rmax * np.linalg.norm(R[i]))) + 2 for i in range(3)]
    out = []
    for m in range(len(cr.mols)):
        cm = mol_frac(cr, m, (0, 0, 0))[1].mean(0)
        for S in itertools.product(*(range(-k, k + 1) for k in n)):
            if m == inst0[0] and np.array_equal(np.asarray(S), np.asarray(inst0[1])):
                continue
            d = float(np.linalg.norm(((cm + np.asarray(S)) @ cr.M) - c0))
            if d <= rmax:
                out.append(d)
    return sorted(out)


def subset(cr, keep):
    """Ordered replica: keep asymmetric-unit sites where keep[i] is True, then re-expand and re-find molecules."""
    keep = np.asarray(keep, bool)
    sub = Crystal(cr.name, cr.lattice, cr.ops, [l for l, k in zip(cr.labels, keep) if k],
                  [e for e, k in zip(cr.elems, keep) if k], cr.frac_asym[keep], cr.occ[keep],
                  [g for g, k in zip(cr.dgroup, keep) if k])
    _expand(sub)
    _molecules(sub)
    return sub


def disorder_components(cr):
    """{group: mean occupancy} for every non-zero disorder group (PART)."""
    out = {}
    for g, o in zip(cr.dgroup, cr.occ):
        if g not in (".", "0", "?"):
            out.setdefault(g, []).append(float(o))
    return {g: float(np.mean(v)) for g, v in out.items()}