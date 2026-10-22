---
title: "CrystalSight: language models read a crystal's text well, but not its 3D space"
author: "Open Scientific Intelligence Hackathon 2026"
---

::: headline
**Key finding.** When a question about a crystal needs real 3D work (enumerating symmetry copies, following a hydrogen-bond network, counting neighbours), text-only reasoning collapses. From CIF text, two current models score 0.20–0.43, and from rendered images or an interactive ASCII 3D viewer 0.10–0.22 (random: 0.13). Give the same models small geometry tools and both reach about 0.75.
:::

**Question.** LLM agents are asked to check crystal structures, shown to them as CIF text, pictures, an interactive viewer or analysis tools. Does that choice decide what they can work out?

**Two sets of spatial questions** (20 each, five families of four). The *easy set* (v3) needs one contact or one plane: a donor–acceptor symmetry relation, the H-bond motif, nearest neighbours, a ring's orientation, π-stacking. The *hard set* (v4) needs exact enumeration or graph search, with atoms named in a copy-aware form `SITE#k[i,j,k]` (symmetry operation k, lattice shift [i,j,k]). Its five families are:

- **G1:** the acceptor copy nearest a given hydrogen;
- **G2:** the number of H-bond steps from a molecule to its own lattice translate;
- **G3:** the size of the smallest H-bond ring through a given bond, and how many molecules it spans;
- **G4:** how many molecules lie within a radius;
- **G5:** neighbour counts in the ordered major and minor replicas of a disordered structure.

Structures come from the Crystallography Open Database and MolCrysKit examples, plus a few licensed CSD entries. The CSD entries are used locally under anonymous ids and are not redistributed.

**Gold answers from geometry.** Gold answers are computed from symmetry-expanded coordinates. A hydrogen bond is D–H···A with D and A in {N, O}, H···A ≤ 2.5 Å and an angle of at least 120°. Every answer is recomputed with all cutoffs shifted by ±5 %, and questions whose answer changed were replaced. Partial credit per JSON field; a copy label earns credit for site, operation and shift separately.

**Five channels, one at a time:**

- CIF text with publication metadata stripped;
- unstripped CIF, as a leakage control;
- three rendered images;
- an interactive MatterVis ASCII 3D viewer (rotate, zoom, relabel, with an H-bond overlay, distance query and disorder-component switch);
- **geometry tools**: MolCrysKit plus six small tools built for this benchmark (H-bond list, nearest atoms, H-bond path, H-bond ring, neighbour shell, disorder components). The tools return raw lists, which the model must still count and interpret.

The models are GPT-6-Luna and DeepSeek-v4.1-Flash (text only), at temperature 0 with up to 32k output tokens.

![](../figures/v4_fig1_channels.png)

![](../figures/v4_fig2_families.png){.side}
**Results.** On the easy set, CIF text alone scores 0.70–0.82, and images and the viewer about 0.40. On the hard set, GPT-6-Luna's text scores fall to 0.37 (CIF) and 0.43 (unstripped CIF). DeepSeek returned no answer to 15 of 20 CIF questions: it reasoned until the 32k-token limit. Images (0.10) and the viewer (0.20–0.22) stay near chance. With geometry tools, both models reach 0.75–0.78 (strict 0.75).

The heatmap shows where text survives. G1, a single nearest contact, is solved from text (0.85–1.00). Paths, rings and counts mostly are not, and disorder replicas defeat every channel, tools included (0.25–0.38).

**Leak found and removed.** Many published CIFs include a precomputed hydrogen-bond table with symmetry codes. That table gives away G1 answers and the edges of the G2/G3 network, so for the hard set we remove it from both text channels. We also fixed a text-stripping bug that dropped the `loop_` keyword from CIF tables. GPT-6-Luna's text channels were re-run on the clean input (CIF 0.31 → 0.37, unstripped CIF 0.43 → 0.43). DeepSeek's CIF result and all easy-set text results still use the old input.

**Limitations.** 20 questions per set, 2 models, one run each: one question moves a score by 0.05. The tools were written for these question types, so they show what the right tools make possible, not a general agent. An earlier 247-question set of structure checks (missing H, disorder, coordination) showed the same ordering: text above images and the viewer. Code, tasks, gold and scored results are in the repository.

