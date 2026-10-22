# CrystalSight — design (v2, 2026-10-22)

## Research question (neutral)
Agents in materials chemistry increasingly have to "read" crystal structures. **We measure which input
modality lets LLMs read a molecular-crystal structure best**: the CIF as text, rendered images
(MatterVis CPU renders along a, b, c), or an interactive ASCII viewer (MatterVis TUI session). We have
no prior expectation about the ranking — in particular we do not assume the TUI beats images or text.
MolCrysKit tool calls are reported separately as a *reference upper bound* (several tools run the same
computations that produce the gold answers), not as a leaderboard entry. `cif_raw` (unstripped CIF) is
kept as a leakage control for the text channel.

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
