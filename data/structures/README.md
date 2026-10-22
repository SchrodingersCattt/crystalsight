# Structure data (public distribution)

**Copyright / redistribution note.** Seventeen MolCrysKit example CIFs previously tracked under `data/structures/mck/` were obtained from the Cambridge Structural Database (CSD) via the Cambridge Crystallographic Data Centre (CCDC) download banners (MolCrysKit / CCDC query workflow). Exact obtainment date and CSD/CCDC database version are not recorded in the repository metadata and are therefore unknown; the files carried standard CCDC download banners and CSD refcodes. Because CSD/CCDC crystal structure data may not be redistributed under the CCDC licence terms applicable to those downloads, those CIFs and their matching `data/gt/mck_*.json` ground-truth files have been removed from this public repository. Redistributable COD structures and non-CSD MolCrysKit examples (e.g. NaCl, Diamond, caffeine CGD examples, DAP-4_order, MAP_H, 368K) remain. Any additional CSD-derived structures used for licensed-local evaluation stay only under the gitignored path `data/structures/ccdc_local/` and must not be published. Users with a CSD licence can regenerate local copies themselves; do not commit them.

## Shipped layout
- `cod/` — Crystallography Open Database CIFs (open / CC0-like)
- `mck/` — only non-CSD MolCrysKit examples safe to redistribute
- `ccdc_local/` — gitignored; local CSD-derived files only (never publish)
