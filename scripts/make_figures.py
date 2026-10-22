"""Generate publication figures from analysis/results.json and a real run.

Usage: python scripts/make_figures.py [--run real-full] [--example cod_2011852:Q4_disorder]
"""
import argparse, json, os, textwrap
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import image as mpimg

ROOT = Path(__file__).resolve().parents[1]
FAM = ["Q3_hydrogen", "Q4_disorder", "Q6_coordination", "Q7_usability", "Q8_compare"]
FAM_LABEL = {"Q3_hydrogen": "Q3 missing H", "Q4_disorder": "Q4 disorder",
             "Q6_coordination": "Q6 coordination", "Q7_usability": "Q7 usability",
             "Q8_compare": "Q8 pair compare"}
CHANNELS = ["cif", "cif_raw", "image", "tui"]
CH_LABEL = {"cif": "CIF text", "cif_raw": "CIF raw\n(leakage ctrl)", "image": "Image\n(3 views)", "tui": "Interactive\nTUI"}
MODELS = ["deepseek-v4-flash", "gemini-2.5-flash"]
BASE = ["baseline|no-problem/majority", "baseline|random"]
ROW_LABEL = {"deepseek-v4-flash": "DeepSeek-v4-Flash", "gemini-2.5-flash": "Gemini-2.5-Flash",
             "baseline|no-problem/majority": "Baseline: no-problem / majority",
             "baseline|random": "Baseline: random"}

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 10,
                     "savefig.dpi": 300, "figure.dpi": 100})


def run_dir(run):
    d = ROOT / "runs" / run
    return d if (d / "scored.jsonl").exists() else ROOT / "results" / run


def heat(ax, M, rows, cols, title, cmap="viridis", vmin=0.3, vmax=1.0):
    im = ax.imshow(M, cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(cols)), cols)
    ax.set_yticks(range(len(rows)), rows)
    ax.set_title(title)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            if np.isnan(v):
                ax.text(j, i, "n/a", ha="center", va="center", color="0.4", fontsize=8)
                ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1, fill=True, color="0.93", lw=0))
            else:
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8.5,
                        color="white" if v < (vmin + vmax) / 2 + .1 else "black")
    ax.axhline(len(MODELS) - .5, color="white", lw=3)
    return im


def fig_leaderboard(R, out):
    rows = MODELS + BASE
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.4), gridspec_kw={"width_ratios": [4, 4, 1.4], "wspace": 0.12})
    for ax, metric, title in [(axes[0], "mean", "Mean score (247 questions)"),
                              (axes[1], "macro_balanced", "Macro balanced score")]:
        M = np.full((len(rows), len(CHANNELS)), np.nan)
        for i, r in enumerate(rows):
            for j, c in enumerate(CHANNELS):
                key = r if r.startswith("baseline") else f"{r}|{c}"
                if key in R:
                    M[i, j] = R[key][metric]
        im = heat(ax, M, [ROW_LABEL[r] for r in rows], [CH_LABEL[c] for c in CHANNELS], title)
    axes[1].set_yticklabels([])
    # tools reference
    M = np.array([[R[f"{m}|tools"]["mean"], R[f"{m}|tools"]["macro_balanced"]] for m in MODELS])
    ax = axes[2]
    ax.imshow(M, cmap="Greys", vmin=0.3, vmax=1.4, aspect="auto")
    ax.set_xticks([0, 1], ["mean", "macro\nbal."])
    ax.set_yticks(range(2), ["DeepSeek", "Gemini"])
    ax.yaxis.tick_right()
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=8.5)
    ax.set_title("Tools (reference\nupper bound)")
    fig.colorbar(im, ax=axes[1], fraction=0.04, pad=0.02)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def fig_families(R, out):
    series = [("deepseek-v4-flash|cif", "DeepSeek · CIF", "#1f4e79"),
              ("gemini-2.5-flash|cif", "Gemini · CIF", "#6fa8dc"),
              ("deepseek-v4-flash|tui", "DeepSeek · TUI", "#b45f06"),
              ("gemini-2.5-flash|tui", "Gemini · TUI", "#f6b26b"),
              ("gemini-2.5-flash|image", "Gemini · Image", "#38761d")]
    series = [s for s in series if s[0] in R]
    fig, ax = plt.subplots(figsize=(8.5, 3.4))
    x = np.arange(len(FAM))
    w = 0.8 / len(series)
    for k, (key, lab, col) in enumerate(series):
        vals = [R[key].get(f"{f}_balanced", np.nan) for f in FAM]
        ax.bar(x - 0.4 + w * (k + .5), vals, w, label=lab, color=col, edgecolor="white", lw=.5)
    base = [R[BASE[0]].get(f"{f}_balanced", np.nan) for f in FAM]
    tools = [max(R[f"{m}|tools"].get(f"{f}_balanced", np.nan) for m in MODELS) for f in FAM]
    for i in range(len(FAM)):
        ax.hlines(base[i], i - .45, i + .45, colors="#cc0000", linestyles="--", lw=1.3,
                  label="No-problem / majority baseline" if i == 0 else None)
        ax.hlines(tools[i], i - .45, i + .45, colors="0.35", linestyles=":", lw=1.5,
                  label="Best tools run (reference)" if i == 0 else None)
    ns = [R["deepseek-v4-flash|cif"].get(f"{f}_n", "") for f in FAM]
    ax.set_xticks(x, [f"{FAM_LABEL[f]}\n(n={n})" for f, n in zip(FAM, ns)])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Balanced score")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(ncol=4, fontsize=7.5, frameon=False, loc="upper center", bbox_to_anchor=(.5, 1.22))
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def tui_excerpt(frame, width=78, height=26):
    lines = frame.splitlines()
    head = lines[0] if lines else ""
    body = [l.rstrip() for l in lines[1:]]
    nz = [i for i, l in enumerate(body) if l.strip()]
    if not nz:
        return head
    body = body[nz[0]:nz[-1] + 1]
    left = min(len(l) - len(l.lstrip()) for l in body if l.strip())
    body = [l[left:left + width] for l in body]
    if len(body) > height:
        s = (len(body) - height) // 2
        body = body[s:s + height]
    return "\n".join([head[:width]] + body)


