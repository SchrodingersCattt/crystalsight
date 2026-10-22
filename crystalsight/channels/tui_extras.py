"""Ad hoc TUI extras for the CrystalSight benchmark (built on top of MatterVis, no upstream change).

MatterVis (0.0.6.dev375) draws covalent bonds only; it has no hydrogen-bond detection or drawing, no distance
query, and its ``is_minor`` flag comes from the loader's disorder solver (chosen orientation), not from the
CIF PART/occupancy columns.  This module adds, for the tui channel only:

* H-bond overlay: D-H...A (D, A in N/O, A in a different covalent unit) detected on the rendered scene atoms;
  drawn as ':' dotted lines between the H and acceptor screen cells (blank cells only) and listed under the
  frame with copy-aware labels at both ends, H...A distance and D-H...A angle.  Criteria are set by the model.
* distance query between two scene atoms given by copy-aware labels (label_sym form).
* disorder component scenes: an ordered CIF keeping non-disordered sites plus the higher- (major) or lower-
  (minor) occupancy disorder groups, loaded as a separate scene (site labels and symmetry numbering unchanged).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from ..paths import CACHE

HB_ELEMS = {"N", "O"}


def _copy_label(atom) -> str:
    from mat_viewer.tui.annotations import copy_aware_label
    return copy_aware_label(atom)


class SceneAnalyzer:
    """Geometry of the atoms actually present in one TUI scene."""

    def __init__(self, crystal):
        self.crystal = crystal
        self.atoms = list(crystal.atoms)
        self.xyz = np.array([np.asarray(a.cart, float) for a in self.atoms]) if self.atoms else np.zeros((0, 3))
        self.elem = [str(a.element) for a in self.atoms]
        self.labels = [_copy_label(a) for a in self.atoms]
        self.index = {}
        for i, lab in enumerate(self.labels):
            self.index.setdefault(lab, i)
        n = len(self.atoms)
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        self.nbrs = [[] for _ in range(n)]
        for b in getattr(crystal, "bonds", []) or []:
            i, j = int(b.i), int(b.j)
            if 0 <= i < n and 0 <= j < n:
                self.nbrs[i].append(j)
                self.nbrs[j].append(i)
                parent[find(i)] = find(j)
        self.unit = [find(i) for i in range(n)]
        self._hb = None

    def hbonds(self):
        """All candidate D-H...A with H...A <= 3.0 A and angle >= 90 deg (filtered later by the model's criteria)."""
        if self._hb is not None:
            return self._hb
        from scipy.spatial import cKDTree
        acc = [i for i, e in enumerate(self.elem) if e in HB_ELEMS]
        out = []
        if acc:
            tree = cKDTree(self.xyz[acc])
            for h, e in enumerate(self.elem):
                if e != "H":
                    continue
                donors = [d for d in self.nbrs[h] if self.elem[d] in HB_ELEMS]
                if not donors:
                    continue
                d = donors[0]
                for k in tree.query_ball_point(self.xyz[h], 3.0):
                    a = acc[k]
                    if a == d or self.unit[a] == self.unit[h]:
                        continue
                    v1, v2 = self.xyz[d] - self.xyz[h], self.xyz[a] - self.xyz[h]
                    ha = float(np.linalg.norm(v2))
                    ang = float(np.degrees(np.arccos(np.clip(v1 @ v2 / np.linalg.norm(v1) / ha, -1, 1))))
                    if ang >= 90:
                        out.append((h, d, a, ha, ang))
        self._hb = sorted(out, key=lambda x: x[3])
        return self._hb

    def distance(self, a: str, b: str) -> str:
        miss = [x for x in (a, b) if _norm(x) not in self.index]
        if miss:
            return f"distance: atom(s) {', '.join(miss)} not in the scene (use copy-aware labels as printed in label_sym mode)"
        i, j = self.index[_norm(a)], self.index[_norm(b)]
        return f"distance {self.labels[i]} - {self.labels[j]} = {float(np.linalg.norm(self.xyz[i] - self.xyz[j])):.3f} A"


def _norm(label: str) -> str:
    return re.sub(r"\s+", "", str(label))


def _line_cells(r0, c0, r1, c1):
    n = max(abs(r1 - r0), abs(c1 - c0))
    for t in range(1, n):
        yield round(r0 + (r1 - r0) * t / n), round(c0 + (c1 - c0) * t / n)


def hbond_overlay(session, analyzer: SceneAnalyzer, text: str, max_ha: float = 2.5, min_angle: float = 120.0,
                  max_list: int = 30) -> str:
    """Draw dotted H...A lines for H-bonds whose H and acceptor are both on screen; list them under the frame."""
    hits = {h.display_index: (h.row, h.col) for h in session.controller.atom_hit_map()}
    lines = [list(x) for x in text.split("\n")]
    shown = []
    for h, d, a, ha, ang in analyzer.hbonds():
        if ha > max_ha or ang < min_angle or h not in hits or a not in hits:
            continue
        (r0, c0), (r1, c1) = hits[h], hits[a]
        for r, c in _line_cells(r0, c0, r1, c1):
            if 0 <= r < len(lines) - 1 and 0 <= c < len(lines[r]) and lines[r][c] == " ":
                lines[r][c] = ":"
        shown.append(f"{analyzer.labels[d]}-{analyzer.labels[h]}...{analyzer.labels[a]} {ha:.2f} A {ang:.0f} deg")
    out = "\n".join("".join(x) for x in lines)
    head = f"H-bonds on screen (H...A <= {max_ha:g} A, D-H...A >= {min_angle:g} deg, ':' lines): {len(shown)}"
    more = f"\n  ... {len(shown) - max_list} more" if len(shown) > max_list else ""
    return out + "\n" + head + ("\n  " + "\n  ".join(shown[:max_list]) if shown else "") + more


def component_cif(path: Path, which: str) -> Path:
    """Ordered CIF for one disorder component: sites without a disorder group plus the groups whose mean
    occupancy is >= 0.5 (major) or < 0.5 (minor).  Other data blocks/loops are kept verbatim."""
    from pymatgen.io.cif import CifFile
    path = Path(path)
    cf = CifFile.from_file(str(path))
    blk = next(b for b in cf.data.values() if "_atom_site_fract_x" in b.data)
    d = blk.data
    labels = list(d["_atom_site_label"])
    groups = list(d.get("_atom_site_disorder_group", ["."] * len(labels)))
    occ = [float(re.sub(r"\(.*\)", "", x)) if x not in ("?", ".") else 1.0 for x in d.get("_atom_site_occupancy", ["1"] * len(labels))]
    mean = {}
    for g, o in zip(groups, occ):
        if g not in (".", "0", "?"):
            mean.setdefault(g, []).append(o)
    if not mean:
        raise ValueError("this structure has no disorder groups")
    mean = {g: sum(v) / len(v) for g, v in mean.items()}
    keep_g = {g for g, o in mean.items() if (o >= 0.5) == (which == "major")}
    keep = [g in (".", "0", "?") or g in keep_g for g in groups]
    keep_lab = {l for l, k in zip(labels, keep) if k}
    for loop in blk.loops:
        if "_atom_site_label" in loop:
            for key in loop:
                d[key] = [v for v, k in zip(d[key], keep) if k]
        elif "_atom_site_aniso_label" in loop:
            mask = [l in keep_lab for l in d["_atom_site_aniso_label"]]
            for key in loop:
                d[key] = [v for v, k in zip(d[key], mask) if k]
    for loop in list(blk.loops):  # an emptied loop (e.g. no aniso rows left) would make the CIF unreadable
        if not d.get(loop[0]):
            blk.loops.remove(loop)
            for key in loop:
                d.pop(key, None)
    out = CACHE / "tui_component" / f"{path.stem}_{which}.cif"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(str(cf), encoding="utf-8")
    return out