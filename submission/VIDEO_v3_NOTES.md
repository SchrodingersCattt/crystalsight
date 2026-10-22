# Demo video v3: what changed

`CrystalSight_demo_v3.mp4` is `CrystalSight_demo_v2.mp4` with only its results segment replaced. v1 and v2 are unchanged.

| part | v2 time | v3 time | content |
|---|---|---|---|
| intro, design, channels | 00:00.0–01:57.45 | 00:00.0–01:57.45 | unchanged (v2 cues 1–30) |
| results | 01:57.45–03:15.43 (v1 results) | 01:57.45–03:20.81 | new: spatial sets v3/v4 |
| limits, next steps, close | 03:15.43–end | 03:20.81–end (≈03:58.9) | unchanged (v2 cues 47–57) |

The total length is about 3:59, under the 4:00 limit. The resolution and encoding match v2 (1920×1080, 30 fps, H.264, AAC 48 kHz stereo).

## New results segment (≈83 s, six shots)

1. Slide "Two spatial question sets" (bridge from the structure checks; ±5 % robustness).
2. Figure 1 (`figures/v4_fig1_channels.png`): easy set text 0.70–0.82, hard set text 0.20–0.43.
3. Screen capture of the v4 report page (`reports/real-v4/index.html`, rendered by a headless browser). The camera pans from the headline and leaderboard down to the tools table and a recorded ASCII-viewer replay. Images and viewer score 0.10–0.22.
4. Tools: a real call from the run, `geom_hbond_ring`, re-executed to show its output (32 atoms, 6 molecules; gold 32, 6; score 1.00). Both models score about 0.75 with tools.
5. Figure 2 (`figures/v4_fig2_families.png`): only G1 is solved without tools, and G5 is hard for everything.
6. Slide "Checks and caveats": the H-bond-table leak was removed, the stripper was fixed, DeepSeek returned empty replies, and the sets are small.

## Caveat: narration voice

The source of the original narration voice was not in the repository. The new segment uses an offline Windows text-to-speech voice ("Microsoft Zira"), so the voice changes for about 83 s. If that is not acceptable, you have two options:

- Record the six lines below yourself and replace the audio of 01:57.45–03:20.81. Keep each line within its shot length, or retime the shots.
- Or ask for the segment to be rebuilt with a different voice.

Narration, one line per shot:

1. These structure checks put text ahead of pictures, but most could be answered from one line of the file. So we added two spatial sets of twenty questions each. Gold answers are computed from geometry and stay the same when every cutoff moves by five percent.
2. On the easy set, CIF text alone scores 0.70 to 0.82. On the hard set, which asks for symmetry copies, hydrogen-bond paths, rings and shell counts, text drops to 0.20 to 0.43.
3. Rendered images and the ASCII viewer stay near chance, at 0.10 to 0.22, even with a hydrogen-bond overlay and a distance query in the viewer.
4. Give the same models six small geometry tools that return raw lists, and both reach about 0.75. Here one call to the ring tool is enough for the right answer.
5. Per family, only the nearest-partner question is solved without tools. Disorder replicas stay hard for every channel.
6. We found that published hydrogen-bond tables leaked answers, removed them, fixed a stripping bug and re-ran the affected text channels. The sets are small, with two models, and the tools were written for these question types.

The unchanged closing segment still describes the v1 limitations ("67 structures", "coordination family has only 11 questions"). That is accurate for the v1 set, but the spoken limits do not mention the spatial sets beyond shot 6.

Build scripts (not part of the repository): a frame and narration builder, plus an ffmpeg concat of v2[0–117.45 s] + segment + v2[195.43 s–end].
