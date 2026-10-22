# MatterVis TUI: proposed improvements for 3D spatial tasks (CrystalSight v3)

Proposal only - nothing in the installed package or any clone was modified.

**Source examined:** installed `matter-vis 0.0.6.dev368` in `.venv/Lib/site-packages/mat_viewer/tui/`,
built from https://github.com/SchrodingersCattt/MatterVis (branch main, commit `cfc6e26`, per `direct_url.json`).
How CrystalSight drives it: `crystalsight/channels/tui.py` -> `mat_viewer.tui.loader_adapter.load_for_tui(path, display_mode='auto')`
(pickled CrystalIR) -> `mat_viewer.tui.TerminalSession(crystal, width=100, height=36, charset='ascii7')`; allowed actions
observe/reset/orbit/align/pan/zoom/fit/set_display (select/focus refused to avoid the chemistry inspector).

## What the check showed (see `tui_check/tui_verdicts.json`, frames in `tui_check/<structure>/`)

- 1 of 20 questions perceivable, 12 partially, 7 not (all four neighbour-count questions are "not").
- Scene = unit cell + boundary replicas (`_load_bundle` calls `build_bundle_scene(display_mode='unit_cell', include_boundary_replicas=True)`); the scene pipeline already supports `transforms` (`repeat`, `grow_radius`, `grow_bonds`, `complete_fragment`, `by_symmetry`, ... in `mat_viewer/transforms/`), but the TUI loader never passes them.
- Default level is `molecule` (hulls/centroids) for every v3 structure (>64 atoms); at atom level `label_mode='auto'` resolves to `dot` (>160 atoms) or `element` (>32), so labels need an explicit `label_mode='label'`.
- **Channel bug:** the CrystalSight GUIDE lists `label_mode: auto | element | none`; mat-vis rejects `none` (valid: auto, label, element, molecule, dot) and the guide never mentions `label`, so a model following it cannot see atom labels.
- Every symmetry copy has the same label; no H-bond lines, no distances, no scale, no axis triad; ascii7 drops colour-only depth tiers.

## Improvements (ordered by value / effort)

| # | Improvement | Files / functions to change | Est. LOC | tui.py channel change? |
|---|---|---|---|---|
| 1 | Fix channel guide: advertise `label_mode: auto|label|element|molecule|dot`, `display_level: atom|molecule`, drop invalid `none` | `crystalsight/channels/tui.py` `GUIDE` string only | 2-3 | yes (this is the change) |
| 2 | Symmetry-copy-aware labels: new `label_mode='label_sym'` -> `O2` for the x,y,z copy, `O2'k` / `O2[1,0,0]` for other copies (op index + lattice shift) | `compositor.py`: `LABEL_MODES`, `_atom_label_text`; `controller._validate_label_mode`; uses existing `AtomIR.image_shift`, `AtomIR.display_copy_id` / `_symop_index` from `loader_adapter._crystal_ir_from_scene` | 30-50 | guide text only |
| 3 | Neighbour shell / supercell at load time: `load_for_tui(..., transforms=[{"kind":"grow_radius","seeds":<molecule of label>,"radius":R}])` or `{"kind":"repeat","a":2,"b":2,"c":2}`; CLI flags `--repeat`, `--shell-around LABEL --radius R` | `loader_adapter.load_for_tui` + `_load_bundle` (thread `transforms` into `build_bundle_scene`), `tui/cli.py` args; scene/transform code already exists | 25-40 (+15 CLI) | yes: `_LOADER` string and pickle cache key must include the transform spec; optional per-task `tui_scope` field |
| 4 | Reference-molecule highlight / isolate: `set_display {"highlight": "molecule_of:O1", "dim_others": true}` or `"show_only": "molecule_of:O1+neighbours:4.0"` (perception-only, no chemistry text) | `state.TerminalDisplayState` (+fields), `controller.set_display`, `session.execute` allowed keys, `compositor.compose_frame` (dim/skip atoms; reuse `crystal_ir.filter_crystal`) | 80-120 | add keys to guide; ALLOWED unchanged |
| 5 | H-bond / short-contact overlay: `show_hbonds` toggle; D-H...A with D,A in N/O, H...A <= 2.5 A, angle >= 120 deg, drawn as dotted `:` / `.` line in a separate layer (also across boundary replicas) | new `tui/contacts.py` (KD-tree or brute force on IR coords + bonds), `CrystalIR` field `contacts`, `compositor.compose_frame` new layer (reuse dashed drawing like `_draw_dashed_circle`), `state`/`controller.set_display`/`session` toggle | 120-160 | guide text; note: makes F1/F2 easier by design - decide per experiment arm |
| 6 | Axis triad + scale bar in a frame corner (projected a, b, c arrows; "|---| 5 A" bar from viewport scale) | `compositor.compose_frame` (overlay pass), `projection.Viewport` for A-per-cell scale | 40-60 | none (appears in frame text) |
| 7 | Depth cue for ascii7: mark back-tier atoms with lowercase/`()` labels or a different bond glyph, since colour tiers are lost | `compositor._atom_label_text`, `_tier_color` call sites, ascii charset branch | 20-30 | none |
| 8 | Ring centroid markers (`*` + ring id) and optional normal stub, for 5/6-membered planar rings | new helper in `tui/crystal_ir.py` or `loader_adapter` (networkx cycle basis on `BondIR`), `compose_frame` marker layer, toggle in display state | 80-110 | guide text |
| 9 | Perception-safe `measure` action: distance between two visible label tokens (with copy suffix from #2) and angle between ring planes; returns numbers only, no chemistry names | `session.execute` dispatch + `controller.measure()`; reuse IR coordinates | 60-90 | add `measure` to `ALLOWED` + guide; changes the channel's capability, so make it a separate experiment arm |
| 10 | Label de-clutter: `hide_h_labels`, label only atoms of highlighted molecule, cap labels per row | `compose_frame` label relaxation stage, display state toggle | 20-40 | guide text |

**Suggested minimum set for the hackathon:** #1 (now), #2, #3, #6 (about 100-150 LOC in mat-vis plus about 20 in `tui.py`). This keeps the channel perception-only while making F1, F4, F5 answerable from frames; #5 and #9 make it closer to a tool channel and should be reported as separate arms.

**Per-family impact (expected):** F1 partially -> perceivable with #2 + #4 (+#5); F2 partially -> perceivable with #3 + #5; F3 not -> partially with #3 + #4 (+#9 for exact counts); F4 partially -> perceivable with #2/#4 + #6; F5 not/partially -> perceivable with #8 + #6 (+#9).
