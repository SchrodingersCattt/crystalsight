# CrystalSight results (real-full)

Tasks: 247 questions (Q3_hydrogen 67, Q4_disorder 67, Q6_coordination 11, Q7_usability 67, Q8_compare 35); 67 structures. Scores are partial-credit means in [0, 1] (see crystalsight/score.py).

**Balanced** = per family, the mean of the score on structures that have the problem and on those that do not (Q3 missing H, Q4 disordered, Q7 not usable); Q6/Q8 use the plain mean. **Macro** = average over the 5 families. **Problem subset** = mean score on the flagged-problem questions only (Q3/Q4/Q7, n=52).

## Leaderboard

| model | channel | mean | macro balanced | problem subset | Q3 | Q4 | Q6 | Q7 | Q8 |
|---|---|---|---|---|---|---|---|---|---|
| deepseek-v4-flash | cif | 0.950 | 0.934 | 0.842 | 0.868 | 0.878 | 1.000 | 0.955 | 0.971 |
| deepseek-v4-flash | cif_raw (leakage control) | 0.947 | 0.925 | 0.823 | 0.835 | 0.872 | 1.000 | 0.949 | 0.971 |
| gemini-2.5-flash | cif_raw (leakage control) | 0.862 | 0.865 | 0.827 | 0.733 | 0.854 | 1.000 | 0.880 | 0.857 |
| gemini-2.5-flash | cif | 0.823 | 0.849 | 0.854 | 0.648 | 0.898 | 0.909 | 0.847 | 0.943 |
| deepseek-v4-flash | tui | 0.767 | 0.658 | 0.334 | 0.723 | 0.608 | 0.636 | 0.664 | 0.657 |
| gemini-2.5-flash | image | 0.669 | 0.612 | 0.468 | 0.759 | 0.484 | 0.636 | 0.666 | 0.514 |
| gemini-2.5-flash | tui | 0.481 | 0.571 | 0.728 | 0.653 | 0.516 | 0.636 | 0.566 | 0.486 |
| deepseek-v4-flash | tools (reference upper bound) | 0.968 | 0.963 | 0.904 | 0.956 | 0.870 | 1.000 | 0.991 | 1.000 |
| gemini-2.5-flash | tools (reference upper bound) | 0.958 | 0.955 | 0.895 | 0.965 | 0.894 | 1.000 | 0.943 | 0.971 |
| baseline | no-problem/majority | 0.678 | 0.474 | 0.000 | 0.500 | 0.500 | 0.500 | 0.500 | 0.371 |
| baseline | random | 0.435 | 0.336 | 0.345 | 0.477 | 0.411 | 0.109 | 0.461 | 0.223 |

Per-family columns show the balanced score.

## Problem vs clean subsets (Q3 / Q4 / Q7)

| model | channel | Q3 problem | Q3 clean | Q4 problem | Q4 clean | Q7 problem | Q7 clean |
|---|---|---|---|---|---|---|---|
| deepseek-v4-flash | cif | 0.787 | 0.948 | 0.757 | 1.000 | 0.910 | 1.000 |
| deepseek-v4-flash | cif_raw | 0.704 | 0.966 | 0.764 | 0.980 | 0.898 | 1.000 |
| gemini-2.5-flash | cif_raw | 0.620 | 0.845 | 0.806 | 0.902 | 0.909 | 0.850 |
| gemini-2.5-flash | cif | 0.657 | 0.638 | 0.854 | 0.941 | 0.919 | 0.775 |
| deepseek-v4-flash | tui | 0.567 | 0.879 | 0.215 | 1.000 | 0.327 | 1.000 |
| gemini-2.5-flash | image | 0.656 | 0.862 | 0.340 | 0.627 | 0.481 | 0.850 |
| gemini-2.5-flash | tui | 0.893 | 0.414 | 0.757 | 0.275 | 0.657 | 0.475 |
| deepseek-v4-flash | tools | 0.964 | 0.948 | 0.740 | 1.000 | 0.981 | 1.000 |
| gemini-2.5-flash | tools | 0.964 | 0.966 | 0.788 | 1.000 | 0.935 | 0.950 |
| baseline | no-problem/majority | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 | 1.000 |
| baseline | random | 0.426 | 0.528 | 0.296 | 0.525 | 0.347 | 0.575 |

