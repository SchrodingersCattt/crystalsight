## Framing (v4-final, narration re-record)

One-pager / social headline: **Can AI perceive 3D crystal structure?**

Key finding (same numbers as narration, spoken as tenths):
- Easy text: ~0.70–0.82 → "seven to eight tenths"
- Hard text: ~0.20–0.43 → "two to four tenths"
- Hard + tools: ~0.75–0.78 → "near three-quarters"

Results-segment TTS was re-recorded (Microsoft Zira Desktop, Rate=-1) with the six new story lines below. Subtitles match the new audio.

# Demo video v3: what changed

`CrystalSight_demo_v3.mp4` is `CrystalSight_demo_v2.mp4` with only its results segment replaced. v1 and v2 are unchanged.

| part | v2 time | v3 time | content |
|---|---|---|---|
| opening example, design | 00:00.0–01:11.05 | 00:00.0–01:11.05 | unchanged (v2 cues 1–18). New caption for 00:00–00:25.9: the opening example comes from the earlier structure-check set (Gemini-2.5-Flash, DeepSeek-v4-Flash), and the spatial results use GPT-6-Luna and DeepSeek-v4.1-Flash |
| scoring details of the v1 set | 01:11.05–01:35.49 | cut | v2 cues 19–25 (baselines and balanced score of the v1 set) |
| channels | 01:35.49–01:57.45 | 01:11.05–01:33.01 | unchanged (v2 cues 26–30) |
| results | 01:57.45–03:15.43 (v1 results) | 01:33.01–02:18.70 | new story lines + Zira TTS (~45.7 s, six shots) |
| v1 limitations and "next" | 03:15.43–03:40.99 | cut | v2 cues 47–53 |
| close | 03:40.99–end | 02:18.70–end (~02:31.2) | unchanged (v2 cues 54–57) |

The video is cut only: everything outside the results segment is the original v2 footage and audio. Resolution and encoding match v2 (1920×1080, 30 fps, H.264, AAC 48 kHz stereo). Total length ≈ 2:31 (≤ 4 min).

## New results segment (~46 s, six shots)

1. Slide "Two spatial question sets": opener — can AI see a crystal as space?
2. Figure 1 (`figures/v4_fig1_channels.png`): hundreds of spatial questions, easy to hard.
3. Screen capture of the v4 report page (`reports/real-v4/index.html`): easy text prompts land around seven to eight tenths.
4. Tools slide: hard text-only falls to two to four tenths; words alone are not enough. (Visual still shows the tool call example while the line sets up the gap.)
5. Figure 2 (`figures/v4_fig2_families.png`): hand them tools to look and measure — hard accuracy near three-quarters.
6. Slide "Checks and caveats": CrystalSight takeaway — structure becomes readable when models can perceive, not only predict from prose.

## Caveat: narration voice

The source of the original narration voice was not in the repository. The results segment uses offline Windows TTS ("Microsoft Zira Desktop"). Voice therefore changes for ~46 s relative to the v2 body. Subtitles in the segment have at most 42 characters per line and two lines per cue.

Narration, one line per shot (spoken 2026-10-23 Asia/Shanghai morning re-record):

1. So can AI actually see a crystal—not as a spreadsheet, but as space?
2. We asked hundreds of spatial questions on real structures, from easy neighbor checks to hard geometry.
3. On easy text prompts, models already land around seven to eight tenths.
4. On the hard set, text-only scores fall to roughly two to four tenths—words alone are not enough.
5. Hand them tools to look and measure, and hard accuracy climbs back near three-quarters.
6. CrystalSight's takeaway: structure becomes readable when models can perceive, not only predict from prose.

Shot timings within the results segment (lead 0.10 s, 0.55 s gaps, ~0.5 s tail):

| shot | start–end (segment-local) | ~duration |
|---|---|---|
| 1 | 0.10–6.39 | 6.3 s |
| 2 | 6.94–14.41 | 7.5 s |
| 3 | 14.96–20.97 | 6.0 s |
| 4 | 21.52–29.70 | 8.2 s |
| 5 | 30.25–36.56 | 6.3 s |
| 6 | 37.11–45.19 | 8.1 s |

Absolute in the assembled file: segment starts at 01:33.01; ends ~02:18.70.

Build scripts (not part of the repository): `_scratch/video3/tts_lines.ps1` (Zira WAV per line), `rebuild_narration.py` (concat + cues), `make_segment2.py` (frames + burned-in subs), `assemble3.py` (ffmpeg concat of v2[0–71.05 s] + v2[95.49–117.45 s] + segment + v2[220.99 s–end], with the opening caption drawn as text).