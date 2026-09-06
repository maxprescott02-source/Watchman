"""Nothing watches the watchman unless the watchman leaves a mark; every run writes one, and a second runner that finds it stale fails on that alone."""
# Descends from brain-ops assertion 41 (Entry 158, F9): the only alive-signal for the
# sweeper was a weekly log line a human had to notice the absence of.
import datetime
import json
import os

from ._util import Result, now

NAME = "heartbeat"


def read(cfg):
    try:
        with open(cfg.heartbeat, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def write(cfg, results, sizes):
    counts = {s: sum(1 for r in results if r.status == s) for s in ("PASS", "WARN", "FAIL")}
    os.makedirs(os.path.dirname(cfg.heartbeat) or ".", exist_ok=True)
    tmp = cfg.heartbeat + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"ran_at": now(cfg).isoformat(), "counts": counts, "sizes": sizes}, fh, indent=1)
    os.replace(tmp, cfg.heartbeat)


def age_hours(cfg, hb):
    try:
        ran = datetime.datetime.fromisoformat(hb["ran_at"])
    except (KeyError, TypeError, ValueError):
        return None
    return (now(cfg) - ran).total_seconds() / 3600


def run(cfg, first_run_ok=True):
    """Read the mark the previous run left. `first_run_ok` is False for a second
    runner, where a missing heartbeat means the first runner has never run."""
    max_age = float((cfg.section("watchman") or {}).get("heartbeat_max_age_hours", 30))
    hb = read(cfg)
    if hb is None:
        status = "WARN" if first_run_ok else "FAIL"
        return Result(NAME, status, f"no heartbeat at {cfg.rel(cfg.heartbeat)}; either this "
                      f"is the first run or nothing has been running", 0, 0)
    age = age_hours(cfg, hb)
    if age is None:
        return Result(NAME, "FAIL", "heartbeat present but its timestamp does not parse", 1, 1)
    c = hb.get("counts", {})
    tail = (f"last run {age:.1f}h ago reported {c.get('PASS', '?')} passed, "
            f"{c.get('WARN', '?')} warned, {c.get('FAIL', '?')} failed")
    if age > max_age:
        return Result(NAME, "FAIL", f"heartbeat is {age:.0f}h old, limit {max_age:.0f}h. The "
                      f"watchman stopped running and nothing else would have said so · {tail}",
                      1, 1)
    return Result(NAME, "PASS", tail, 1, 1)
