"""Tests for the spatial sets: text-channel inputs, copy-label scoring and v4 gold consistency."""
import json
from pathlib import Path

import pytest

from crystalsight.channels.cif_text import strip_cif, strip_hbond_loops
from crystalsight.score_v3 import score_v3

ROOT = Path(__file__).resolve().parents[1]
CIF = """data_x
_journal_name_full 'J'
_publ_section_title
;
A title
;
_space_group_IT_number 14
loop_
_publ_author_name
'Doe, A.'
'Roe, B.'
loop_
_symmetry_equiv_pos_as_xyz
'x, y, z'
'-x, -y, -z'
loop_
_atom_site_label
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
O1 0.1 0.2 0.3
loop_
_geom_hbond_atom_site_label_D
_geom_hbond_atom_site_label_H
_geom_hbond_atom_site_label_A
_geom_hbond_site_symmetry_A
O1 H1 O1 2_555
loop_
_geom_bond_atom_site_label_1
_geom_bond_atom_site_label_2
_geom_bond_distance
O1 H1 0.84
"""


def test_strip_cif_keeps_loops_and_neighbours():
    s = strip_cif(CIF)
    assert "_journal" not in s and "_publ" not in s and "Doe" not in s and "A title" not in s
    assert "_space_group_IT_number 14" in s          # line after a stripped ;-block survives
    assert s.count("loop_") == 4                     # symmetry, atom_site, geom_hbond, geom_bond
    assert "'-x, -y, -z'" in s and "O1 0.1 0.2 0.3" in s


def test_strip_hbond_loops_only_touches_hbond_tables():
    s = strip_hbond_loops(CIF)
    assert "_geom_hbond" not in s and "2_555" not in s
    assert "_geom_bond_distance" in s and "O1 H1 0.84" in s
    assert s.replace("\n", "") == CIF.replace("\n", "").replace(
        "loop__geom_hbond_atom_site_label_D_geom_hbond_atom_site_label_H_geom_hbond_atom_site_label_A"
        "_geom_hbond_site_symmetry_AO1 H1 O1 2_555", "")


def test_copy_label_partial_credit():
    t = {"benchmark": "v4", "gold": {"acceptor": "O2#3[0,0,1]"}, "score_weights": {"acceptor": 1.0}}
    assert score_v3(t, {"acceptor": "O2#3[0,0,1]"})["score"] == 1.0
    wrong_shift = score_v3(t, {"acceptor": "O2#3[1,1,2]"})["score"]
    assert abs(wrong_shift - 0.6) < 1e-9             # site 0.2 + operation 0.4
    assert score_v3(t, {"acceptor": "N1"})["score"] == 0.0


V4 = ROOT / "tasks_v4" / "tasks_v4.jsonl"


@pytest.mark.skipif(not V4.exists(), reason="v4 tasks not present")
def test_v4_tasks_are_robust_and_oracle_scores_one():
    tasks = [json.loads(line) for line in V4.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(tasks) == 20
    assert not any(t["fragile"] for t in tasks)
    assert all("abs_path" not in t for t in tasks)
    for t in tasks:
        assert score_v3(t, t["gold"])["score"] == 1.0