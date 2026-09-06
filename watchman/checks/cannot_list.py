"""A capability tested once, found missing and written down becomes a rule that nothing re-tests; every written-down "cannot" carries a re-test date, and an expired one must be re-tested before it is obeyed."""
# Descends from brain-ops conventions.md, corrected 2026-08-23: a session refused a
# prompt edit on the strength of a paragraph saying it was impossible; it was not.
import os

from ._util import Result, parse_date, read, table_rows, today

NAME = "cannot-list"


def run(cfg):
    c = cfg.section("cannots")
    path = cfg.path(c["file"])
    if not os.path.exists(path):
        return Result(NAME, "FAIL", f"{c['file']} does not exist. If nothing has ever been "
                      f"found impossible, say so in a row; a missing list is not a clean one",
                      0, 1)
    rows = table_rows(read(path), c.get("key", "Date"))
    t = today(cfg)
    expired, undated = [], []
    for _, header, cells in rows:
        col = {k: i for i, k in enumerate(header)}
        claim = cells[col.get("Cannot", 1)] if col.get("Cannot", 1) < len(cells) else "?"
        i = col.get("Re-test by")
        due = parse_date(cells[i]) if i is not None and i < len(cells) else None
        if due is None:
            undated.append(claim[:40])
        elif due < t:
            expired.append(f"{claim[:40]!r} (due {due})")
    if undated:
        return Result(NAME, "FAIL", f"{len(undated)} cannot(s) carry no re-test date: "
                      f"{undated[:3]}. A cannot without a date is permanent by accident",
                      len(rows), 1)
    if expired:
        return Result(NAME, "WARN", f"{len(expired)} of {len(rows)} cannot(s) past their "
                      f"re-test date: {'; '.join(expired[:3])}. Re-test a written-down "
                      f"cannot before obeying it", len(rows), 1)
    return Result(NAME, "PASS", f"{len(rows)} cannot(s) on file, all inside their re-test "
                  f"window", len(rows), 1)
