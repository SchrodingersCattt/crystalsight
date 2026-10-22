# CrystalSight

**Can a language model judge whether a crystal structure is fit for use, and does it matter how the structure is shown to it?**

CrystalSight is a small, reproducible benchmark that asks LLM agents the questions a crystallographer asks before using a CIF (missing hydrogens, disorder, metal coordination, overall usability, pairwise comparison) and presents the *same* structure through different channels: CIF text, rendered images, and an interactive terminal (TUI) viewer. Ground truth is computed with [MolCrysKit](https://github.com/SchrodingersCattt/MolCrysKit) plus documented rules; images and the TUI come from [MatterVis](https://github.com/SchrodingersCattt/MatterVis). A tool-using channel is reported separately as a reference upper bound.

* Design and rules: [`DESIGN.md`](DESIGN.md)
* One-page write-up: [`writeup/CrystalSight_onepager.pdf`](writeup/CrystalSight_onepager.pdf) (source: `.md`)
* Results: [`analysis/results.md`](analysis/results.md), [`analysis/results.csv`](analysis/results.csv), figures in [`figures/`](figures/)

## Question families

| id | question | answer |
|----|----------|--------|
| Q3 | Are hydrogens missing? On which elements? | `{missing_h, elements}` |
| Q4 | Is there disorder? Which components, which type? | `{disordered, components, types}` |
| Q6 | Coordination number and geometry of the metal | `{cn, geometry}` |
| Q7 | Is the structure usable for simulation as is? Which issues? | `{usable, issues}` |
| Q8 | Which of two structures has property X (A / B / both / neither)? | choice |

Scoring gives partial credit per field (see `crystalsight/score.py`). The released task set has 247 questions over 67 structures from the Crystallography Open Database (COD) and MolCrysKit's examples.

## Channels

| channel | what the model sees |
|---------|---------------------|
| `cif` | CIF text with occupancy/disorder hints that would give away the answer stripped |
| `cif_raw` | unmodified CIF text (leakage control) |
| `image` | three rendered views (six for pairs) |
| `tui` | an interactive MatterVis terminal viewer, 8 actions per structure (rotate, zoom, change display, ...) |
| `tools` | MolCrysKit analysis tools (*reference upper bound, not part of the main leaderboard*) |

## Install

Python 3.11+ is required.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -e .
python -m pytest -q tests        # optional sanity check
```

`pip install -e .` pulls MolCrysKit and MatterVis (from GitHub main) as dependencies.

## Quick start with mock models (no API key)

```bash
python -m crystalsight taskgen                  # GT + tasks -> data/gt/, tasks/tasks.jsonl (already shipped)
python -m crystalsight prepare                  # renders + TUI warm-up cache -> data/renders/
python -m crystalsight run --models mock-oracle mock-random --channels cif cif_raw image tui tools --run-id mock-e2e --workers 8
python -m crystalsight score mock-e2e
python -m crystalsight report mock-e2e --cases 5  # -> reports/mock-e2e/index.html
```

`mock-oracle` answers with the gold label (pipeline check, should score 1.0); `mock-random` is the random baseline used in the analysis.

## Real models (your own OpenAI-compatible endpoint)

Credentials are read **only** from environment variables or from a repo-local `.env` (gitignored). Copy the template and fill it in:

```bash
cp .env.example .env
# OPENAI_BASE_URL=https://your-gateway.example.com/v1
# OPENAI_API_KEY=...
# optional separate endpoint for the DeepSeek entry: DEEPSEEK_BASE_URL / DEEPSEEK_API_KEY
```

Model entries live in [`configs/models.toml`](configs/models.toml) (only variable *names*, never values). Each entry has a generic default `model` id; if your gateway names the model differently (e.g. with a provider prefix), set the variable named in its `model_env` field, e.g. `CRYSTALSIGHT_MODEL_DEEPSEEK=<your-id>` in `.env`, instead of editing the file. Set `vision = false` for text-only models (the image channel is then skipped). Then:

```bash
python -m crystalsight smoke --models deepseek-v4-flash gemini-2.5-flash       # one request per model/channel
python -m crystalsight run --models deepseek-v4-flash gemini-2.5-flash --channels cif image tui tools --run-id real-full --workers 16 --resume
python -m crystalsight run --models deepseek-v4-flash gemini-2.5-flash --channels cif_raw --run-id real-full --workers 16 --resume
python -m crystalsight score real-full
python -m crystalsight report real-full --cases 5
```

On Windows, `scripts/real_full.ps1` does both passes plus scoring (`--resume` makes it restartable). Use `--structures id1 id2 ...` for a subset. API keys are never written to `runs/` or `reports/`.

## Reproduce analysis and figures

```bash
python scripts/analyze.py --run real-full --random-run mock-e2e   # -> analysis/results.{md,csv,json}, detection.csv, failure_cases.json
python scripts/make_figures.py --run real-full                    # -> figures/fig1_leaderboard.png, fig2_families.png, fig3_example.png
```

`analysis/` and `figures/` in the repository were produced from the run reported in the write-up (2026-10-22). Full raw run records (`runs/`, with complete model transcripts) are not committed. Instead `results/real-full/` holds the scored answers (`scored.jsonl`, `summary.json`, `leaderboard.csv`) and the TUI frames used in Figure 3, and `results/mock-e2e/scored.jsonl` holds the random baseline. Both scripts read `runs/<run>` if it exists and otherwise fall back to `results/<run>`, so the analysis and figures can be reproduced from a fresh clone without API access.

## Data and licensing

The task set uses COD structures (public domain / CC0) and MolCrysKit's MIT-licensed examples only. The pipeline works on any CIF, including CSD entries, but CSD-derived tasks cannot be redistributed. `scripts/fetch_data.py` re-downloads the COD files from their IDs.

## Repository layout

```
crystalsight/        runner, channels (cif_text, image, tui, tools), models, gt, taskgen, score, report
configs/models.toml  model registry (env-var names only)
data/                structures (CIF), ground truth (data/gt), manifest
tasks/tasks.jsonl    the 247 benchmark questions with gold answers and evidence
scripts/             fetch_data, analyze, make_figures, real-run helpers
results/             scored answers of the reported run (compact)
analysis/, figures/  results of the reported run
writeup/             one-page summary
```
