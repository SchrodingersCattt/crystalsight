"""Channel 1: the CIF file as text (baseline).

strip=True removes metadata that states the answer outright (formula/moiety
records, chemical names, Z, free-text) so the model must read the atom table.
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


def strip_cif(text: str) -> str:
    out, skip_multiline = [], False
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("#"):
            i += 1
            continue
        if STRIP_PREFIX.match(s):
            # skip value on same line, or a following ;-delimited block / single value line
            if len(s.split(None, 1)) == 1 and i + 1 < len(lines):
                if lines[i + 1].startswith(";"):
                    i += 2
                    while i < len(lines) and not lines[i].startswith(";"):
                        i += 1
                i += 1
            i += 1
            continue
        out.append(line)
        i += 1
    text = "\n".join(out)
    # drop loops whose header tags were all stripped (left as bare "loop_" followed by data)
    text = re.sub(r"loop_\s*\n(?=\s*loop_|\s*data_|\s*_)", "", text)
    return text


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