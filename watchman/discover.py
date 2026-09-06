"""`watchman init --discover DIR`: read the folder, guess its shape, propose a watchman.toml.

Every guess is a comment in the file it writes, and every guess that could be
wrong carries `# TODO confirm`. A section that rests on a guess also carries a
real key, `guessed = true`: its check can warn but never fail until the operator
deletes that line (`watchman confirm` does it). Nothing is asked interactively:
the operator reads the proposal once, deletes what is wrong, and runs `watchman doctor`.

What it looks for, and which section each becomes:

  a head line like "Generated 2026-09-05 06:00 ..."      [stale_state], and an [[expected]] job
  a "folded through Entry N" head line plus a numbered log  [stale_state] in entry mode, [log]
  files where lines start with a timestamp                  one [[expected]] job per job name seen
  markdown that names paths in backticks                    [prompts]
  a folder of files named by date                           [absence] dirs
  markdown tables with a Status-like column                 [[ledgers]] with state_column
"""
import calendar
import collections
import datetime
import os
import re
import statistics

from .checks.prompt_drift import PLACEHOLDER, TOKEN, _looks_like_path
from .config import local_utc_offset
from .checks._util import _plural

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".watchman", ".obsidian"}
TEXT = (".md", ".txt", ".log", ".csv", ".json", ".html")
MAX_FILES = 3000
MAX_BYTES = 2_000_000

DATE = r"\d{4}-\d{2}-\d{2}"
STAMP_LINE = re.compile(rf"^({DATE}[T ]\d{{2}}:\d{{2}}(?::\d{{2}})?)\S*\s+(.*)$")
HEAD_MARK = re.compile(
    rf"(?im)^\W*((?:generated|rebuilt|refreshed|updated|last updated|as of|as at|built|compiled|snapshot)\b[^\n\d]{{0,40}}?)"
    rf"({DATE}(?:[T ]\d{{2}}:\d{{2}})?)")
ENTRY_MARK = re.compile(r"folded through Entry\s+(\d+)")
ENTRY_HEADING = re.compile(rf"^##\s+({DATE}).*?Entry\s+(\d+)", re.M)
STATE_WORDS = ("status", "state", "stage", "disposition", "outcome")
PROMPT_DIRS = ("prompts", "prompt", "tasks", "skills", "agents", "schedules", "jobs")
SKIP_NAMES = ("readme", "changelog", "license", "watchman")
GUESSED = "guessed = true    # TODO confirm: delete this line once the section above is right"


def _walk(root):
    n = 0
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for f in sorted(files):
            if f.startswith(".") or not f.lower().endswith(TEXT):
                continue
            p = os.path.join(base, f)
            try:
                if os.path.getsize(p) > MAX_BYTES:
                    continue
            except OSError:
                continue
            n += 1
            if n > MAX_FILES:
                return
            yield p


