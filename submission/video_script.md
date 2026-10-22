# CrystalSight: video script (target ≤ 4:00)

*Open Scientific Intelligence Hackathon 2026 · Author: [AUTHOR PLACEHOLDER]*

Narration is about 500 words. At a relaxed 135–145 words per minute that is roughly 3:30–3:45, which leaves about 15 s of slack under the 4:00 limit. Timestamps are targets: if you run long, trim the lines marked *(optional)* first.

**Assets to have open before recording**
- `figures/fig1_leaderboard.png`: heatmaps of mean and macro-balanced scores by model × channel, with baselines; tools in a separate panel
- `figures/fig2_families.png`: balanced score per question family
- `figures/fig3_example.png`: the 7-coordinate Fe case (cod_2014451, Q6): (a) image render, (b) last TUI frame
- `reports/real-full/index.html`: leaderboard tables and per-case replays
- A terminal at the repo root with a clean prompt. Hide the username, hostname and any local paths: use a generic prompt such as `$ ` and a neutral working-directory name.
- Optionally, `tasks/tasks.jsonl` opened in an editor to show one question with its gold answer and evidence

Score definitions used below: **mean** = partial-credit mean over all 247 questions. **Macro balanced** = for each family, the average of the problem and clean subsets, then averaged over the 5 families. Numbers come from `analysis/results.md` (run `real-full`).

---

## Shot list

| # | Time | On screen | Narration |
|---|------|-----------|-----------|
| 1 | 0:00–0:15 | **Hook.** `fig3_example.png` full screen. Zoom slowly into panel (a), the render, then (b), the ASCII frame. Caption overlay: *"Gold: CN 7, pentagonal bipyramid"*. | "This iron centre has seven neighbours: it is a pentagonal bipyramid. We showed it to language models as pictures and through an interactive viewer, and every visual run called it octahedral. Given the CIF text, both models got it right. That case is the question behind CrystalSight." |
| 2 | 0:15–0:42 | **Problem.** Title card: *"CrystalSight: does the way a crystal structure is shown change what an LLM can judge?"* Then a slide or split screen with three panels: a CIF text snippet, a render, an ASCII viewer frame. | "Before a database structure is used for simulation, someone checks it. Are hydrogens missing? Is part of it disordered? What is the metal's coordination? Can it go straight into DFT or MD? LLM agents are increasingly asked to do this check, and we can give them the structure as text, as rendered images or as an interactive viewer. We don't know whether those are equivalent." |
| 3 | 0:42–1:05 | **Design: tasks.** Slide listing the 5 families (Q3 hydrogen, Q4 disorder, Q6 coordination, Q7 usability, Q8 comparison). Optionally cut to `tasks.jsonl` and highlight one question, its gold answer and evidence. | "CrystalSight asks the same questions about the same structures: 67 molecular crystals from the Crystallography Open Database and 247 questions in five families: hydrogen completeness, disorder, metal coordination, usability for simulation, and pairwise comparison. Gold answers are computed with MolCrysKit plus documented rules, and every answer is scored automatically with partial credit." |
| 4 | 1:05–1:35 | **Design: channels.** Slide with a channel table: `cif`, `cif_raw`, `image`, `tui`, `tools (reference)`. Short terminal clip (5–8 s) of the MatterVis TUI rotating or zooming, or a prerecorded replay from the report. | "The model sees one channel at a time: CIF text with give-away disorder annotations stripped; the unstripped CIF as a leakage control; three MatterVis renders; or an interactive MatterVis ASCII viewer that it can rotate, zoom and relabel. Tool access to MolCrysKit is reported separately as a reference upper bound, because those tools compute the gold answers. Most structures are clean, so we also report a balanced score and two trivial baselines." |
| 5 | 1:35–2:12 | **Results: leaderboard.** `fig1_leaderboard.png`. Highlight the cif row, then the image/tui cells, then the baseline row. Optionally scroll the "Main leaderboard" table in `index.html`. | "CIF text is clearly the best channel. DeepSeek-v4-Flash scores 0.950 mean and Gemini-2.5-Flash 0.823. Visual channels fall towards the baselines: Gemini with images scores 0.669, DeepSeek with the viewer 0.767 and Gemini with the viewer 0.481. Always answering 'no problem' scores 0.678, so on the raw mean Gemini's image and viewer runs do not beat saying everything is fine." |
| 6 | 2:12–2:40 | **Results: families and failure modes.** `fig2_families.png`, with the Q4 disorder bars highlighted. Overlay text: *"DeepSeek-TUI sens 0.25 / spec 1.00"* and *"Gemini-TUI sens 0.94 / spec 0.27"*. | "With the same model, macro-balanced score drops by 0.24 to 0.28 between text and pictures or the viewer. The failures run in opposite directions. On disorder, DeepSeek in the viewer almost always says 'ordered': sensitivity 0.25, specificity 1.00. Gemini in the viewer flags almost everything: sensitivity 0.94, specificity 0.27." |
| 7 | 2:40–3:00 | **Results: coordination, tools, leakage.** Back to `fig3_example.png` briefly, then the tools panel of `fig1`. | "Coordination from pictures reaches 0.64, against 0.91 to 1.00 from text, and that includes the iron centre. With MolCrysKit tools both models reach about 0.96. Stripping the CIF annotations changes the mean by −0.004 for DeepSeek and +0.039 for Gemini, so the ranking holds." |
| 8 | 3:00–3:35 | **Limitations and next steps.** Slide with two columns: *Limitations* / *Next*. | "There are limits. The gold labels depend on heuristic thresholds, and even with tools the models reach only 0.87 to 0.89 on disorder, so some of those labels are ambiguous. The benchmark covers 67 structures and two models, with one run each; the coordination family has only 11 questions. The renders may not show partial occupancy at all. Next: more structures and models with repeated runs, occupancy-aware renders, an opt-in local CSD task builder, expert review of ambiguous labels, and agents that combine viewing with text or tool checks." |
| 9 | 3:35–3:50 | **Call to action.** End card: project name, `[REPO LINK]`, "Code · tasks · ground truth · figures: open", author placeholder, hackathon name. Optional terminal shot of `python -m crystalsight run --models mock-oracle mock-random ...`. | "The code, tasks, ground truth and figures are open, and a mock run needs no API key. Try your own model, or add a channel. The link is below." |
| — | 3:50–4:00 | Hold the end card (buffer). | *(silence or music)* |

