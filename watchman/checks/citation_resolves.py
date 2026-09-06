"""A citation that points at an entry which does not exist reads perfectly and proves nothing; every E-number in a knowledge file must resolve to a log entry."""
# Descends from brain-ops conventions.md (2026-08-23): four writes cited E299 on the
# assumption the append would allocate 299; it allocated 311, and both numbers resolved.
import re

from ._util import Result, log_entries, read

NAME = "citation-resolves"


def run(cfg):
    c = cfg.section("citations")
    pat = re.compile(c.get("pattern", r"\bE(\d{3,})\b"))
    known = {r[2] for r in log_entries(cfg)}
    files = cfg.files(c.get("files", []))
    total, unresolved = 0, []
    for p in files:
        for i, line in enumerate((read(p) or "").splitlines(), 1):
            for m in pat.finditer(line):
                total += 1
                if int(m.group(1)) not in known:
                    unresolved.append(f"{cfg.rel(p)}:{i} {m.group(0)}")
    if unresolved:
        return Result(NAME, "FAIL", f"{len(unresolved)} of {total} citation(s) resolve to no "
                      f"entry: {', '.join(unresolved[:6])}. Read the number back after the "
                      f"append; never assume what it will allocate", total, 1)
    return Result(NAME, "PASS", f"{total} citation(s) in {len(files)} file(s) all resolve "
                  f"against {len(known)} entries", total, 1)
