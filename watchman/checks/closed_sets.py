"""A ledger heading nothing enforces is a suggestion; every row sits under one of a declared closed set of states, every ID parses once, and "Noted" is not an outcome."""
# Descends from brain-ops assertions 16 to 19 (2026-08-14): three anomalies were
# filed under the least wrong heading and written up as defect notes instead of fixed.
import re

from ._util import item, _plural, read, Result, table_rows

NAME = "closed-sets"


def run(cfg):
    ledgers = cfg.section("ledgers") or []
    problems, unconfirmed, items, total = [], [], [], 0
    for spec in ledgers:
        rel = spec["file"]
        # A guessed ledger (its states were read off the file) can only warn: the
        # row outside the set may be right and the guess wrong.
        found = unconfirmed if spec.get("guessed") else problems
        text = read(cfg.path(rel))
        if text is None:
            found.append(f"{rel} missing")
            items.append(item(f"ledger {rel} is missing",
                              f"Restore {rel} or fix the `file =` line in watchman.toml.",
                              files=[rel]))
            continue
        allowed = set(spec["states"])
        states_text = ", ".join(sorted(allowed))
        state_col = spec.get("state_column")
        # Two shapes: the state is the `## Heading` a row sits under (every state
        # must keep its heading), or the state is a column in one table.
        if not state_col:
            present = {l[3:].strip() for l in text.splitlines() if l.startswith("## ")}
            for want in allowed - present:
                found.append(f"{rel}: heading '{want}' has disappeared")
                items.append(item(f"{rel} has lost its '{want}' heading",
                                  f"Put the `## {want}` heading back in {rel}; rows under "
                                  f"it are otherwise in no state.", files=[rel]))
        rows = table_rows(text, spec.get("key", "ID"))
        if not rows:
            found.append(f"{rel}: no rows parsed under key '{spec.get('key', 'ID')}'; "
                         f"the parser saw nothing, which is not the same as nothing to see")
            items.append(item(f"{rel} has no table keyed on '{spec.get('key', 'ID')}'",
                              f"Check the first header cell of the table in {rel}, or the "
                              f"`key =` line in watchman.toml.", files=[rel]))
        idpat = re.compile(spec["id"]) if spec.get("id") else None
        seen = {}
        for heading, header, cells in rows:
            total += 1
            state = heading
            if state_col and state_col in header:
                i = header.index(state_col)
                state = cells[i].strip("* ") if i < len(cells) else ""
            row_id = cells[0][:24]
            where = f"its '{state_col}' column" if state_col else "its heading"
            if state not in allowed:
                found.append(f"{rel}: {row_id!r} carries '{state}', outside [{states_text}]")
                items.append(item(f"{rel}: row {row_id!r} carries '{state}', outside "
                                  f"[{states_text}]",
                                  f"Edit row {row_id!r} in {rel}: set {where} to one of "
                                  f"{states_text}, or add '{state}' to `states` in "
                                  f"watchman.toml if it is a real outcome.", files=[rel]))
            if idpat:
                m = idpat.match(cells[0])
                if not m:
                    found.append(f"{rel}: unparseable ID {row_id[:18]!r}")
                    items.append(item(f"{rel}: row {row_id[:18]!r} has no readable ID",
                                      f"Give row {row_id[:18]!r} in {rel} an ID matching "
                                      f"{spec['id']!r}.", files=[rel]))
                elif m.group(0) in seen and heading not in spec.get("id_unique_exempt", ["Void"]):
                    found.append(f"{rel}: {m.group(0)} appears twice")
                    items.append(item(f"{rel}: {m.group(0)} appears twice",
                                      f"Renumber one of the two {m.group(0)} rows in {rel}.",
                                      files=[rel]))
                else:
                    seen[m.group(0)] = heading
    if problems or unconfirmed:
        msg = []
        if problems:
            msg.append("; ".join(problems[:5]))
        if unconfirmed:
            msg.append("unconfirmed: " + "; ".join(unconfirmed[:5]))
        action = " ".join(i["action"] for i in items[:2])
        return Result(NAME, "FAIL" if problems else "WARN", " · ".join(msg) + ". " + action,
                      total, 1, items=items)
    return Result(NAME, "PASS", f"{total} rows across {_plural(len(ledgers), 'ledger')}, all in "
                  f"their closed sets", total, 1)