def fmt(ans):
    if ans is None:
        return "(no answer)"
    if isinstance(ans, dict):
        parts = []
        for k, v in ans.items():
            if isinstance(v, list):
                v = "{" + ", ".join(map(str, v)) + "}" if v else "{}"
            parts.append(f"{k}={v}")
        return "; ".join(parts)
    return str(ans)


def fig_example(run, task_id, out):
    sid = task_id.split(":")[0]
    tasks = {json.loads(l)["id"]: json.loads(l) for l in open(ROOT / "tasks/tasks.jsonl", encoding="utf-8")}
    task = tasks[task_id]
    scored = [json.loads(l) for l in open(run_dir(run) / "scored.jsonl", encoding="utf-8")]
    scored = [r for r in scored if r["task_id"] == task_id]
    frame = ""
    rec = ROOT / f"runs/{run}/records.jsonl"
    if rec.exists():
        for l in open(rec, encoding="utf-8"):
            r = json.loads(l)
            if r.get("task_id") == task_id and r.get("channel") == "tui" and r.get("frames"):
                frame = r["frames"][-1]
                if r["model"].startswith("deepseek"):
                    break
    else:  # released compact copy
        fr = json.load(open(run_dir(run) / "tui_final_frames_examples.json", encoding="utf-8"))
        keys = sorted((k for k in fr if k.endswith("|" + task_id)), key=lambda k: not k.startswith("deepseek"))
        frame = fr[keys[0]] if keys else ""
    fig = plt.figure(figsize=(11, 6.2))
    gs = fig.add_gridspec(2, 2, width_ratios=[1, 1.3], height_ratios=[1.15, 1], hspace=.15, wspace=.12)
    ax = fig.add_subplot(gs[0, 0])
    img = ROOT / f"data/renders/{sid}_c.png"
    if img.exists():
        ax.imshow(mpimg.imread(img))
    ax.set_axis_off()
    ax.set_title(f"(a) Image-channel render, view c", loc="left")
    ax = fig.add_subplot(gs[0, 1])
    ax.set_axis_off()
    ax.set_title("(b) TUI channel: last ASCII frame seen by the agent", loc="left")
    ax.text(0, 1, tui_excerpt(frame), family="DejaVu Sans Mono", fontsize=5.4, va="top", ha="left",
            transform=ax.transAxes)
    ax = fig.add_subplot(gs[1, :])
    ax.set_axis_off()
    q = task["question"].split(" Types:")[0]
    txt = f"(c) Structure {sid} (COD). Question ({task['qtype']}): " + "\n".join(textwrap.wrap(q, 150))
    txt += "\n\nGold (from MolCrysKit + documented rule): " + fmt(task["gold"])
    ax.text(0, 1, txt, va="top", ha="left", fontsize=8.5, transform=ax.transAxes)
    order = {c: i for i, c in enumerate(CHANNELS + ["tools"])}
    scored.sort(key=lambda r: (r["model"], order.get(r["channel"], 9)))
    rows = [[ROW_LABEL.get(r["model"], r["model"]), r["channel"], fmt(r.get("answer")), f"{r['score']:.2f}"]
            for r in scored]
    tb = ax.table(cellText=rows, colLabels=["Model", "Channel", "Answer", "Score"], loc="lower left",
                  cellLoc="left", colWidths=[.16, .08, .66, .06], bbox=[0, 0, 1, .66])
    tb.auto_set_font_size(False)
    tb.set_fontsize(7.5)
    for (i, j), c in tb.get_celld().items():
        c.set_edgecolor("0.85")
        if i == 0:
            c.set_text_props(weight="bold")
            c.set_facecolor("0.92")
        if i > 0:
            c._loc = "left"
        if i > 0 and j == 3:
            v = float(rows[i - 1][3])
            c.set_facecolor((1, .85, .85) if v < .5 else ((1, .95, .8) if v < 1 else (.87, .95, .87)))
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="real-full")
    ap.add_argument("--results", default="analysis/results.json")
    ap.add_argument("--example", default="cod_2014451:Q6_coordination")
    ap.add_argument("--out", default="figures")
    a = ap.parse_args()
    out = ROOT / a.out
    out.mkdir(exist_ok=True)
    R = json.load(open(ROOT / a.results, encoding="utf-8"))
    fig_leaderboard(R, out / "fig1_leaderboard.png")
    fig_families(R, out / "fig2_families.png")
    fig_example(a.run, a.example, out / "fig3_example.png")
    print("wrote", sorted(p.name for p in out.glob("*.png")))


if __name__ == "__main__":
    main()
