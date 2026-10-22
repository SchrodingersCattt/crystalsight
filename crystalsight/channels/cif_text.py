"""Channel 1: the CIF file as text (baseline).

strip=True removes metadata that states the answer outright (formula/moiety
records, chemical names, Z, free-text) so the model must read the atom table.
For v4 tasks, both channels also drop _geom_hbond_* tables (strip_hbond_loops).
"""

from __future__ import annotations

import re
from pathlib import Path

from ..paths import ROOT
from .base import SYSTEM, Channel, answer_instructions, task_structures

MAX_CHARS = 60000
STRIP_PREFIX = re.compile(
    r"^_(chemical_formula|chemical_name|chemical_compound|cell_formula_units_Z|exptl_|journal_|publ_|"
    r"citation_|database_|cod_|computing_|refine_|reflns_|diffrn_|audit_|chemical_melting|chemical_absolute)",
    re.I,
)


def _skip_value(lines: list[str], i: int) -> int:
    """Index after the value that starts at lines[i] (a ;-delimited block or one line)."""
    if i < len(lines) and lines[i].startswith(";"):
        i += 1
        while i < len(lines) and not lines[i].startswith(";"):
            i += 1
        return i + 1  # past the closing ';'
    return i + 1


def strip_cif(text: str) -> str:
    """Remove comments and the STRIP_PREFIX items.  Loops survive intact (including their ``loop_`` keyword)
    unless every header tag is stripped, in which case the whole loop (keyword, tags, data rows) is removed."""
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("#"):
            i += 1
            continue
        if s.lower() == "loop_":
            j = i + 1
            tags = []
            while j < len(lines) and lines[j].strip().startswith("_"):
                tags.append(lines[j].strip())
                j += 1
            if tags and all(STRIP_PREFIX.match(tg) for tg in tags):
                # drop the data rows too, up to the next tag / loop / data block
                while j < len(lines):
                    sj = lines[j].strip()
                    if sj.startswith(("_", "data_")) or sj.lower() == "loop_":
                        break
                    j = _skip_value(lines, j) if lines[j].startswith(";") else j + 1
                i = j
                continue
            out.append(line)
            out.extend(lines[i + 1:j])
            i = j
            continue
        if STRIP_PREFIX.match(s):
            parts = s.split(None, 1)
            i = _skip_value(lines, i + 1) if len(parts) == 1 else i + 1
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


HBOND_TAG = re.compile(r"^_geom_hbond_", re.IGNORECASE)


def strip_hbond_loops(text: str) -> str:
    """Remove precomputed hydrogen-bond tables (_geom_hbond_* loops or single items), keeping every other line
    byte-identical.  Used for v4 in BOTH text channels: the tables list D-H...A with CIF symmetry codes, which
    directly give the v4 G1 answers and the edges of the G2/G3 H-bond graph.  _geom_bond/_geom_angle are kept."""
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if s.lower() == "loop_":
            j = i + 1
            tags = []
            while j < len(lines) and lines[j].strip().startswith("_"):
                tags.append(lines[j].strip())
                j += 1
            if tags and all(HBOND_TAG.match(tg) for tg in tags):
                while j < len(lines):
                    sj = lines[j].strip()
                    if sj.startswith(("_", "data_")) or sj.lower() == "loop_":
                        break
                    j = _skip_value(lines, j) if lines[j].startswith(";") else j + 1
                i = j
                continue
            out.extend(lines[i:j])
            i = j
            continue
        if HBOND_TAG.match(s):
            i = _skip_value(lines, i + 1) if len(s.split(None, 1)) == 1 else i + 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


class CifTextChannel(Channel):
    def __init__(self, strip: bool = True):
        self.strip = strip
        self.name = "cif" if strip else "cif_raw"

    def run(self, task, model):
        rec = {"channel": self.name, "steps": 0}
        structs = task_structures(task)
        limit = MAX_CHARS // len(structs)
        blocks, total, truncated = [], 0, False
        for st in structs:
            text = Path(ROOT / st["path"]).read_text(encoding="utf-8", errors="replace")
            if task.get("benchmark") == "v4":  # both cif and cif_raw: no precomputed H-bond tables (see DESIGN.md)
                text = strip_hbond_loops(text)
            if self.strip:
                text = strip_cif(text)
            tr = len(text) > limit
            truncated = truncated or tr
            text = text[:limit]
            total += len(text)
            head = f"CIF file{' of structure ' + st['label'] if st['label'] else ''}{' (truncated)' if tr else ''}:"
            blocks.append(f"{head}\n```\n{text}\n```")
        text = "\n\n".join(blocks)
        rec["input_chars"] = total
        rec["truncated"] = truncated
        user = f"Question: {task['question']}\n{answer_instructions(task)}\n\n{text}"
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
        self.log_turn(rec, "user", f"<CIF text, {len(text)} chars>\nQuestion: {task['question']}")
        r = model.complete(msgs, context={"task": task, "channel": self.name, "step": 0})
        self.usage_add(rec, r.usage, r.latency_ms)
        if r.error:
            rec["error"] = r.error
            rec["answer"] = None
            return rec
        self.log_turn(rec, "assistant", r.text[-4000:])
        rec["steps"] = 1
        return self.final(rec, r.text)