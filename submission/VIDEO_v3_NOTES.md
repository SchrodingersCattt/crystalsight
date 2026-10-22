# Demo video v3: what changed

`CrystalSight_demo_v3.mp4` is `CrystalSight_demo_v2.mp4` with only its results segment replaced. v1 and v2 are unchanged.

| part | v2 time | v3 time | content |
|---|---|---|---|
| opening example, design | 00:00.0–01:11.05 | 00:00.0–01:11.05 | unchanged (v2 cues 1–18). New caption for 00:00–00:25.9: the opening example comes from the earlier structure-check set (Gemini-2.5-Flash, DeepSeek-v4-Flash), and the spatial results use GPT-6-Luna and DeepSeek-v4.1-Flash |
| scoring details of the v1 set | 01:11.05–01:35.49 | cut | v2 cues 19–25 (baselines and balanced score of the v1 set) |
| channels | 01:35.49–01:57.45 | 01:11.05–01:33.01 | unchanged (v2 cues 26–30) |
| results | 01:57.45–03:15.43 (v1 results) | 01:33.01–02:56.37 | new: spatial sets v3/v4 (narration unchanged since the previous v3) |
| v1 limitations and "next" | 03:15.43–03:40.99 | cut | v2 cues 47–53: the v1 limits (0.87–0.89, 67 structures, 11 questions) contradicted the new claims, and the "Limitations" panel stayed on screen during "Next" |
| close | 03:40.99–end | 02:56.37–end (≈03:08.9) | unchanged (v2 cues 54–57) |

The video is cut only: everything outside the results segment is the original v2 footage and audio. Resolution and encoding match v2 (1920×1080, 30 fps, H.264, AAC 48 kHz stereo).

## New results segment (≈83 s, six shots)

1. Slide "Two spatial question sets": bridge from the structure checks, ±5 % robustness, and the two models.
2. Figure 1 (`figures/v4_fig1_channels.png`, shown alone with its own title): easy set text 0.70–0.82, hard set text 0.20–0.43.
3. Screen capture of the v4 report page (`reports/real-v4/index.html`, rendered by a headless browser at 2× resolution), zoomed to the content column. The shot holds on the leaderboard, then moves to the tools table and a recorded ASCII-viewer replay. Images and viewer score 0.10–0.22.
4. Tools: a real call from the run, `geom_hbond_ring`, re-executed to show its output (32 atoms, 6 molecules; gold 32, 6; score 1.00). Both models score about 0.75 with tools.
5. Figure 2 (`figures/v4_fig2_families.png`, shown alone with its own title): only G1 is solved without tools, and G5 is hard for everything.
6. Slide "Checks and caveats": the H-bond-table leak was removed, the stripper was fixed, DeepSeek returned empty replies, and the sets are small.

## Caveat: narration voice

The source of the original narration voice was not in the repository. The new segment uses an offline Windows text-to-speech voice ("Microsoft Zira"), so the voice changes for about 83 s. This revision kept that narration unchanged and rebuilt only the pictures and subtitles. Subtitles in the segment now have at most 42 characters per line and two lines per cue. If that is not acceptable, you have two options:

- Record the six lines below yourself and replace the audio of 01:33.01–02:56.37. Keep each line within its shot length, or retime the shots.
- Or ask for the segment to be rebuilt with a different voice.

Narration, one line per shot:

1. These structure checks put text ahead of pictures, but most could be answered from one line of the file. So we added two spatial sets of twenty questions each. Gold answers are computed from geometry and stay the same when every cutoff moves by five percent.
2. On the easy set, CIF text alone scores 0.70 to 0.82. On the hard set, which asks for symmetry copies, hydrogen-bond paths, rings and shell counts, text drops to 0.20 to 0.43.
3. Rendered images and the ASCII viewer stay near chance, at 0.10 to 0.22, even with a hydrogen-bond overlay and a distance query in the viewer.
4. Give the same models six small geometry tools that return raw lists, and both reach about 0.75. Here one call to the ring tool is enough for the right answer.
5. Per family, only the nearest-partner question is solved without tools. Disorder replicas stay hard for every channel.
6. We found that published hydrogen-bond tables leaked answers, removed them, fixed a stripping bug and re-ran the affected text channels. The sets are small, with two models, and the tools were written for these question types.

Shot 5's narration says "nearest-partner question", while the figures now use "G1 nearest contact". The narration was not changed, so that wording difference remains. The burned-in subtitles of the original v2 footage are unchanged too: cue 15 still says "Crystallography Open Database" only, while the .srt file says "Crystallography Open Database and MolCrysKit examples".

Build scripts (not part of the repository): a frame and subtitle builder that reuses the existing narration audio, plus an ffmpeg concat of v2[0–71.05 s] + v2[95.49–117.45 s] + segment + v2[220.99 s–end], with the opening caption drawn as text.
