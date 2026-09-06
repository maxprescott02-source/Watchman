"""A ledger heading nothing enforces is a suggestion; every row sits under one of a declared closed set of states, every ID parses once, and "Noted" is not an outcome."""
# Descends from brain-ops assertions 16 to 19 (2026-08-14): three anomalies were
# filed under the least wrong heading and written up as defect notes instead of fixed.
import re

from ._util import Result, read, table_rows

NAME = "closed-sets"


def run(cfg):
    ledgers = cfg.section("ledgers") or []
    problems, total = [], 0
    for spec in ledgers:
        rel = spec["file"]
        text = read(cfg.path(rel))
        if text is None:
            problems.append(f"{rel} missing")
            continue
        allowed = set(spec["states"])
        present = {l[3:].strip() for l in text.splitlines() if l.startswith("## ")}
        for want in allowed - present:
            problems.append(f"{rel}: heading '{want}' has disappeared")
        rows = table_rows(text, spec.get("key", "ID"))
        if not rows:
            problems.append(f"{rel}: no rows parsed under key '{spec.get('key', 'ID')}'; "
                            f"the parser saw nothing, which is not the same as nothing to see")
        idpat = re.compile(spec["id"]) if spec.get("id") else None
        state_col = spec.get("state_column")
        seen = {}
        for heading, header, cells in rows:
            total += 1
            state = heading
            if state_col and state_col in header:
                i = header.index(state_col)
                state = cells[i].strip("* ") if i < len(cells) else ""
            if state not in allowed:
                problems.append(f"{rel}: {cells[0][:24]!r} carries '{state}', outside "
                                f"{sorted(allowed)}")
            if idpat:
                m = idpat.match(cells[0])
                if not m:
                    problems.append(f"{rel}: unparseable ID {cells[0][:18]!r}")
                elif m.group(0) in seen and heading not in spec.get("id_unique_exempt", ["Void"]):
                    problems.append(f"{rel}: {m.group(0)} appears twice")
                else:
                    seen[m.group(0)] = heading
    if problems:
        return Result(NAME, "FAIL", "; ".join(problems[:5]), total, 1)
    return Result(NAME, "PASS", f"{total} rows across {len(ledgers)} ledger(s), all in "
                  f"their closed sets", total, 1)
