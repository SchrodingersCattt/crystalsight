from crystalsight.channels.cif_text import strip_cif
from crystalsight.models import MockModel, extract_json
from crystalsight.score import _norm_formula, score_answer


def T(answer_type, gold, options=None):
    return {"answer_type": answer_type, "gold": gold, "options": options}


def test_scalar_scoring():
    assert score_answer(T("int", 4), 4)[0] == 1.0
    assert score_answer(T("int", 4), "4")[0] == 1.0
    assert score_answer(T("int", 4), 5)[0] == 0.0
    assert score_answer(T("int", 1), True)[0] == 0.0
    assert score_answer(T("bool", True), "yes")[0] == 1.0
    assert score_answer(T("bool", False), None)[0] == 0.0


def test_set_scoring():
    t = T("set", ["hydrogen_bond", "pi_stacking"])
    assert score_answer(t, ["pi_stacking", "hydrogen_bond"])[0] == 1.0
    assert abs(score_answer(t, ["hydrogen_bond"])[0] - 2 / 3) < 1e-9
    assert score_answer(T("set", []), [])[0] == 1.0


def test_formula_norm():
    assert _norm_formula("H9C8NO2") == _norm_formula("C8 H9 N O2") == "C8H9NO2"
    assert score_answer(T("formula_set", ["C8H9NO2", "H2O"]), ["OH2", "C8H9N1O2"])[0] == 1.0


def test_extract_json():
    assert extract_json('blah ```json\n{"answer": 3}\n``` tail') == {"answer": 3}
    assert extract_json('<think>{"x":1}</think>{"answer": true}') == {"answer": True}
    assert extract_json("no json") is None


def test_strip_cif_removes_formula_and_z():
    cif = "data_x\n_chemical_formula_moiety 'C8 H9 N O2'\n_cell_formula_units_Z 8\n_cell_length_a 11.8\n# comment\n"
    s = strip_cif(cif)
    assert "C8 H9" not in s and "units_Z" not in s and "_cell_length_a 11.8" in s


def test_mock_oracle_and_random():
    task = {"id": "x", "answer_type": "int", "gold": 7}
    assert extract_json(MockModel("oracle").complete([], context={"task": task, "channel": "cif"}).text)["answer"] == 7
    r = extract_json(MockModel("random").complete([], context={"task": task, "channel": "cif"}).text)["answer"]
    assert isinstance(r, int)

def O(qtype, gold):
    return {"answer_type": "object", "qtype": qtype, "gold": gold}


def test_family_partial_credit():
    q4 = O("Q4_disorder", {"disordered": True, "components": ["solvent"], "types": ["partial_occupancy"]})
    assert score_answer(q4, {"disordered": True, "components": ["solvent"], "types": ["partial_occupancy"]})[0] == 1.0
    assert abs(score_answer(q4, {"disordered": True, "components": ["main"], "types": ["partial_occupancy"]})[0] - 2 / 3) < 1e-9
    assert score_answer(q4, {"disordered": False, "components": [], "types": []})[0] == 0.0
    clean = O("Q4_disorder", {"disordered": False, "components": [], "types": []})
    assert score_answer(clean, {"disordered": False})[0] == 1.0
    q3 = O("Q3_hydrogen", {"missing_h": True, "elements": ["C", "N"]})
    assert score_answer(q3, {"missing_h": True, "elements": ["c"]})[0] == 0.5 + 0.5 * (2 / 3)
    q7 = O("Q7_usability", {"usable": False, "issues": ["disorder"]})
    assert score_answer(q7, {"usable": False, "issues": ["disorder"]})[0] == 1.0
    assert score_answer(q7, {"usable": True, "issues": []})[0] == 0.0
    q6 = O("Q6_coordination", {"cn": 6, "geometry": "octahedron"})
    assert score_answer(q6, {"cn": 6, "geometry": "trigonal prism"})[0] == 0.5
    q8 = {"answer_type": "choice", "qtype": "Q8_compare", "gold": "B", "options": ["A", "B", "both", "neither"]}
    assert score_answer(q8, "b")[0] == 1.0 and score_answer(q8, "A")[0] == 0.0
