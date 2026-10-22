"""TUI feasibility probe for tasks_v4 (no model calls): load each scene exactly as the tui channel does, render
views, and check whether the information needed for the gold answer is present/visible."""
import json, sys, re, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from crystalsight.channels.tui import load_crystal, tui_options, extra_options, WIDTH, HEIGHT, _frame
from crystalsight.channels.tui_extras import SceneAnalyzer, hbond_overlay, component_cif
from mat_viewer.tui import TerminalSession, TerminalAction
from mat_viewer.tui.annotations import copy_aware_label
OUT = ROOT / "tasks_v4" / "tui_check"; OUT.mkdir(parents=True, exist_ok=True)
tasks = [json.loads(l) for l in open(ROOT / "tasks_v4" / "tasks_v4.jsonl", encoding="utf-8")]
only = sys.argv[1:]
res = {}
for t in tasks:
    if only and not any(o in t["id"] for o in only): continue
    lo, vo = tui_options(t)
    cr = load_crystal(t["structure_id"] + "_v4", ROOT / t["path"], lo)
    labs = [copy_aware_label(a) for a in cr.atoms]; labset = set(labs)
    n_minor = sum(bool(getattr(a, "is_minor", False)) for a in cr.atoms)
    s = TerminalSession(cr, width=WIDTH, height=HEIGHT, charset="ascii7", **vo)
    views = [("default", None), ("align_a", ("align", {"axis": "a"})), ("align_b", ("align", {"axis": "b"})),
             ("align_c", ("align", {"axis": "c"})), ("zoom3", ("zoom", {"factor": 3.0}))]
    frames = {}
    ex = extra_options(t)
    an = SceneAnalyzer(cr) if ex["show_hbonds"] else None
    for name, act in views:
        obs = s.observe().as_dict() if act is None else s.execute(TerminalAction(act[0], act[1])).as_dict()
        if an is not None:
            obs = dict(obs, frame=dict(obs["frame"], text=hbond_overlay(s, an, obs["frame"]["text"], ex["hbond_max_ha"], ex["hbond_min_angle"])))
        frames[name] = _frame(obs)
    d = OUT / t["id"]; d.mkdir(exist_ok=True)
    for k, v in frames.items(): (d / f"{k}.txt").write_text(v, encoding="utf-8")
    alltext = "\n".join(frames.values())
    g, num, fam = t["gold"], t["numeric"], t["family"]
    chk = dict(scene_atoms=len(cr.atoms), minor_atoms=n_minor, labels_in_frames=len(re.findall(r"[A-Z][a-z]?\d+[A-Za-z']*(?:#\d+)?(?:\[-?\d+,-?\d+,-?\d+\])?", alltext)))
    if fam == "G1":
        H = re.search(r"hydrogen atom (\S+) ", t["question"]).group(1)
        chk.update(gold_in_scene=g["acceptor"] in labset, ref_in_scene=H in labset,
                   gold_in_a_frame=g["acceptor"] in alltext, ref_in_a_frame=re.search(rf"(?<![\w#\[]){re.escape(H)}(?![\w#\[])", alltext) is not None)
        chk["gold_in_hbond_overlay"] = any(f"{H}...{g['acceptor']} " in fr or f"-{H}...{g['acceptor']} " in fr for fr in frames.values())
        v = "perceivable" if chk["gold_in_scene"] and (chk["gold_in_a_frame"] or chk["gold_in_hbond_overlay"]) else ("partially" if chk["gold_in_scene"] else "not")
        why = ("acceptor copy is in the scene; the ad hoc H-bond overlay lists " + H + "..." + g["acceptor"] + " with its distance and the "
               "distance action can confirm it is the closest N/O") if chk["gold_in_hbond_overlay"] else \
              ("acceptor copy is in the scene with its label_sym tag (distance action available to compare candidates)" if v != "not" else "acceptor copy not in scene")
    elif fam == "G2":
        tl = "[%d,%d,%d]" % tuple(num["t"]); tgt = num["ref"] + tl
        chk.update(target_in_scene=tgt in labset, ref_in_scene=num["ref"] in labset)
        v = "partially" if chk["target_in_scene"] and chk["ref_in_scene"] else "not"
        why = ("both M0 and its translate are inside the 2x2x2 supercell and labelled and the show_hbonds overlay draws/lists on-screen H-bonds, but the chain must be "
               "followed across views and intermediate molecules may be cut at the supercell edge") if v == "partially" else "target copy outside scene"
    elif fam == "G3":
        path = num["path"]; inn = sum(p in labset for p in path)
        chk.update(ring_atoms_in_scene=f"{inn}/{len(path)}")
        v = "partially" if inn == len(path) else "not"
        why = (f"all {len(path)} ring atoms are inside the grow_radius scene with label_sym tags, but tracing a {len(path)}-atom ring "
               "through overlay-listed H-bonds in 100x36 ASCII is hard") if v == "partially" else f"only {inn}/{len(path)} ring atoms in scene"
    elif fam == "G4":
        v = "partially"
        why = (f"scene has {len(cr.atoms)} atoms; molecules out to the cutoff are present (grow_radius {lo.get('grow_radius')} A) and "
               "display_level=molecule gives one marker each, but counting dozens of markers inside a 3D radius from ASCII "
               "projections is unreliable; scale bar gives the radius")
    else:
        comps = {}
        for c in ("major", "minor"):
            try:
                cc = load_crystal(t["structure_id"] + "__" + c, component_cif(ROOT / t["path"], c), lo)
                comps[c] = len(cc.atoms)
            except Exception as e:  # noqa: BLE001
                comps[c] = f"error {str(e)[:60]}"
        chk["component_scene_atoms"] = comps
        ok = all(isinstance(x, int) for x in comps.values())
        v = "partially" if ok else "not"
        why = (f"set_component loads ordered major/minor scenes ({comps}); the reference molecule and its neighbours are labelled, "
               "but counting molecules inside a 3-4.5 A contact cutoff from ASCII still needs many distance actions") if ok else "component scene failed"
        res[t["id"]] = dict(verdict=v, reason=why, checks=chk)
        print(t["id"], v, json.dumps(chk), flush=True)
        continue
    if False:
        v = "partially" if n_minor else "not"
        why = (f"both components are rendered ({n_minor} minor-component atoms flagged, labels distinguish PART sites) but the "
               "viewer cannot hide one component, so each ordered replica must be imagined; neighbour counting as in G4") if n_minor else \
              "minor component not flagged in the scene"
    res[t["id"]] = dict(verdict=v, reason=why, checks=chk)
    print(t["id"], v, json.dumps(chk), flush=True)
old = {}
vf = ROOT / "tasks_v4" / "tui_verdicts_v4.json"
if vf.exists() and only: old = json.loads(vf.read_text(encoding="utf-8"))
old.update(res)
vf.write_text(json.dumps(old, indent=1), encoding="utf-8")
print("PROBE_DONE")