# CrystalSight: social posts

Placeholders: `[REPO LINK]` and `[VIDEO]`. On X, attach the video (under 4 minutes) natively to the main post. On LinkedIn, attach it or replace `[VIDEO]` with a link. X counts any URL as 23 characters and the 🔬 emoji as 2; the character counts below assume that.

**Hashtags:** the event page (luma.com/ku88xh92, checked 2026-10-22) lists no official hashtag, so these posts use generic tags. If the organizers announce an official tag or account before the deadline, add it to the X post and the LinkedIn post.

The numbers below come from `analysis/results_v4.md` (spatial sets v3/v4). The earlier v1 post text is in git history.

---

## X: main post (≤ 280 characters; COUNT_Can LLMs reason about a crystal in 3D, or only read its file?

CrystalSight: 40 spatial questions with geometry-derived gold, via CIF text, images, an ASCII 3D viewer or geometry tools.

Hard set: text 0.20–0.43, images/viewer 0.10–0.22, tools ~0.75.

#AI4Science 🔬 with the video attached)

```
Can LLMs reason about a crystal in 3D, or only read its file?

CrystalSight: 40 spatial questions with geometry-derived gold, via CIF text, images, an ASCII 3D viewer or geometry tools.

Hard set: text 0.20–0.43, images/viewer 0.10–0.22, tools ~0.75.

#AI4Science 🔬
```

## X: thread (each reply ≤ 280; counts 241, 262, 241 with the link)

**2/**
```
Two sets of 20. Easy (one contact or one plane): CIF text alone scores 0.70–0.82. Hard (symmetry copies, H-bond paths and rings, shell counts, disorder replicas): text reasoning collapses. Every gold answer is rechecked with all cutoffs ±5%.
```

**3/**
```
Without tools, only the single-contact question is reliably solved. Published H-bond tables in CIFs leaked answers: we removed them from both text channels, fixed a stripping bug and re-ran. An earlier 247-question set of structure checks gave the same ordering.
```

**4/**
```
Limits: 20 questions per set, 2 models, tools written for these question types, and DeepSeek returned empty replies on 15/20 hard CIF questions at a 32k-token cap. Code, tasks and gold are open:
[REPO LINK]
#MaterialsScience #LLM
```

---

## LinkedIn (~170 words)

```
Can a language model reason about a crystal in 3D, or does it only read the file well?

For the Open Scientific Intelligence Hackathon, I built CrystalSight. It has two sets of 20 spatial questions on molecular crystals, with gold answers computed from geometry and checked against ±5 % changes in every cutoff. Each question is asked through CIF text, rendered images, an interactive ASCII 3D viewer (MatterVis), or a small set of geometry tools.

What I found:
• Easy questions, where one contact or one plane is enough: CIF text alone scores 0.70–0.82.
• Hard questions, which need enumeration or graph search (symmetry copies, H-bond paths and rings, shell counts): text drops to 0.20–0.43, and images or the viewer stay near chance (0.10–0.22).
• With geometry tools, both models reach about 0.75.
• Published H-bond tables in CIF files leaked answers. I removed them and re-ran the affected text channels.

Caveats: 20 questions per set, two models, and tools written for these question types.

Video: [VIDEO]
Code and data: [REPO LINK]

#AI4Science #MaterialsScience #Chemistry #LLM
```