## Detection of the problem flag (sensitivity / specificity)

| model | channel | Q3_hydrogen | Q4_disorder | Q7_usability |
|---|---|---|---|---|
| deepseek-v4-flash | cif | 0.89 / 0.95 | 0.94 / 1.00 | 0.93 / 1.00 |
| deepseek-v4-flash | cif_raw | 0.78 / 0.97 | 0.94 / 0.98 | 0.93 / 1.00 |
| deepseek-v4-flash | tui | 0.67 / 0.88 | 0.25 / 1.00 | 0.33 / 1.00 |
| gemini-2.5-flash | cif | 0.78 / 0.67 | 1.00 / 0.94 | 0.96 / 0.78 |
| gemini-2.5-flash | cif_raw | 0.67 / 0.84 | 1.00 / 0.90 | 1.00 / 0.85 |
| gemini-2.5-flash | image | 0.67 / 0.86 | 0.50 / 0.63 | 0.56 / 0.85 |
| gemini-2.5-flash | tui | 1.00 / 0.41 | 0.94 / 0.27 | 0.81 / 0.47 |
| deepseek-v4-flash | tools | 1.00 / 0.95 | 1.00 / 1.00 | 1.00 / 1.00 |
| gemini-2.5-flash | tools | 1.00 / 0.97 | 1.00 / 1.00 | 1.00 / 0.95 |

## Leakage control: stripped CIF (cif) vs raw CIF (cif_raw)

| model | Q3 | Q4 | Q6 | Q7 | Q8 | mean | macro |
|---|---|---|---|---|---|---|---|
| deepseek-v4-flash (raw - stripped) | +0.004 | -0.013 | +0.000 | -0.005 | +0.000 | -0.004 | -0.009 |
| gemini-2.5-flash (raw - stripped) | +0.174 | -0.041 | +0.091 | +0.041 | -0.086 | +0.039 | +0.016 |

## Illustrative failure cases

- **TUI misses disorder that the CIF text reveals** - deepseek-v4-flash / tui on `cod_2011852:Q4_disorder`: answered `{"disordered": false, "components": [], "types": []}`, gold `{"disordered": true, "components": ["solvent"], "types": ["partial_occupancy"]}` (score 0.00).
- **TUI misses disorder that the CIF text reveals** - deepseek-v4-flash / tui on `cod_2013465:Q4_disorder`: answered `{"disordered": false, "components": [], "types": []}`, gold `{"disordered": true, "components": ["main"], "types": ["partial_occupancy"]}` (score 0.00).
- **Image: wrong coordination number** - gemini-2.5-flash / image on `cod_2004754:Q6_coordination`: answered `{"cn": 4, "geometry": "tetrahedron"}`, gold `{"cn": 6, "geometry": "octahedron"}` (score 0.00).
- **Image: wrong coordination number** - gemini-2.5-flash / image on `cod_2014451:Q6_coordination`: answered `{"cn": 6, "geometry": "octahedron"}`, gold `{"cn": 7, "geometry": "pentagonal_bipyramid"}` (score 0.00).
- **Image/TUI: false alarm on missing H** - gemini-2.5-flash / tui on `cod_1008775:Q3_hydrogen`: answered `{"missing_h": true, "elements": ["O"]}`, gold `{"missing_h": false, "elements": []}` (score 0.00).
- **Comparison answered wrongly from pictures** - gemini-2.5-flash / image on `cod_2004754|cod_2001125:Q8_solvent`: answered `"B"`, gold `"neither"` (score 0.00).

Baselines: *no-problem/majority* answers 'no missing H', 'not disordered', 'usable' for Q3/Q4/Q7 and the majority gold for Q6 ({"cn": 4, "geometry": "tetrahedron"}) and Q8 ("B"); *random* is a seeded type-correct random answer (mock-random, averaged over channels).
