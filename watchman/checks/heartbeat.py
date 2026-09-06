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


def write(cfg, results, sizes, incidents=None):
    """The mark: when, the counts, the sizes measured, and the open incidents so
    the next run can say which are new and which are still there."""
    counts = {s: sum(1 for r in results if r.status == s) for s in ("PASS", "WARN", "FAIL")}
    os.makedirs(os.path.dirname(cfg.heartbeat) or ".", exist_ok=True)
    tmp = cfg.heartbeat + ".tmp"
    open_incidents = [{"keys": i.keys, "since": i.since, "text": i.text, "short": i.short}
                      for i in (incidents or []) if i.state != "resolved"]
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"ran_at": now(cfg).isoformat(), "counts": counts, "sizes": sizes,
                   "incidents": open_incidents}, fh, indent=1)
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
        if first_run_ok:
            # A first run is not a warning: there is nothing to compare against yet,
            # and an operator reading amber on their first board reads it as a fault.
            return Result(NAME, "PASS", "first run over this folder; the next run will "
                          "compare against it", 0, 0)
        return Result(NAME, "FAIL", f"no heartbeat at {cfg.rel(cfg.heartbeat)}; nothing has "
                      f"been running. Run the board once by hand, then check the scheduler "
                      f"that should be running it nightly.", 0, 0)
    age = age_hours(cfg, hb)
    if age is None:
        return Result(NAME, "FAIL", "heartbeat present but its timestamp does not parse. "
                      f"Delete {cfg.rel(cfg.heartbeat)} and run the board again.", 1, 1)
    c = hb.get("counts", {})
    tail = (f"last run {age:.1f}h ago reported {c.get('PASS', '?')} passed, "
            f"{c.get('WARN', '?')} warned, {c.get('FAIL', '?')} failed")
    if age > max_age:
        return Result(NAME, "FAIL", f"heartbeat is {age:.0f}h old, limit {max_age:.0f}h. The "
                      f"watchman stopped running, or this machine was off or asleep, and "
                      f"nothing else would have said so · {tail}. Check the scheduler that "
                      f"runs watchman (crontab -l, or launchctl list on a Mac) and run the "
                      f"board once by hand.", 1, 1)
    return Result(NAME, "PASS", tail, 1, 1)
