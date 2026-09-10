"""A scheduled job that silently stops firing leaves nothing behind to inspect; declare when each job should run and what it leaves when it does, and fail when the evidence is missing after the last expected fire."""
# Descends from anthropics/claude-code issues #55378 and #47899 (scheduled tasks
# dropping fires for weeks while showing healthy) and brain-ops' liveness.json
# (assertion 41, 2026-08-15). This check needs no conventions from the agent at all:
# only a schedule and a path the job touches, which every job already has.
import calendar
import datetime
import os
import re

from ._util import item, now, _plural, Result

NAME = "expected-run"

_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")
_STAMP = re.compile(r"(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?")
FORMS = ('"daily HH:MM", "weekdays HH:MM", "mon,thu HH:MM", "monthly 1 HH:MM", '
         '"monthly last HH:MM", or five-field cron like "30 6 * * 1-5"')


def _last_fire(schedule, at):
    """The most recent moment before `at` the schedule says the job should have
    fired. Schedules: "daily HH:MM", "weekdays HH:MM", "mon,thu HH:MM",
    "monthly <day|last> HH:MM", or a five-field cron with plain numbers, lists,
    ranges and */n in the minute, hour and weekday fields (the subset a
    scheduled-task UI actually produces)."""
    parts = schedule.split()
    if len(parts) == 3 and parts[0].lower() == "monthly" and _TIME.match(parts[2]):
        hh, mm = (int(x) for x in _TIME.match(parts[2]).groups())
        which = parts[1].lower()
        if which != "last" and not which.isdigit():
            raise ValueError(f"unreadable schedule {schedule!r}: after \"monthly\" give a "
                             f"day of the month or \"last\"")
        y, mo = at.year, at.month
        for _ in range(3):
            dom = calendar.monthrange(y, mo)[1] if which == "last" else min(int(which), calendar.monthrange(y, mo)[1])
            t = datetime.datetime(y, mo, dom, hh, mm, tzinfo=at.tzinfo)
            if t <= at:
                return t
            mo -= 1
            if mo == 0:
                y, mo = y - 1, 12
        return None
    if len(parts) == 2 and _TIME.match(parts[1]):
        hh, mm = (int(x) for x in _TIME.match(parts[1]).groups())
        word = parts[0].lower()
        try:
            days = (set(range(7)) if word == "daily" else set(range(5)) if word == "weekdays"
                    else {_WEEKDAYS[w[:3]] for w in word.split(",")})
        except KeyError:
            raise ValueError(f"unreadable schedule {schedule!r}: accepted forms are {FORMS}")
        for back in range(0, 8):
            d = at.date() - datetime.timedelta(days=back)
            t = datetime.datetime.combine(d, datetime.time(hh, mm), tzinfo=at.tzinfo)
            if d.weekday() in days and t <= at:
                return t
        return None
    if len(parts) == 5:
        mins, hours, dom, _mon, dows = parts
        for back in range(0, 32 * 24 * 60):
            t = (at - datetime.timedelta(minutes=back)).replace(second=0, microsecond=0)
            if (_cron_match(mins, t.minute, 0, 59) and _cron_match(hours, t.hour, 0, 23)
                    and _cron_match(dom, t.day, 1, 31)
                    and _cron_match(dows, (t.weekday() + 1) % 7, 0, 6)):
                return t
        return None
    raise ValueError(f"unreadable schedule {schedule!r}: accepted forms are {FORMS}")


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


class NoMatch(Exception):
    """The evidence file is there but the pattern matches none of it."""


def _evidence_time(cfg, spec, since):
    """Newest evidence for the job at or after `since`: a file matching `evidence`
    modified since then, or a line in `evidence` matching `pattern` that carries a
    date on or after `since`. Returns (found, description, newest), or raises
    NoMatch when the evidence exists but the pattern matches no line of it at
    all: that is the pattern's fault, not the job's."""
    pattern = spec.get("pattern")
    paths = cfg.files([spec["evidence"]]) if any(ch in spec["evidence"] for ch in "*?[") \
        else [cfg.path(spec["evidence"])]
    newest, existing = None, 0
    for p in paths:
        if not os.path.exists(p):
            continue
        existing += 1
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
        if pattern and existing:
            raise NoMatch(f"pattern matches no line in {spec['evidence']}; fix the pattern or remove it")
        return False, f"{spec['evidence']} does not exist (no evidence at all)", None
    return newest >= since, f"newest evidence {newest.strftime('%Y-%m-%d %H:%M')}", newest


def _parse_stamp(s, tz):
    """A date, with or without a time, anywhere at the start of the captured text."""
    m = _STAMP.match((s or "").strip())
    if not m:
        return None
    try:
        d = datetime.date.fromisoformat(m.group(1))
        t = datetime.time(int(m.group(2) or 0), int(m.group(3) or 0), int(m.group(4) or 0))
    except ValueError:
        return None
    return datetime.datetime.combine(d, t, tzinfo=tz)


def _silent_fact(name, due, ev, why):
    """The fact, without a cause: from the folder, a job that never fired, a
    machine that was asleep and a job that ran but wrote nothing look the same."""
    return (f"{name} left no expected evidence for its {due} run ({why}): it may not have "
            f"run, this machine may have been off or asleep, or it may have run without "
            f"updating {ev}")


