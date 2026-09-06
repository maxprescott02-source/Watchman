"""A scheduled job that silently stops firing leaves nothing behind to inspect; declare when each job should run and what it leaves when it does, and fail when the evidence is missing after the last expected fire."""
# Descends from anthropics/claude-code issues #55378 and #47899 (scheduled tasks
# dropping fires for weeks while showing healthy) and brain-ops' liveness.json
# (assertion 41, 2026-08-15). This check needs no conventions from the agent at all:
# only a schedule and a path the job touches, which every job already has.
import datetime
import glob
import os
import re

from ._util import Result, now

NAME = "expected-run"

_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")


def _last_fire(schedule, at):
    """The most recent moment before `at` the schedule says the job should have
    fired. Schedules: "daily HH:MM", "weekdays HH:MM", "mon,thu HH:MM", or a
    five-field cron with plain numbers, lists and */n in the minute and hour
    fields (the subset a scheduled-task UI actually produces)."""
    parts = schedule.split()
    if len(parts) == 2 and _TIME.match(parts[1]):
        hh, mm = (int(x) for x in _TIME.match(parts[1]).groups())
        word = parts[0].lower()
        days = (set(range(7)) if word == "daily" else set(range(5)) if word == "weekdays"
                else {_WEEKDAYS[w[:3]] for w in word.split(",")})
        for back in range(0, 8):
            d = at.date() - datetime.timedelta(days=back)
            t = datetime.datetime.combine(d, datetime.time(hh, mm), tzinfo=at.tzinfo)
            if d.weekday() in days and t <= at:
                return t
        return None
    if len(parts) == 5:
        mins, hours, _dom, _mon, dows = parts
        for back in range(0, 8 * 24 * 60):
            t = (at - datetime.timedelta(minutes=back)).replace(second=0, microsecond=0)
            if (_cron_match(mins, t.minute, 0, 59) and _cron_match(hours, t.hour, 0, 23)
                    and _cron_match(dows, (t.weekday() + 1) % 7, 0, 6)):
                return t
        return None
    raise ValueError(f"unreadable schedule {schedule!r}")


def _cron_match(field, value, lo, hi):
    if field == "*":
        return True
    for piece in field.split(","):
        if piece.startswith("*/"):
            if value % int(piece[2:]) == 0:
                return True
        elif "-" in piece:
            a, b = (int(x) for x in piece.split("-"))
            if a <= value <= b:
                return True
        elif piece.isdigit() and int(piece) == value:
            return True
    return False


def _evidence_time(cfg, spec, since):
    """Newest evidence for the job at or after `since`: a file matching `evidence`
    modified since then, or a line in `evidence` matching `pattern` that carries a
    date on or after `since`. Returns (found, description)."""
    pattern = spec.get("pattern")
    paths = cfg.files([spec["evidence"]]) if any(ch in spec["evidence"] for ch in "*?[") \
        else [cfg.path(spec["evidence"])]
    newest = None
    for p in paths:
        if not os.path.exists(p):
            continue
        if pattern:
            pat = re.compile(pattern)
            with open(p, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    m = pat.search(line)
                    if not m:
                        continue
                    stamp = m.group(1) if m.groups() else None
                    when = _parse_stamp(stamp, since.tzinfo) if stamp else None
                    if when is None:
                        when = datetime.datetime.fromtimestamp(os.path.getmtime(p), since.tzinfo)
                    if newest is None or when > newest:
                        newest = when
        else:
            when = datetime.datetime.fromtimestamp(os.path.getmtime(p), since.tzinfo)
            if newest is None or when > newest:
                newest = when
    if newest is None:
        return False, "no evidence at all"
    return newest >= since, f"newest evidence {newest.strftime('%Y-%m-%d %H:%M')}"


def _parse_stamp(s, tz):
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s[:len(fmt) + 2], fmt).replace(tzinfo=tz)
        except ValueError:
            continue
    try:
        return datetime.datetime.fromisoformat(s).astimezone(tz)
    except (ValueError, TypeError):
        return None


def run(cfg):
    specs = cfg.section("expected") or []
    if isinstance(specs, dict):
        specs = [specs]
    at = now(cfg)
    silent, waiting, ok = [], [], 0
    for spec in specs:
        name = spec.get("name", spec.get("evidence", "?"))
        try:
            last = _last_fire(spec["schedule"], at)
        except (ValueError, KeyError) as exc:
            silent.append(f"{name}: {exc}")
            continue
        if last is None:
            silent.append(f"{name}: schedule {spec['schedule']!r} never fires")
            continue
        grace = datetime.timedelta(minutes=int(spec.get("grace_minutes", 90)))
        if at < last + grace:
            waiting.append(name)
            continue
        found, why = _evidence_time(cfg, spec, last)
        if found:
            ok += 1
        else:
            silent.append(f"{name}: due {last.strftime('%a %H:%M')}, {why}")
    n = len(specs)
    tail = f" · {n} job(s) declared, {ok} evidenced, {len(waiting)} inside grace"
    if silent:
        return Result(NAME, "FAIL", f"{len(silent)} job(s) fired with no evidence: "
                      f"{'; '.join(silent[:3])}. A schedule that says healthy is not "
                      f"evidence; the file the job touches is" + tail, n, 1)
    return Result(NAME, "PASS", "every declared job left evidence after its last expected "
                  "fire" + tail, n, 1)