def _read(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def _toml_str(s):
    """Single quotes when the text has backslashes (a regex), double otherwise."""
    if "\\" in s and "'" not in s:
        return "'" + s + "'"
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _list(items):
    return "[" + ", ".join(_toml_str(i) for i in items) + "]"


def _guess_schedule(stamps, name=""):
    """(schedule, confident) from the timestamps a job has left behind."""
    times = [datetime.datetime.strptime(s[:16].replace("T", " "), "%Y-%m-%d %H:%M") for s in stamps]
    times.sort()
    minutes = [t.hour * 60 + t.minute for t in times]
    med = int(statistics.median(minutes))
    hhmm = f"{med // 60:02d}:{(med % 60) // 5 * 5:02d}"
    days = sorted({t.date() for t in times})
    if len(days) < 2:
        d = days[0]
        if d.day == calendar.monthrange(d.year, d.month)[1] or "month" in name.lower():
            return f"monthly last {hhmm}", False
        return f"daily {hhmm}", False
    spread = max(abs(m - med) for m in minutes)
    if spread > 45:
        return f"daily {hhmm}", False
    gaps = [(b - a).days for a, b in zip(days, days[1:])]
    if all(d.day == calendar.monthrange(d.year, d.month)[1] for d in days):
        return f"monthly last {hhmm}", len(days) >= 2
    if min(gaps) >= 27 and len({d.day for d in days}) == 1:
        return f"monthly {days[0].day} {hhmm}", True
    if all(d.weekday() < 5 for d in days) and len(days) >= 5 and max(gaps) <= 3:
        return f"weekdays {hhmm}", True
    if statistics.median(gaps) <= 1.5:
        return f"daily {hhmm}", len(days) >= 3
    if statistics.median(gaps) in (6, 7, 8):
        return f"{calendar.day_abbr[days[-1].weekday()].lower()} {hhmm}", True
    return f"daily {hhmm}", False


def _tables_with_state(text):
    """[(key, state_column, sorted states)] for every markdown table whose header
    has a status-like column."""
    out, header, states, key, col = [], None, None, None, None
    for line in text.splitlines() + [""]:
        if not line.startswith("|"):
            if header and states:
                out.append((key, header[col], sorted(states)))
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            hits = [i for i, c in enumerate(cells) if c.lower() in STATE_WORDS]
            if hits and cells[0]:
                header, col, key, states = cells, hits[0], cells[0], set()
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        if col < len(cells) and cells[col]:
            states.add(cells[col].strip("* "))
    return out


def discover(root, today=None):
    """Returns (toml_text, guesses) where guesses is one plain line per section."""
    root = os.path.abspath(root)
    today = today or datetime.date.today()
    rel = lambda p: os.path.relpath(p, root).replace(os.sep, "/")   # noqa: E731
    rebuilt, logs, prompts, dated_dirs, dated_files, ledgers = [], [], [], {}, [], []
    entry_logs, entry_state, csv_status = [], None, []
    for p in _walk(root):
        r = rel(p)
        name = os.path.basename(p).lower()
        text = _read(p)
        head = "\n".join(text.splitlines()[:8])
        if name.endswith(".csv"):
            first = text.splitlines()[0].lower() if text else ""
            if any(w in first.split(",") for w in STATE_WORDS):
                csv_status.append(r)
            continue
        # numbered log files, the brain-ops shape
        if len(ENTRY_HEADING.findall(text)) >= 2:
            entry_logs.append(r)
            continue
        em = ENTRY_MARK.search(head)
        if em:
            entry_state = r
            continue
        # timestamped lines: a run log
        stamped = collections.defaultdict(list)
        for line in text.splitlines():
            m = STAMP_LINE.match(line)
            if m:
                words = re.findall(r"[A-Za-z][\w.-]*", m.group(2))
                job = words[0] if words else os.path.splitext(os.path.basename(p))[0]
                stamped[job].append(m.group(1))
        if sum(len(v) for v in stamped.values()) >= 3:
            logs.append((r, dict(stamped)))
            continue
        # a rebuilt file: says when it was generated in its head
        hm = HEAD_MARK.search(head)
        if hm and not name.startswith(SKIP_NAMES):
            rebuilt.append((r, hm.group(1), hm.group(2)))
            continue
        # tables with a status column
        for key, col, states in _tables_with_state(text):
            if len(states) >= 1:
                ledgers.append((r, key, col, states))
        # prompt-like markdown
        if name.endswith(".md") and not name.startswith(SKIP_NAMES):
            paths = [t.group(1).strip().rstrip(".,;:)") for t in TOKEN.finditer(text)]
            paths = [x for x in paths if _looks_like_path(x) and not PLACEHOLDER.search(x)]
            in_prompt_dir = any(part.lower() in PROMPT_DIRS for part in r.split("/")[:-1])
            if len(paths) >= 2 or (in_prompt_dir and paths):
                prompts.append(r)
                continue
        # dated notes: by file name (folder series) or by dates inside (file series)
        if re.search(DATE, name):
            dated_dirs.setdefault(os.path.dirname(r) or ".", []).append(r)
        elif len(set(re.findall(rf"\b{DATE}\b", text))) >= 3:
            dated_files.append(r)

    out, guesses = [], []
    utc = local_utc_offset()
    out += ["# watchman.toml, proposed by `watchman init --discover` from the files in this folder.",
            "# Every section switches on one check. Delete a section to turn its check off.",
            "# Lines marked `# TODO confirm` are guesses; fix them, then run `watchman doctor`.",
            "# A section with `guessed = true` can warn but never fail. Delete that line to confirm",
            "# the section (`watchman confirm --all` deletes every one).",
            "", "[watchman]",
            f"utc_offset_hours = {utc:g}    # this machine's zone when the proposal was written",
            'heartbeat = ".watchman/heartbeat.json"', "heartbeat_max_age_hours = 30",
            f'attention_file = "WATCHMAN.md"    # written every run at the root of this folder; "" turns it off', ""]

    # [log] and entry-mode stale_state, only for the numbered-log shape
    if entry_logs:
        dirs = sorted({os.path.dirname(x) or "." for x in entry_logs})
        globs = [f"{d}/*.md" if d != "." else "*.md" for d in dirs]
        out += ["[log]    # numbered entries under `## DATE ... Entry N` headings; append-only-log",
                f"files = {_list(globs)}",
                "heading = '^##\\s+(?P<date>\\d{4}-\\d{2}-\\d{2}).*?Entry\\s+(?P<n>\\d+)'",
                f'write_to = "{dirs[0] + "/" if dirs[0] != "." else ""}{{month}}.md"',
                "floor = 1", "quiet_days = 3", ""]
        guesses.append(f"[log]: numbered entries in {', '.join(entry_logs[:3])}")
        if entry_state:
            out += ["[stale_state]    # the read-first file, measured by its own marker against the log",
                    f'file = "{entry_state}"', "marker = 'folded through Entry (\\d+)'",
                    "grace_days = 1", ""]
            guesses.append(f"[stale_state]: {entry_state} says which entry it folded through")

    # rebuilt files: date-mode stale_state for the freshest, expected jobs for all
    rebuilt.sort(key=lambda t: t[2], reverse=True)
    if rebuilt and not entry_state:
        r, prefix, stamp = rebuilt[0]
        marker = re.escape(prefix.strip()) + r"\s*(\d{4}-\d{2}-\d{2})"
        out += [f"[stale_state]    # {r} says when it was last rebuilt; stale when that date falls behind",
                f'file = "{r}"',
                f"marker = {_toml_str(marker)}",
                "grace_days = 1    # TODO confirm: how many days old may it be before that is a problem",
                "sources = []    # TODO confirm: globs of the files it is rebuilt from, e.g. [\"inbox/*.eml\"]; empty means compare with today",
                GUESSED, ""]
        guesses.append(f"[stale_state]: {r} carries '{prefix.strip()} {stamp}' in its head")

    expected = []
    for r, prefix, stamp in rebuilt:
        has_time = len(stamp) > 10
        job = os.path.splitext(os.path.basename(r))[0]
        sched = f"daily {stamp[11:16]}" if has_time else "daily 06:00"
        marker = re.escape(prefix.strip()) + r"\s*(\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2})?)"
        expected.append((job, sched, r, marker, has_time,
                         f"{r} is rebuilt with a '{prefix.strip()} <date>' line"))
    for r, jobs in logs:
        for job, stamps in jobs.items():
            if any(job.lower() in e[0].lower() or e[0].lower() in job.lower() for e in expected):
                continue
            sched, sure = _guess_schedule(stamps, job)
            pat = r"^(\S+)\s+" + re.escape(job).replace("\\-", "-") + r"\b"
            expected.append((job, sched, r, pat, sure,
                             f"{_plural(len(stamps), 'line')} in {r} start with a timestamp and name '{job}'"))
    for job, sched, evidence, pat, sure, why in expected:
        out += [f"[[expected]]    # {why}",
                f'name = "{job}"',
                f'schedule = "{sched}"' + ("" if sure else "    # TODO confirm: guessed from the times seen; forms: daily HH:MM, weekdays HH:MM, mon,thu HH:MM, monthly last HH:MM"),
                f'evidence = "{evidence}"',
                f"pattern = {_toml_str(pat)}",
                "grace_minutes = 90"] + ([] if sure else [GUESSED]) + [""]
        guesses.append(f"[[expected]] {job}: {sched}, evidence {evidence}" + ("" if sure else " (schedule guessed)"))
    if not expected:
        out += ["# No [[expected]] job proposed: nothing here carries a timestamp a job leaves behind.",
                "# Declare one by hand; it needs nothing but a schedule and a file the job touches:",
                "# [[expected]]", '# name = "nightly"', '# schedule = "daily 03:00"',
                '# evidence = "summary.md"', "# grace_minutes = 90", ""]

    if prompts:
        globs = sorted({f"{os.path.dirname(x)}/*.md" if "/" in x else x for x in prompts})
        out += ["[prompts]    # scheduled prompts as markdown; every `path` they name must exist",
                f"mirrors = {_list(globs)}", "floor = 1",
                "# exempt = []    # paths that are prose, not paths the prompt uses", ""]
        guesses.append(f"[prompts]: {_plural(len(prompts), 'file')} naming paths in backticks: {', '.join(prompts[:3])}")

    series_dirs = sorted(d for d, fs in dated_dirs.items() if len(fs) >= 3)
    if series_dirs or dated_files:
        out += ["[absence]    # things with their own cadence; warns when one goes quiet"]
        if series_dirs:
            out += [f"dirs = {_list(series_dirs)}    # one series per folder, dated by file name"]
        if dated_files:
            out += [f"files = {_list(dated_files)}    # one series per file, dated by the dates inside"]
        out += ["min_dates = 5", "factor = 2.0", ""]
        guesses.append("[absence]: " + ", ".join(f"{d}/ ({len(dated_dirs[d])} dated files)" for d in series_dirs)
                       + (", " if series_dirs and dated_files else "") + ", ".join(dated_files))

    for r, key, col, states in ledgers:
        out += [f"[[ledgers]]    # a table in {r} with a '{col}' column; every row must carry one of these",
                f'file = "{r}"' + ("    # TODO confirm: a dated file; point this at the newest one when the next appears" if re.search(DATE, r) else ""),
                f'key = "{key}"', f'state_column = "{col}"',
                f"states = {_list(states)}    # TODO confirm: the values seen so far; add any that are allowed but absent",
                GUESSED, ""]
        guesses.append(f"[[ledgers]]: {r}, column '{col}' with states {states}")
    for r in csv_status:
        out += [f"# {r} has a status column, but watchman reads markdown tables, not CSV. Skipped.", ""]

    if not (rebuilt or logs or prompts or series_dirs or dated_files or ledgers or entry_logs):
        guesses.append("nothing recognisable: no dated head lines, timestamped logs, prompts, dated folders or status tables")
    return "\n".join(out), guesses