---

## Narration only (for the teleprompter)

> This iron centre has seven neighbours: it is a pentagonal bipyramid. We showed it to language models as pictures and through an interactive viewer, and every visual run called it octahedral. Given the CIF text, both models got it right. That case is the question behind CrystalSight.
>
> Before a database structure is used for simulation, someone checks it. Are hydrogens missing? Is part of it disordered? What is the metal's coordination? Can it go straight into DFT or MD? LLM agents are increasingly asked to do this check, and we can give them the structure as text, as rendered images or as an interactive viewer. We don't know whether those are equivalent.
>
> CrystalSight asks the same questions about the same structures: 67 molecular crystals from the Crystallography Open Database and 247 questions in five families: hydrogen completeness, disorder, metal coordination, usability for simulation, and pairwise comparison. Gold answers are computed with MolCrysKit plus documented rules, and every answer is scored automatically with partial credit.
>
> The model sees one channel at a time: CIF text with give-away disorder annotations stripped; the unstripped CIF as a leakage control; three MatterVis renders; or an interactive MatterVis ASCII viewer that it can rotate, zoom and relabel. Tool access to MolCrysKit is reported separately as a reference upper bound, because those tools compute the gold answers. Most structures are clean, so we also report a balanced score and two trivial baselines.
>
> CIF text is clearly the best channel. DeepSeek-v4-Flash scores 0.950 mean and Gemini-2.5-Flash 0.823. Visual channels fall towards the baselines: Gemini with images scores 0.669, DeepSeek with the viewer 0.767 and Gemini with the viewer 0.481. Always answering "no problem" scores 0.678, so on the raw mean Gemini's image and viewer runs do not beat saying everything is fine.
>
> With the same model, macro-balanced score drops by 0.24 to 0.28 between text and pictures or the viewer. The failures run in opposite directions. On disorder, DeepSeek in the viewer almost always says "ordered": sensitivity 0.25, specificity 1.00. Gemini in the viewer flags almost everything: sensitivity 0.94, specificity 0.27.
>
> Coordination from pictures reaches 0.64, against 0.91 to 1.00 from text, and that includes the iron centre. With MolCrysKit tools both models reach about 0.96. Stripping the CIF annotations changes the mean by minus 0.004 for DeepSeek and plus 0.039 for Gemini, so the ranking holds.
>
> There are limits. The gold labels depend on heuristic thresholds, and even with tools the models reach only 0.87 to 0.89 on disorder, so some of those labels are ambiguous. The benchmark covers 67 structures and two models, with one run each; the coordination family has only 11 questions. The renders may not show partial occupancy at all. Next: more structures and models with repeated runs, occupancy-aware renders, an opt-in local CSD task builder, expert review of ambiguous labels, and agents that combine viewing with text or tool checks.
>
> The code, tasks, ground truth and figures are open, and a mock run needs no API key. Try your own model, or add a channel. The link is below.

---

## Fact sheet (from `analysis/results.md`, run real-full; check before recording)

| claim in narration | source value |
|---|---|
| CIF text, mean | DeepSeek 0.950, Gemini 0.823 (macro balanced 0.934 / 0.849) |
| Image / TUI, mean | Gemini image 0.669; DeepSeek TUI 0.767; Gemini TUI 0.481 |
| Baselines | no-problem/majority 0.678 mean (0.474 macro balanced); random 0.435 (0.336) |
| Text → visual drop, same model | DeepSeek 0.934 → 0.658 (−0.276); Gemini 0.849 → 0.612 / 0.571 (−0.237 / −0.278) |
| Disorder detection (sens / spec) | DeepSeek-TUI 0.25 / 1.00; Gemini-TUI 0.94 / 0.27 |
| Q6 coordination | image and TUI 0.636 (all three runs); text 0.909–1.000 |
| 7-coordinate Fe | cod_2014451, gold CN 7 pentagonal bipyramid; visual runs answered octahedron (per the one-pager) |
| Tools (reference) | DeepSeek 0.968, Gemini 0.958 mean; Q4 0.870 / 0.894 |
| Leakage control (raw − stripped, mean) | DeepSeek −0.004, Gemini +0.039 |
| Scale | 67 structures, 247 questions (Q3 67, Q4 67, Q6 11, Q7 67, Q8 35), 2 models, 1 run each |

Note: the HTML report rounds DeepSeek `cif` overall to 0.951. The script uses 0.950 to match `results.md` and the one-pager.

**Before publishing, check the recording for:** local paths, the username or hostname in the terminal prompt, gateway URLs or `.env` contents, and browser tabs or bookmarks visible on screen.
