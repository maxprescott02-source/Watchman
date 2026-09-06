"""Every writer that computes the next entry number itself produces duplicates; numbers are allocated under a lock and the log fails on a duplicate or a step backwards."""
# Descends from brain-ops Entry 047 (62 headings carrying 46 distinct numbers) and
# assertions 1 and 2; tools/append-log.py allocates under flock and is the only writer.
import datetime
import os

from ._util import Result, log_entries, today

NAME = "append-only-log"


def append(cfg, title, body=""):
    """Allocate the next number under an exclusive lock and append in 'a' mode."""
    log = cfg.section("log") or {}
    target = cfg.path(log.get("write_to", "log/log.md"))
    fmt = log.get("write_format", "## {date} Entry {n} {title}")
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    lock_path = target + ".lock"
    with open(lock_path, "w") as lock:
        try:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
        except ImportError:                                     # Windows: no flock
            pass
        n = max((r[2] for r in log_entries(cfg)), default=0) + 1
        line = fmt.format(date=today(cfg).isoformat(), n=n, title=title.strip())
        with open(target, "a", encoding="utf-8") as fh:
            fh.write(("\n" if os.path.getsize(target) else "") + line + "\n"
                     + (body.rstrip() + "\n" if body else ""))
    return n, target


def run(cfg):
    log = cfg.section("log") or {}
    floor = int(log.get("floor", 1))
    rows = log_entries(cfg)
    nums = [r[2] for r in rows]
    dupes = sorted({n for n in nums if nums.count(n) > 1})
    if dupes:
        return Result(NAME, "FAIL", f"duplicate entry numbers {dupes[:8]}. Two writers each "
                      f"computed the next number; allocate under a lock", len(rows), floor)
    out_of_order = []
    by_file = {}
    for p, _, n, _ in rows:
        by_file.setdefault(p, []).append(n)
    for p, seq in by_file.items():
        if seq != sorted(seq):
            out_of_order.append(cfg.rel(p))
    if out_of_order:
        return Result(NAME, "FAIL", f"numbers do not ascend in {out_of_order}; a write landed "
                      f"mid-file", len(rows), floor)
    newest = max((r[3] for r in rows), default=None)
    stale_days = int(log.get("quiet_days", 3))
    if newest:
        try:
            age = (today(cfg) - datetime.date.fromisoformat(newest)).days
        except ValueError:
            return Result(NAME, "FAIL", f"newest entry carries unparseable date {newest!r}",
                          len(rows), floor)
        if age > stale_days:
            return Result(NAME, "WARN", f"{len(rows)} entries, distinct and ascending, but the "
                          f"newest is {age}d old; the writers may have stopped", len(rows), floor)
    return Result(NAME, "PASS", f"{len(rows)} entries across {len(by_file)} file(s), all "
                  f"distinct and ascending · newest {newest}", len(rows), floor)
