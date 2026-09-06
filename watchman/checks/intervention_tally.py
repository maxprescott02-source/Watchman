"""Every time the human did the agent's job is evidence a rule was never written down; count it, and a rising rate is the signal, not the individual row."""
# Descends from brain-ops tools/intervene.py and assertion 45 (2026-08-19): a
# 26,000-token paste was split by hand, cost a session, and nothing counted it.
import datetime
import os
import re

from ._util import Result, parse_date, read, today

NAME = "intervention-tally"
DISPOSITIONS = ("Rule", "Assertion", "Tool change", "Accepted", "Void")
NEEDS_WHY = "Accepted"
ROW = re.compile(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|(.*)\|\s*$")
HEADER = """# Interventions

One line every time the human had to do something the agent should have done.
Written only through `watchman intervene`. Not a to-do list; the weekly pass turns
each row into a rule, an assertion, a tool change, or an explicit acceptance with a
stated reason. "Noted" is not an outcome.

| Date | What they had to do | What it cost | What would remove it | Disposition |
|---|---|---|---|---|
"""


def rows(path):
    out = []
    for line in (read(path) or "").splitlines():
        if ROW.match(line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")] + [""] * 5
            out.append({"date": cells[0], "what": cells[1], "cost": cells[2],
                        "fix": cells[3], "disposition": cells[4]})
    return out


def parse_disposition(cell):
    cell = (cell or "").strip()
    for d in DISPOSITIONS:
        if cell == d:
            return d, ""
        for sep in (" - ", ": ", " \u2014 ", " \u2013 "):
            if cell.startswith(d + sep):
                return d, cell[len(d) + len(sep):].strip()
    return cell, ""


def add(cfg, what, cost, fix):
    path = cfg.path(cfg.section("interventions")["file"])
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(HEADER)
    clean = lambda s: (s or "").replace("|", "/").replace("\n", " ").strip()  # noqa: E731
    d = today(cfg).isoformat()
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"| {d} | {clean(what)} | {clean(cost)} | {clean(fix)} | |\n")
    return d, len(rows(path))


def run(cfg):
    c = cfg.section("interventions")
    path = cfg.path(c["file"])
    if not os.path.exists(path):
        return Result(NAME, "FAIL", f"{c['file']} does not exist. A missing tally must never "
                      f"score as zero friction; `watchman intervene \"...\"` creates it", 0, 1)
    rs = rows(path)
    if not rs:
        return Result(NAME, "FAIL", "the file holds no parseable rows; a header with no "
                      "table is a tally that has stopped being one", 0, 1)
    bad = []
    for i, r in enumerate(rs, 1):
        d, why = parse_disposition(r["disposition"])
        if d and d not in DISPOSITIONS:
            bad.append(f"row {i} -> {d[:24]!r}")
        elif d == NEEDS_WHY and not why:
            bad.append(f"row {i} Accepted with no reason")
    if bad:
        return Result(NAME, "FAIL", f"dispositions outside {DISPOSITIONS} or unreasoned: "
                      f"{'; '.join(bad[:3])}. Noted is not an outcome", len(rs), 1)
    t = today(cfg)
    window = int(c.get("window_days", 14))
    recent = sum(1 for r in rs if (parse_date(r["date"]) or t) > t - datetime.timedelta(days=window))
    prior = sum(1 for r in rs if t - datetime.timedelta(days=2 * window)
                < (parse_date(r["date"]) or t) <= t - datetime.timedelta(days=window))
    newest = max(r["date"] for r in rs)
    age = (t - (parse_date(newest) or t)).days
    open_ = sum(1 for r in rs if not r["disposition"])
    msg = (f"{len(rs)} row(s) · newest {newest} ({age}d ago) · {open_} awaiting disposition · "
           f"last {window}d: {recent}, the {window}d before: {prior}")
    if recent > prior and recent >= int(c.get("rising_floor", 3)):
        return Result(NAME, "WARN", msg + ". The rate is rising; each row is a rule that "
                      "was never written", len(rs), 1)
    if age > int(c.get("stale_days", 14)):
        return Result(NAME, "WARN", msg + ". Nothing recorded lately; a frictionless "
                      "fortnight is legitimate and indistinguishable from one nobody "
                      "recorded, so this warns rather than fails", len(rs), 1)
    return Result(NAME, "PASS", msg, len(rs), 1)
