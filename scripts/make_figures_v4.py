"""Figures and tables for the spatial question sets (v3 = easy set, v4 = hard set), from real scored runs only.

Reads runs/<run>/scored.jsonl, falling back to results/<run>/scored.jsonl (compact copies shipped in the repo).
Writes figures/v4_fig1_channels.png, figures/v4_fig2_families.png and analysis/results_v4.{md,csv}.
Usage: python scripts/make_figures_v4.py
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNS = {"v3": ("real-v3", "mock-v3-e2e"), "v4": ("real-v4", "mock-v4-final")}
MODELS = [("gpt-6-luna", "GPT-6-Luna"), ("deepseek-v4.1-flash", "DeepSeek-v4.1-Flash")]
SHORT = {"gpt-6-luna": "GPT-6-Luna", "deepseek-v4.1-flash": "DeepSeek-v4.1-Flash"}
CHANNELS = [("cif", "CIF text"), ("cif_raw", "CIF text, unstripped"), ("image", "Rendered images"),
            ("tui", "ASCII 3D viewer"), ("tools", "Geometry tools")]
FAMILIES = {
    "v3": [("F1", "Symmetry relation"), ("F2", "H-bond network"), ("F3", "Neighbour list"), ("F4", "Orientation"),
           ("F5", "Stacking")],
    "v4": [("G1", "G1\nnearest contact"), ("G2", "G2\nH-bond steps"), ("G3", "G3\nH-bond ring"),
           ("G4", "G4\nshell count"), ("G5", "G5\ndisorder replicas")],
}
INK, MUTED, GRID, ACCENT, ACCENT2 = "#1F2328", "#6E7781", "#D0D7DE", "#2F6FEB", "#8C959F"
plt.rcParams.update({"font.family": "Arial", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": INK, "text.color": INK, "figure.facecolor": "white",
                     "axes.facecolor": "white", "savefig.facecolor": "white"})


def r2(v: float) -> str:
    """Two decimals, halves rounded up (0.425 -> 0.43), used for every displayed score."""
    return str(Decimal(repr(round(v, 9))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


LABEL_BOX = dict(boxstyle="square,pad=0.15", fc="white", ec="none")


def scored(run: str) -> list[dict]:
    for base in ("runs", "results"):
        p = ROOT / base / run / "scored.jsonl"
        if p.exists():
            return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    raise FileNotFoundError(run)


def fam(task_id: str) -> str:
    return task_id.split("_")[1]


def table(rows: list[dict]) -> dict:
    agg = defaultdict(list)
    for r in rows:
        if str(r.get("error")) in ("True", "true", "1"):
            continue
        s, st = float(r["score"]), float(r["strict"])
        empty = r.get("answer") in (None, "None", "", {})
        for key in ((r["model"], r["channel"], "ALL"), (r["model"], r["channel"], fam(r["task_id"]))):
            agg[key].append((s, st, empty, int(r.get("completion_tokens") or 0)))
    return {k: dict(n=len(v), score=sum(x[0] for x in v) / len(v), strict=sum(x[1] for x in v) / len(v),
                    unparseable=sum(x[2] for x in v), out_tokens=sum(x[3] for x in v)) for k, v in agg.items()}


def random_baseline(rows: list[dict]) -> float:
    v = [float(r["score"]) for r in rows if r["model"] == "mock-random"]
    return sum(v) / len(v)


def fig_channels(T: dict, base: dict, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.1), sharey=True)
    for ax, ver, title in ((axes[0], "v3", "Easy set (v3): one contact, one plane"),
                           (axes[1], "v4", "Hard set (v4): enumerate, trace, count")):
        ys = list(range(len(CHANNELS)))[::-1]
        for mi, (mid, mname) in enumerate(MODELS):
            color = ACCENT if mi == 0 else ACCENT2
            for y, (ch, _) in zip(ys, CHANNELS):
                k = (mid, ch, "ALL")
                yy = y + (0.19 if mi == 0 else -0.19)
                if k not in T[ver]:
                    ax.text(0.01, yy, "not run" if ch != "image" else "no image input (text-only model)", va="center",
                            fontsize=8, color=MUTED, bbox=LABEL_BOX, zorder=4)
                    continue
                v = T[ver][k]["score"]
                ax.barh(yy, v, height=0.34, color=color, label=mname if y == ys[0] else None)
                x = v + 0.012 if not (v < base[ver] + 0.01 and v + 0.06 > base[ver]) else base[ver] + 0.012
                ax.text(x, yy, r2(v), va="center", fontsize=8.5, color=INK, bbox=LABEL_BOX, zorder=4)
        ax.axvline(base[ver], color=MUTED, lw=1, ls=(0, (3, 3)), zorder=1)
        ax.text(base[ver] + 0.01, -0.75, f"random {r2(base[ver])}", fontsize=8, color=MUTED)
        ax.set_yticks(ys, [c[1] for c in CHANNELS])
        ax.set_xlim(0, 1.05)
        ax.set_ylim(-0.95, len(CHANNELS) - 0.45)
        ax.set_title(title, loc="left", fontsize=11, color=INK, pad=8)
        ax.grid(axis="x", color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.set_xlabel("mean score (partial credit), 20 questions", color=MUTED, fontsize=9)
    axes[0].legend(loc="lower right", frameon=False, fontsize=9)
    fig.suptitle("Easy questions: text is enough. Hard 3D questions: only geometry tools hold up",
                 x=0.01, ha="left", fontsize=13.5, fontweight="bold")
    fig.text(0.01, 0.915, f"Mean partial-credit score, 20 questions per set. Dashed line = random ({r2(base['v3'])} easy, "
             f"{r2(base['v4'])} hard). DeepSeek CIF (hard): "
             f"{T['v4'][('deepseek-v4.1-flash', 'cif', 'ALL')]['unparseable']}/20 empty at 32k-token cap.",
             fontsize=9.5, color=MUTED)
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    fig.savefig(out, dpi=200)
    plt.close(fig)


def fig_families(T: dict, out: Path) -> None:
    rows = [(m, c) for m, _ in MODELS for c, _ in CHANNELS if (m, c, "ALL") in T["v4"]]
    fams = FAMILIES["v4"]
    data = [[T["v4"].get((m, c, f), {}).get("score", float("nan")) for f, _ in fams] for m, c in rows]
    cmap = LinearSegmentedColormap.from_list("cl", ["#FFFFFF", "#DCE8FD", ACCENT])
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    ax.imshow(data, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i, row in enumerate(data):
        for j, v in enumerate(row):
            ax.text(j, i, r2(v), ha="center", va="center", fontsize=11, color="white" if v > 0.7 else INK)
    chn = dict(CHANNELS)
    ax.set_yticks(range(len(rows)), [f"{SHORT[m]}  ·  {chn[c]}" for m, c in rows])
    ax.set_xticks(range(len(fams)), [f[1] for f in fams], fontsize=9.5)
    ax.xaxis.tick_top()
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([x - 0.5 for x in range(1, len(fams))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(rows))], minor=True)
    ax.grid(which="minor", color=GRID, lw=0.8)
    fig.suptitle("Without tools, only the nearest-contact question (G1) is reliably solved, and only from text",
                 x=0.01, ha="left", fontsize=12.5, fontweight="bold")
    fig.text(0.01, 0.905, "Hard set (v4), mean score per question family (4 questions each). DeepSeek CIF text: old "
             "text input, 15/20 replies empty at the token cap.", fontsize=9.5, color=MUTED)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(out, dpi=200)
    plt.close(fig)


def main() -> None:
    T, base, out_rows = {}, {}, []
    for ver, (real, mock) in RUNS.items():
        T[ver] = table(scored(real))
        base[ver] = random_baseline(scored(mock))
        for (m, c, f), v in sorted(T[ver].items()):
            out_rows.append(dict(set=ver, model=m, channel=c, family=f, **{k: (round(x, 4) if isinstance(x, float) else x) for k, x in v.items()}))
    (ROOT / "figures").mkdir(exist_ok=True)
    (ROOT / "analysis").mkdir(exist_ok=True)
    fig_channels(T, base, ROOT / "figures" / "v4_fig1_channels.png")
    fig_families(T, ROOT / "figures" / "v4_fig2_families.png")
    with open(ROOT / "analysis" / "results_v4.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        w.writeheader()
        w.writerows(out_rows)
    md = ["# Spatial sets: results (v3 easy set, v4 hard set)", "",
          "Generated by `scripts/make_figures_v4.py` from the scored runs `real-v3`, `real-v4` (random baseline: "
          "`mock-v3-e2e`, `mock-v4-final`). Score = mean partial credit, strict = all fields exactly right. "
          "Scores are shown with three decimals here; figures and text round halves up (0.425 -> 0.43).", ""]
    for ver in ("v4", "v3"):
        md += [f"## {ver} ({'hard' if ver == 'v4' else 'easy'} set), random baseline {base[ver]:.3f}", "",
               "| model | channel | score | strict | unparseable | output tokens | " + " | ".join(f for f, _ in FAMILIES[ver]) + " |",
               "|---|---|---|---|---|---|" + "---|" * len(FAMILIES[ver])]
        for m, _ in MODELS:
            for c, _ in CHANNELS:
                a = T[ver].get((m, c, "ALL"))
                if not a:
                    continue
                fs = " | ".join(r2(T[ver].get((m, c, f), {}).get("score", float("nan"))) for f, _ in FAMILIES[ver])
                md.append(f"| {m} | {c} | {a['score']:.3f} | {a['strict']:.3f} | {a['unparseable']} | {a['out_tokens']} | {fs} |")
        md.append("")
    (ROOT / "analysis" / "results_v4.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()