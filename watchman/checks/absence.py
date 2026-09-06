"""A subject that has gone quiet relative to its own cadence is a finding; runs of silence are data, and nothing else on the board can see them."""
# Descends from brain-ops spec.md layer 1 ("runs of silence are data") and skill
# rule 4, "absence is data": going quiet for five nights says more than the sixth answer.
import os
import statistics

from ._util import DATE, Result, item, parse_date, read, today

NAME = "absence"
# Fewer dated files than this and the median gap is noise, not a cadence; the
# line stays green and says how much history there is.
MIN_HISTORY = 5


def _series(cfg, c, t):
    """[(label, sorted dates)]: one series per file in `files` (the dates written
    inside it) and one per folder in `dirs` (the dates in its file names, so a
    folder of daily notes is one subject, not thirty)."""
    out = []
    for p in cfg.files(c.get("files", [])):
        dates = {d for d in (parse_date(s) for s in DATE.findall(read(p) or "")) if d and d <= t}
        out.append((cfg.rel(p), sorted(dates)))
    for d in c.get("dirs", []):
        folder = cfg.path(d)
        if not os.path.isdir(folder):
            out.append((d + "/", None))
            continue
        dates = set()
        for name in os.listdir(folder):
            for s in DATE.findall(name):
                dd = parse_date(s)
                if dd and dd <= t:
                    dates.add(dd)
        out.append((d.rstrip("/") + "/", sorted(dates)))
    return out


def run(cfg):
    c = cfg.section("absence")
    min_dates = max(int(c.get("min_dates", MIN_HISTORY)), MIN_HISTORY)
    factor = float(c.get("factor", 2.0))
    min_days = int(c.get("min_days", 3))
    t = today(cfg)
    measured, quiet, missing, thin, items, dated = 0, [], [], [], [], 0
    for label, dates in _series(cfg, c, t):
        if dates is None:
            missing.append(label)
            continue
        dated += len(dates)
        if len(dates) < min_dates:
            thin.append((label, len(dates)))
            continue
        measured += 1
        gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
        usual = max(statistics.median(gaps), 1)
        since = (t - dates[-1]).days
        if since > max(usual * factor, min_days):
            fact = f"{label} has gone quiet (last dated {dates[-1]}, {since}d ago, usual gap {usual:.0f}d)"
            action = (f"Open {label} and decide whether it is really quiet or whether the "
                      f"notes moved.")
            quiet.append(f"{label} (last dated {dates[-1]}, {since}d ago, usual gap {usual:.0f}d)")
            items.append(item(fact, action, files=[label]))
    if missing:
        return Result(NAME, "FAIL", f"[absence] dirs that do not exist: {missing}. Fix the "
                      f"`dirs =` line in watchman.toml or create the folder.", measured, 1)
    thin_note = f" · {len(thin)} series with not enough history yet" if thin else ""
    if quiet:
        action = " ".join(i["action"] for i in items[:2])
        return Result(NAME, "WARN", f"{len(quiet)} of {measured} gone quiet against their own "
                      f"cadence: {'; '.join(quiet[:4])}{thin_note}. " + action, measured, 1,
                      items=items)
    if not measured:
        # The population is the dated files seen, so this honest line is not
        # flipped to a failure for having measured no cadence yet.
        return Result(NAME, "PASS", f"not enough history to know the cadence yet ({dated} "
                      f"dated file{'s' if dated != 1 else ''}; {min_dates} needed per series)",
                      dated, 1)
    return Result(NAME, "PASS", f"{measured} series with a cadence, none quiet beyond "
                  f"{factor}x their usual gap" + thin_note, measured, 1)
