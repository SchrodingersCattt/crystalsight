# Social post (X / Twitter)

Fill-in links used below:
- REPO = https://github.com/SchrodingersCattt/crystalsight
- VIDEO = https://zenodo.org/records/23581207
- DOI / Zenodo record = https://zenodo.org/records/23581207

---

## Single post (main)

Can AI perceive 3D crystal structure?

CrystalSight turns crystal geometry into a spatial reading test—hundreds of questions on real CIFs across text, images, a terminal UI, and tool use.

Easy text: ~0.70–0.82
Hard text: ~0.20–0.43
Hard + tools: ~0.75–0.78

The gap is the story: models struggle to see structure from words alone, and regain it when they can inspect and measure.

Video: https://zenodo.org/records/23581207
Code: https://github.com/SchrodingersCattt/crystalsight

#OpenScience #Crystallography #AI #OSI2026

---

## Thread (optional follow-ups)

1/ CrystalSight is a multimodal crystal-structure VLM benchmark built on MolCrysKit + MatterVis (render | TUI). Same view, same structure—side-by-side so you can see what the model is asked to read.

2/ Easy questions (one contact / one plane) look solvable from CIF text. Hard questions need symmetry copies, H-bond paths, rings, and shell counts. Text accuracy collapses; images and the ASCII viewer stay near chance.

3/ Give the same models six small geometry tools that return raw lists, and hard-set scores climb back to ~0.75–0.78. The model still has to count and interpret—tools do not answer for it.

4/ Everything is open: tasks, ground truth, figures, and a mock run that needs no API key. Try your own model or add a channel.
Repo: https://github.com/SchrodingersCattt/crystalsight
Video: https://zenodo.org/records/23581207
