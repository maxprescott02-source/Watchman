"""A subject that has gone quiet relative to its own cadence is a finding; runs of silence are data, and nothing else on the board can see them."""
# Descends from brain-ops spec.md layer 1 ("runs of silence are data") and skill
# rule 4, "absence is data": going quiet for five nights says more than the sixth answer.
import statistics

from ._util import DATE, Result, parse_date, read, today

NAME = "absence"


def run(cfg):
    c = cfg.section("absence")
    min_dates = int(c.get("min_dates", 3))
    factor = float(c.get("factor", 2.0))
    min_days = int(c.get("min_days", 3))
    t = today(cfg)
    measured, quiet = 0, []
    for p in cfg.files(c.get("files", [])):
        dates = sorted({d for d in (parse_date(s) for s in DATE.findall(read(p) or ""))
                        if d and d <= t})
        if len(dates) < min_dates:
            continue
        measured += 1
        gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
        usual = max(statistics.median(gaps), 1)
        since = (t - dates[-1]).days
        if since > max(usual * factor, min_days):
            quiet.append(f"{cfg.rel(p)} (last dated {dates[-1]}, {since}d ago, usual gap {usual:.0f}d)")
    if quiet:
        return Result(NAME, "WARN", f"{len(quiet)} of {measured} gone quiet against their own "
                      f"cadence: {'; '.join(quiet[:4])}", measured, 1)
    return Result(NAME, "PASS", f"{measured} file(s) with a cadence, none quiet beyond "
                  f"{factor}x their usual gap", measured, 1)
