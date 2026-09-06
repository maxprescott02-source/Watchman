"""A step that skipped because it could not do its job leaves no bytes anywhere a check looks; age the skips the step itself declared degraded, and fail a job that ended without the thing it exists to produce."""
# Descends from brain-ops assertion 51 (2026-08-21): the nightly sweep over now.md
# gated itself off, the skip was recorded in a state file nothing opened, board green.
import datetime
import glob
import json
import os

from ._util import Result, parse_date

NAME = "degraded-steps"


def _states(cfg, c):
    out = []
    for p in sorted(glob.glob(os.path.join(cfg.path(c["state_dir"]), "*.json"))):
        try:
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        day = parse_date(d.get("day"))
        if day and d.get("job"):
            out.append((day, d))
    return sorted(out, key=lambda t: t[0], reverse=True)


def run(cfg):
    c = cfg.section("degraded")
    fail_after = int(c.get("fail_after", 8))
    # A job may declare degradation as a flag or as a marker inside its result text
    # (brain-ops writes "DEGRADED: <reason>"); both are the step's own declaration.
    marker = c.get("degraded_marker")
    states = _states(cfg, c)
    by_job = {}
    for day, d in states:
        by_job.setdefault(d["job"], {})[day] = d
    runs, missing, steps = {}, [], 0
    for job, days in by_job.items():
        newest = max(days)
        d = days[newest]
        if d.get("ended") and d.get("artefact") and not os.path.exists(cfg.path(d["artefact"])):
            missing.append(f"{job} ended {newest} without {d['artefact']}")
        for step in {s for x in days.values() for s in x.get("done", {})}:
            steps += 1
            n, cur = 0, newest
            while cur in days:
                e = days[cur].get("done", {}).get(step)
                if not isinstance(e, dict):
                    break
                declared = bool(e.get("degraded")) or (marker and marker in str(e.get("result", "")))
                if not declared:
                    break
                n, cur = n + 1, cur - datetime.timedelta(days=1)
            if n:
                runs[(job, step)] = (n, str(days[newest]["done"][step].get("result", ""))[:120])
    tail = f" · {len(states)} state file(s), {steps} step(s) examined"
    if missing:
        return Result(NAME, "FAIL", "; ".join(missing) + ". An ended job without its "
                      "primary artefact is a run that printed complete over nothing" + tail,
                      len(states), 1)
    hard = {k: v for k, v in runs.items() if v[0] >= fail_after}
    if hard:
        (j, s), (n, why) = next(iter(hard.items()))
        return Result(NAME, "FAIL", f"{j} step {s} degraded {n} consecutive nights "
                      f"(limit {fail_after}): {why}" + tail, len(states), 1)
    if runs:
        (j, s) = max(runs, key=lambda k: runs[k][0])
        n, why = runs[(j, s)]
        return Result(NAME, "WARN", f"{len(runs)} step(s) degraded, longest {j} step {s} "
                      f"at {n} of {fail_after} nights: {why}" + tail, len(states), 1)
    return Result(NAME, "PASS", "no step is skipping because it could not do its job" + tail,
                  len(states), 1)