def _re_run(silent):
    """The action for silent jobs: look at the job, rerun it if that is safe, and if
    it did run, look at why the evidence did not move."""
    if len(silent) == 1:
        name, _due, ev, _why = silent[0]
        return (f"Check the {name} job. If it is safe to rerun, run it now; if it already "
                f"ran, check why {ev} was not updated.")
    names = " and ".join(n for n, _, _, _ in silent)
    files = " and ".join(sorted({ev for _, _, ev, _ in silent}))
    return (f"Check the {names} jobs. If they are safe to rerun, run them now; if they "
            f"already ran, check why {files} were not updated.")


def run(cfg):
    specs = cfg.section("expected") or []
    if isinstance(specs, dict):
        specs = [specs]
    at = now(cfg)
    silent, unconfirmed, broken, waiting, ok, items, ran = [], [], [], [], 0, [], {}
    for spec in specs:
        name = spec.get("name", spec.get("evidence", "?"))
        for key in ("schedule", "evidence"):
            if key not in spec:
                broken.append((name, f"{name}: no `{key} =` line in its [[expected]] block"))
                break
        else:
            try:
                last = _last_fire(spec["schedule"], at)
            except ValueError as exc:
                broken.append((name, f"{name}: {exc}"))
                continue
            if last is None:
                broken.append((name, f"{name}: schedule {spec['schedule']!r} never fires"))
                continue
            grace = datetime.timedelta(minutes=int(spec.get("grace_minutes", 90)))
            in_grace = at < last + grace
            if in_grace:
                # The newest due run is still inside its grace window and cannot be
                # judged yet, so judge the one before it. Without this step back, a job
                # whose due time falls within grace_minutes of watchman's own nightly
                # run is inside grace at every run, and one dead for weeks reads healthy
                # forever. `_last_fire` returns the fire at or before its argument, so
                # step back a minute to get the previous one rather than this one.
                prev = _last_fire(spec["schedule"], last - datetime.timedelta(minutes=1))
                if prev is None:
                    waiting.append(name)
                    continue
                last = prev
            try:
                found, why, newest = _evidence_time(cfg, spec, last)
            except NoMatch as exc:
                if in_grace:
                    # the pattern's fault, not the job's, and the run that would report
                    # it has not come due yet
                    waiting.append(name)
                    continue
                broken.append((name, f"{name}: {exc}"))
                continue
            if found:
                ok += 1
                ran[name] = (newest, spec["evidence"])
                continue
            if in_grace and newest is None:
                # it has never left evidence at all, so the run before last is
                # unevidenced through no fault of its own: a job added today has an
                # empty yesterday, and a red line on the first night is the one thing
                # this must never produce
                waiting.append(name)
                continue
            due = last.strftime("%a %d %b %H:%M")
            fact = _silent_fact(name, due, spec["evidence"], why)
            row = (name, due, spec["evidence"], why)
            (unconfirmed if spec.get("guessed") else silent).append(row)
            action = _re_run([row])
            if spec.get("guessed"):
                action = (f"Confirm the schedule for {name} in watchman.toml (`watchman "
                          f"confirm`), then " + action[0].lower() + action[1:])
            # keyed on the job, linked to its evidence: two jobs sharing one log are
            # two incidents, and a stale file folds in only when it is this
            # job's evidence or carries this job's name
            items.append(item(fact, action, jobs=[name], links=["file:" + spec["evidence"]]))
    n = len(specs)
    zone = f"UTC{cfg.utc_offset:+.0f}" if cfg.utc_offset else "UTC"
    tail = (f" · {_plural(n, 'job')} declared, {ok} evidenced, {len(waiting)} inside grace"
            f" · times are {zone}")
    if silent or broken or unconfirmed:
        msg, actions = [], []
        if silent:
            msg.append(f"{_plural(len(silent), 'job')} fired with no evidence: "
                       + "; ".join(_silent_fact(nm, d, ev, why) for nm, d, ev, why in silent[:3])
                       + ". A scheduler that says healthy is not sufficient evidence; the "
                       "file the job touches is")
            actions.append(_re_run(silent))
        if unconfirmed:
            msg.append(f"unconfirmed: {_plural(len(unconfirmed), 'guessed job')} with no evidence: "
                       + "; ".join(f"{nm} due {d} ({why})" for nm, d, _ev, why in unconfirmed[:3]))
            actions.append(f"Confirm the guessed {'schedule' if len(unconfirmed) == 1 else 'schedules'} in watchman.toml (`watchman "
                           f"confirm`), then check "
                           + " and ".join(nm for nm, _, _, _ in unconfirmed) + ".")
        if broken:
            msg.append(f"{_plural(len(broken), 'job')} could not be checked: "
                       + "; ".join(b for _, b in broken[:3]))
            actions.append("Fix the [[expected]] block for "
                           + " and ".join(nm for nm, _ in broken) + " in watchman.toml; "
                           "`watchman doctor` names the line.")
            for nm, b in broken:
                items.append(item(b, actions[-1], jobs=[nm]))
        status = "FAIL" if (silent or broken) else "WARN"
        r = Result(NAME, status, " · ".join(msg) + tail + ". " + " ".join(actions), n, 1,
                   items=items)
    else:
        # do not claim evidence nothing produced: with every job still inside its first
        # grace window there is nothing yet to have left any
        headline = ("every declared job left evidence after its last expected fire" if ok
                    else "no declared job has reached a due run outside its grace window yet")
        r = Result(NAME, "PASS", headline + tail, n, 1)
    # what the evidenced jobs left and when, so the runner can say "ran at <time>
    # but <file> still says <date>" when a summary lags its own job
    r.ran = ran
    return r
