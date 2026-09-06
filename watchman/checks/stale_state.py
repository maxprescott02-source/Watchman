"""A read-first file is current only if its own marker names the latest source entry; mtime and a header date prove nothing, because the job that writes the body writes those too."""
# Descends from brain-ops assertion 6 (now.md current), rewritten 2026-08-15 after
# it reported a file that had missed 15 entries as ok on the strength of its date.
import datetime
import re

from ._util import Result, log_entries, today

NAME = "stale-state"


def run(cfg):
    c = cfg.section("stale_state")
    path = cfg.path(c["file"])
    marker = re.compile(c.get("marker", r"folded through Entry (\d+)"))
    grace = int(c.get("grace_days", 1))
    entries = log_entries(cfg)
    floor = int((cfg.section("log") or {}).get("floor", 1))
    try:
        with open(path, encoding="utf-8") as fh:
            head = "".join(fh.readline() for _ in range(int(c.get("head_lines", 5))))
    except OSError:
        return Result(NAME, "FAIL", f"{c['file']} missing or unreadable", len(entries), floor)
    m = marker.search(head)
    if not m:
        return Result(NAME, "FAIL", f"{c['file']} carries no marker matching "
                      f"{marker.pattern!r} in its head. The rebuild dropped its own "
                      f"currency mark, and the date cannot stand in for it",
                      len(entries), floor)
    folded = int(m.group(1))
    cutoff = str(today(cfg) - datetime.timedelta(days=grace - 1))
    stale = sorted({n for _, _, n, d in entries if n > folded and d < cutoff})
    ahead = sorted({n for _, _, n, d in entries if n > folded})
    if stale:
        return Result(NAME, "FAIL", f"{c['file']} folded through Entry {folded}, but "
                      f"{len(stale)} older entr{'y is' if len(stale) == 1 else 'ies are'} "
                      f"not in it: {stale[:8]}. Every session reads it without them",
                      len(entries), floor)
    note = f"{len(ahead)} written inside the grace period" if ahead else "nothing above it"
    return Result(NAME, "PASS", f"{c['file']} folded through Entry {folded} · {note} · "
                  f"{len(entries)} entries scanned", len(entries), floor)
