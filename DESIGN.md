# CrystalSight — design (v1 structure checks; v3/v4 spatial sets, 2026-10-22)

## Research question (neutral)
Agents in materials chemistry increasingly have to "read" crystal structures. **We measure which input
modality lets LLMs read a molecular-crystal structure best**: the CIF as text, rendered images
(MatterVis CPU renders along a, b, c), or an interactive ASCII viewer (MatterVis TUI session). We have
no prior expectation about the ranking — in particular we do not assume the TUI beats images or text.
MolCrysKit tool calls are reported separately as a *reference upper bound* (several tools run the same
computations that produce the gold answers), not as a leaderboard entry. `cif_raw` (unstripped CIF) is
kept as a leakage control for the text channel.

## Spatial question sets (v3 easy, v4 hard; headline results)
The v1 families below are structure checks. The spatial sets ask questions whose answers need 3D work in the
crystal, with gold answers computed from geometry only (`crystalsight/gt_spatial.py`).
- **v3 (easy, `tasks_v3/`):** F1 symmetry relation of an H-bond partner, F2 H-bond motif, F3 nearest neighbours,
  F4 ring orientation, F5 stacking. One contact or one plane is enough, and text models solve most of it.
- **v4 (hard, `tasks_v4/`):**
  - G1 nearest contact: the copy-aware label `SITE#k[i,j,k]` of the nearest acceptor;
  - G2 H-bond steps: steps from a molecule to its lattice translate;
  - G3 H-bond ring: smallest H-bond ring through a given H-bond (ring size and number of molecules);
  - G4 shell count: count of molecules within a centroid or contact radius;
  - G5 disorder replicas: neighbour counts in the ordered major and minor disorder replicas.

  These need exact enumeration or graph search.
- **Robustness:** every gold answer is recomputed with all cutoffs shifted by ±5 %. Questions whose answer changes are
  flagged as fragile and replaced; v4 has 20 questions over 16 structures and none is fragile. Each task records the
  numbers behind its answer, a note on why it is hard from CIF text, and whether it is feasible in the TUI.
- **Scoring:** partial credit per JSON field (`crystalsight/score_v3.py`). A copy label earns 0.2 for the site,
  0.4 for the symmetry operation and 0.4 for the shift. Strict = every field exactly right.
- **Text inputs:** see "Text-channel inputs" below (H-bond tables removed for v4; `strip_cif` fix).
- **Results:** `analysis/results_v4.md` and `figures/v4_fig*.png`, from `results/real-v3` and `results/real-v4`.
  Hard set: text 0.20–0.43, images and viewer 0.10–0.22, geometry tools 0.75–0.78 (models: GPT-6-Luna, DeepSeek-v4.1-Flash; scores rounded half up).

## Question families: what a crystallographer asks when judging a CIF
The v1 set (molecule counts, moiety formulas, contact types) was dropped because it mirrored
MolCrysKit's feature list ("teaching to the test"). v2 keeps only judgement questions:

| family | question | answer | gold (deterministic) |
|---|---|---|---|
| Q3_hydrogen | Are H atoms missing; on atoms of which element(s)? | `{missing_h, elements}` | MolCrysKit `add_hydrogens`; each added H attributed to its nearest heavy atom. Missing iff H added ≥ 5 % of the completed H count, or the model has no H at all; `elements` = parent elements carrying ≥ 10 % of the added H. |
| Q4_disorder | Is there disorder; which component; which type? | `{disordered, components ⊆ {main, solvent, counterion, other_component}, types ⊆ {alternative_positions, partial_occupancy}}` | Per MolCrysKit molecule: atoms with occupancy < 1 or a CIF disorder group. Type: `alternative_positions` if a molecule has ≥ 2 disorder groups or two partial atoms of the same element < 1.0 Å apart; `partial_occupancy` for partial sites without such a partner. |
| Q6_coordination | Metal CN and coordination geometry (metal-containing structures only) | `{cn, geometry}` | Donors = non-H, non-metal atoms within 1.15 × (sum of covalent radii); geometry = MolCrysKit `classify_shell` (CShM). Asked only when all sites of that metal share one CN in 4–8 and best CShM ≤ 3. |
| Q7_usability | Can this CIF be used directly for periodic DFT/MD; if not, what blocks it? | `{usable, issues ⊆ {disorder, missing_hydrogen, solvent_present}}` | Rule: issues = disorder (Q4 gold) + missing_hydrogen (Q3 gold) + solvent_present (any species with role solvent); usable iff no issue. Solvent counts as blocking because a solvate cell forces a modelling decision (keep / remove / model) before simulation. |
| Q8_compare | Two similar structures A/B: which contains solvent / which is disordered? | `A / B / both / neither` | Composed from the single-structure golds. Pairing: for each property, each positive structure is paired with the most similar unused negative (same main-component heavy-atom formula first, else closest main-component size, ≤ 50 % difference), plus ~1/3 as many same-label pairs (both / neither). A/B order randomised with a fixed seed. |

