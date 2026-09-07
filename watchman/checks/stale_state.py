"""A read-first file is current only if its own marker names the latest source entry; mtime and a header date prove nothing, because the job that writes the body writes those too."""
# Descends from brain-ops assertion 6 (now.md current), rewritten 2026-08-15 after
# it reported a file that had missed 15 entries as ok on the strength of its date.
#
# Two modes, chosen by what the marker's group captures:
#   entry mode  marker group is a number ("folded through Entry (\d+)"), compared
#               with the newest entry number in [log].files. The original.
#   date mode   marker group is a date ("Generated (\d{4}-\d{2}-\d{2})"), compared
#               with the newest change among `sources` globs (mtime, or the newest
#               timestamp written inside them), or with today when `sources` is empty.
#               The marker is still the file's own claim about itself; what changed
#               is what it is measured against.
import datetime
import os
import re

from ._util import DATE, item, log_entries, now, _plural, read, Result, today

NAME = "stale-state"
STAMP = re.compile(r"\b(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}):(\d{2}))?")


def _head(path, lines):
    with open(path, encoding="utf-8") as fh:
        return "".join(fh.readline() for _ in range(lines))


def _marker_date(s):
    m = STAMP.match(s.strip())
    if not m:
        return None
    try:
        d = datetime.date.fromisoformat(m.group(1))
    except ValueError:
        return None
    if m.group(2):
        return datetime.datetime.combine(d, datetime.time(int(m.group(2)), int(m.group(3))))
    return datetime.datetime.combine(d, datetime.time(0, 0))


def _newest_source(cfg, patterns, tz):
    """(when, description) of the newest change among the sources: a file's mtime,
    or the newest date or timestamp written inside it, whichever is later."""
    newest, which = None, None
    for p in cfg.files(patterns):
        when = datetime.datetime.fromtimestamp(os.path.getmtime(p), tz).replace(tzinfo=None)
        how = "modified"
        for m in STAMP.finditer(read(p) or ""):
            stamped = _marker_date(m.group(0))
            if stamped and stamped > when and stamped <= now(cfg).replace(tzinfo=None):
                when, how = stamped, "last wrote"
        if newest is None or when > newest:
            newest, which = when, f"{cfg.rel(p)} {how} {when.strftime('%Y-%m-%d %H:%M')}"
    return newest, which


def _action(file, due):
    """Every red line ends in the thing the operator does next. No cause is claimed:
    from the folder, a job that never fired and one that ran and wrote nothing look
    the same."""
    return (f"Check the job that writes {file}; it was due {due}. If it is safe to rerun, "
            f"run it now; if it already ran, check why {file} was not updated.")


def _date_mode(cfg, c, head, m, tz):
    stamped = _marker_date(m.group(1))
    grace = int(c.get("grace_days", 1))
    if stamped is None:
        return Result(NAME, "FAIL", f"{c['file']} marker matched {m.group(1)!r}, which is "
                      f"neither an entry number nor a date. The marker's group must capture "
                      f"one or the other", 1, 1)
    sources = c.get("sources", [])
    if sources:
        newest, which = _newest_source(cfg, sources, tz)
        if newest is None:
            return Result(NAME, "FAIL", f"{c['file']} says {m.group(1)}, but none of its "
                          f"sources {sources} exist to compare against. Fix the globs, or "
                          f"leave sources empty to measure against today", 1, 1)
        behind = (newest.date() - stamped.date()).days
        if behind > grace:
            due = f"after {which}"
            fact = f"{c['file']} says {m.group(1)}, but {which}, {_plural(behind, 'day')} later"
            return Result(NAME, "FAIL", f"{fact} (grace {grace}). Whatever reads "
                          f"{c['file']} is reading a picture from before that change. "
                          + _action(c["file"], due), 1, 1,
                          items=[item(fact, _action(c["file"], due), files=[c["file"]],
                                      says=stamped.isoformat())])
        return Result(NAME, "PASS", f"{c['file']} says {m.group(1)} · newest source: {which} "
                      f"· within {_plural(grace, 'day')}", 1, 1)
    behind = (today(cfg) - stamped.date()).days
    if behind > grace:
        due = f"by {stamped.date() + datetime.timedelta(days=grace)}"
        fact = f"{c['file']} is {_plural(behind, 'day')} old (it says {m.group(1)}, today is {today(cfg)})"
        return Result(NAME, "FAIL", f"{fact}, grace {grace}. The rebuild may not have run, "
                      f"this machine may have been off or asleep, or the rebuild may have "
                      f"run without updating it; anything reading the file does not know. "
                      + _action(c["file"], due),
                      1, 1, items=[item(fact, _action(c["file"], due), files=[c["file"]],
                                        says=stamped.isoformat())])
    return Result(NAME, "PASS", f"{c['file']} says {m.group(1)} · {_plural(behind, 'day')} old, "
                  f"within {grace} · measured against today (no sources listed)", 1, 1)


def run(cfg):
    c = cfg.section("stale_state")
    path = cfg.path(c["file"])
    marker = re.compile(c.get("marker", r"folded through Entry (\d+)"))
    if marker.groups < 1:
        return Result(NAME, "FAIL", f"[stale_state] marker {marker.pattern!r} has no "
                      f"capture group; wrap the number or the date in parentheses", 0, 1)
    grace = int(c.get("grace_days", 1))
    try:
        head = _head(path, int(c.get("head_lines", 5)))
    except OSError:
        return Result(NAME, "FAIL", f"{c['file']} missing or unreadable", 0, 1)
    m = marker.search(head)
    if not m:
        return Result(NAME, "FAIL", f"{c['file']} carries no marker matching "
                      f"{marker.pattern!r} in its first {int(c.get('head_lines', 5))} lines. "
                      f"The rebuild dropped its own currency mark, and the date cannot "
                      f"stand in for it", 1, 1)
    tz = datetime.timezone(datetime.timedelta(hours=cfg.utc_offset))
    if not m.group(1).strip().isdigit():
        return _date_mode(cfg, c, head, m, tz)
    entries = log_entries(cfg)
    floor = int((cfg.section("log") or {}).get("floor", 1))
    if not entries:
        return Result(NAME, "FAIL", f"{c['file']} says Entry {m.group(1)} but no log entries "
                      f"were found under [log].files; nothing to measure it against. If "
                      f"the marker is a date, not an entry number, the date form is "
                      f"marker = 'Generated (\\d{{4}}-\\d{{2}}-\\d{{2}})'", 0, floor)
    folded = int(m.group(1))
    cutoff = str(today(cfg) - datetime.timedelta(days=grace - 1))
    stale = sorted({n for _, _, n, d in entries if n > folded and d < cutoff})
    ahead = sorted({n for _, _, n, d in entries if n > folded})
    if stale:
        due = f"after Entry {stale[0]} was written"
        fact = (f"{c['file']} folded through Entry {folded}, but {len(stale)} older "
                f"entr{'y is' if len(stale) == 1 else 'ies are'} not in it: {stale[:8]}")
        return Result(NAME, "FAIL", f"{fact}. Every session reads it without them. "
                      + _action(c["file"], due), len(entries), floor,
                      items=[item(fact, _action(c["file"], due), files=[c["file"]])])
    note = f"{len(ahead)} written inside the grace period" if ahead else "nothing above it"
    return Result(NAME, "PASS", f"{c['file']} folded through Entry {folded} · {note} · "
                  f"{len(entries)} entries scanned", len(entries), floor)
