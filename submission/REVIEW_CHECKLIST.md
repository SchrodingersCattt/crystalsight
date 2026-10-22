# Review checklist (final package, 2026-10-23)

Branch: `v4-final` in the private repository. Nothing has been merged into `main` and nothing has been made public.

## 1. What to review

| item | where | what to check |
|---|---|---|
| Key finding and results | `README.md` (top section), `analysis/results_v4.md` | Do the numbers match the figures? Is the claim worded fairly? |
| Figures | `figures/v4_fig1_channels.png`, `figures/v4_fig2_families.png` | Readability, titles, caveat notes (DeepSeek empty replies, "not run", "text-only model") |
| One-page write-up | `writeup/CrystalSight_onepager.pdf` (also `submission/CrystalSight_onepager.pdf`; source `.md` + `onepager.css`) | Fits on one A4 page; tone; limitations |
| Video v3 | `submission/CrystalSight_demo_v3.mp4` + `.srt`; notes in `submission/VIDEO_v3_NOTES.md` | Results segment only (≈01:57–03:21). The narration voice of the new segment differs from the rest (see notes) |
| Methods and design | `DESIGN.md` (section "Spatial question sets" and the two sections at the end), `tasks_v4/TASKS_v4.md` | Gold definitions, ±5 % checks, H-bond table removal, `strip_cif` fix |
| Social posts | `submission/social_post.md` | Updated to the spatial results; character counts are given |
| Scored data | `results/real-v4`, `results/real-v3`, `results/mock-v4-final` | `run_meta.json` notes: overrides, superseded numbers, early stop, old text input for DeepSeek CIF |

Kept unchanged: `tasks/tasks.jsonl`, `submission/CrystalSight_demo.mp4`/`_v2.mp4` and their `.srt` files.

## 2. Known caveats to keep in mind

- DeepSeek-v4.1-Flash CIF on v4 (0.20) used the old text input (old stripper, H-bond tables present). 15 of its 20 replies were empty at the 32k-token output cap, and its `cif_raw` was not run.
- The GPT-6-Luna v4 text channels were re-run with the fixed input. The superseded numbers (cif 0.310, cif_raw 0.425) are recorded in `results/real-v4/run_meta.json`.
- After the runs, `abs_path` (a local path) was removed from `tasks_v3/tasks_v3.jsonl` and `tasks_v4/tasks_v4.jsonl`. Because of that, the task-file sha256 differs from the hash stored in `run_meta.json`. No question, gold answer or option changed.
- Three v4 tasks and nine v3 tasks use licensed CSD-derived structures. These are not in the repository; they are only referenced by anonymous ids (`ccdc_SNN`).
- The v3 easy-set runs used the old `strip_cif` for the `cif` channel. The H-bond-table removal applies only to v4.

## 3. Steps only you can do

1. Watch the new video segment, then choose the v3 file, or re-record the narration for that segment yourself (script and timings in `submission/VIDEO_v3_NOTES.md`).
2. Review the branch `v4-final`, then merge it into `main` (or open a PR) yourself.
3. Make the repository public. Before that, double-check that no CSD files are present (`git ls-files | findstr ccdc` should list only code and docs).
4. Post on X and LinkedIn (`submission/social_post.md`): fill in `[REPO LINK]` and `[VIDEO]`.
5. Submit the hackathon form before 08:00 Beijing time on 2026-10-23: repository link, video, and one-pager.

## 4. Not in the commit (kept locally, unchanged)

- `submission/CrystalSight_demo.mp4` (v1) and `submission/CrystalSight_demo_v2.mp4` (v2). They were never tracked, and leaving them out keeps the repository about 46 MB smaller. Their `.srt` files are committed.
- `submission/video_script.md` is still the v1/v2 script. The narration of the new results segment is in `VIDEO_v3_NOTES.md`.
- Run folders `runs/`, HTML reports `reports/` and the CSD-derived structures are gitignored. Compact scored results are in `results/`.