**Component roles** (used by Q4/Q7/Q8): main = species with the most heavy atoms; solvent = known
solvent heavy-atom formula (MolCrysKit `COMMON_SOLVENTS` + a short documented list in `gt.py`) or any
O/H-only species (water, incl. H-bonded water clusters); counterion = monoatomic halide/metal ion or a
listed inorganic anion (ClO4, NO3, BF4, PF6, SO4, triflate, ...); everything else = other_component.
Fragments with no heavy atom (loose H sites) are ignored for location.

**Scope**: molecular / metal-organic crystals only (contains C plus H, N or O). Purely inorganic solids
in the data pool are excluded (`tasks/taskgen_log.json: out_of_scope_inorganic`).

**Scoring (partial credit, every family in [0, 1]; implemented in `crystalsight/score.py`)**
- Q3: clean model → 1 iff `missing_h=false`; H missing → 0.5·[missing_h=true] + 0.5·F1(elements).
- Q4: ordered → 1 iff `disordered=false`; disordered → ⅓·[disordered=true] + ⅓·F1(components) + ⅓·F1(types) (location/type only credited if presence is right).
- Q6: 0.5·[CN exact] + 0.5·[geometry exact].
- Q7: usable → 1 iff `usable=true`; not usable → 0.5·[usable=false] + 0.5·F1(issues).
- Q8: exact match.
Infra errors score 0 and are counted separately. Gold = agreement with MolCrysKit + the rules above,
not absolute truth; the write-up must say so.

## Channels
`cif` (stripped CIF text), `cif_raw` (leakage control), `image` (3 renders per structure; 6 for pairs),
`tui` (MatterVis TerminalSession, 8 actions per structure; pairs get two viewers and a `switch` action),
`tools` (reference upper bound: mck summary / molecules / sanity-check / polyhedra, an H-completion report
and a CShM shell report; pairs pass `"structure": "A"|"B"`).

## Data and CCDC note
The pipeline works on any CIF. The public task set uses **COD only** (plus MolCrysKit's MIT-licensed
examples) because CSD/CCDC entries cannot be redistributed. An optional local script that builds the
same tasks from CSD refcodes for licensed users is future work.

## Code provenance
The runner, channels, scorer, report and task generator are written from scratch in this repository.
No code, prompts or tool schemas are taken from chat-crystal-forge (a different competition's project).
MolCrysKit and MatterVis are used only as pip dependencies (GitHub main). The only external file read at
runtime is an optional repo-local `.env` with the OpenAI-compatible gateway credentials (values are never logged).

## Ad hoc tools built for the benchmark (v4)
For the v4 question set (copy-aware H-bond partners, H-bond paths and rings, neighbour shells, ordered
disorder replicas) two small modules were written inside crystalsight, specifically for this benchmark.
They are not part of MolCrysKit or MatterVis and are offered only on v4 tasks, so v3 runs stay reproducible.
- `crystalsight/channels/geom_tools.py` (tools channel): `geom_hbond_list`, `geom_nearest_atoms`,
  `geom_hbond_path`, `geom_hbond_ring`, `geom_neighbours`, `geom_disorder_components`; every tool except
  the last accepts `component = all|major|minor`. Built on the same geometry code as the gold
  (`gt_spatial.py`) and the same copy label form as MatterVis `label_sym` (`SITE#k[i,j,k]`). They return
  raw lists (contacts, chains, ring members, neighbour lists) that the model still has to count and interpret.
  They do not return the final answer.
- `crystalsight/channels/tui_extras.py` (tui channel): `show_hbonds` overlay (':' dashes between H and
  acceptor on screen, plus a list of on-screen H-bonds with copy labels at both ends), a `distance`
  action, and `set_component` (reload the scene with only the major or minor disorder component).
  MatterVis itself has no H-bond detection or drawing. Its `is_minor` flag comes from its disorder solver
  and does not follow CIF PART/occupancy directly, which is why `set_component` filters the CIF instead.
The MolCrysKit CLI gaps these tools stand in for are listed per question in `tasks_v4/TASKS_v4.md`.
## Text-channel inputs: H-bond tables and the strip_cif fix (2026-10-22)
- v4 only: both `cif` and `cif_raw` drop every `_geom_hbond_*` loop before anything else
  (`strip_hbond_loops`, crystalsight/channels/cif_text.py). All other lines stay byte-identical and
  `_geom_bond`/`_geom_angle` are kept. These precomputed D-H...A tables carry CIF symmetry codes, so they directly
  give the G1 acceptor copy and the edges of the G2/G3 H-bond graph. 11 of the 20 v4 tasks had one.
  `cif_raw` therefore means "full CIF minus H-bond tables" for v4.
- `strip_cif` bug fix: the old version removed the `loop_` keyword of almost every loop (atom sites, symmetry
  operations, bonds), so the model saw tag lists followed by unmarked data rows. It also dropped the line after
  every stripped `;` block (e.g. `_space_group_IT_number`). Loops are now kept intact. A loop is removed as a whole
  (keyword, tags and rows) only when all its tags are stripped. Symmetry-operation order and numbering are unchanged.
- Results produced before the fix used the old stripper and still contained the H-bond tables: all v3 text
  results, v4 deepseek-v4.1-flash `cif`, and the superseded first v4 gpt-6-luna `cif`/`cif_raw`.