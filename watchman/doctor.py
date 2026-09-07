"""`watchman doctor`: one line per section of watchman.toml saying whether that check
can run over this folder, and what is missing if not. Reads everything, writes nothing,
puts nothing on the board, exits 0. Run it after `init --discover` and after every edit.
"""
import os
import re

from .checks import REGISTER
from .checks import expected_run
from .checks._util import log_entries, now, read, table_rows
from .checks.prompt_drift import PLACEHOLDER, TOKEN, _looks_like_path
from .checks._util import _plural

READY, FIX, NOTE = "ready", "fix", "note"


def _files(cfg, patterns):
    return cfg.files(patterns if isinstance(patterns, list) else [patterns])


def _exists(cfg, rel):
    return os.path.exists(cfg.path(rel))


def _watchman(cfg, c):
    zone = f"UTC{cfg.utc_offset:+g}"
    src = "from the toml" if "utc_offset_hours" in c else "this machine's zone, not written in the toml"
    yield READY, f"times are {zone} ({src}); heartbeat goes to {cfg.rel(cfg.heartbeat)}"


def _log(cfg, c):
    files = _files(cfg, c.get("files", []))
    if not files:
        yield FIX, f"files = {c.get('files')} matches nothing under {cfg.root}"
        return
    try:
        n = len(log_entries(cfg))
    except re.error as exc:
        yield FIX, f"heading regex does not compile: {exc}"
        return
    if n == 0:
        yield FIX, f"{_plural(len(files), 'file')} matched but no line matches heading = {c.get('heading')!r}; the log is a different shape"
    else:
        yield READY, f"{n} numbered entries across {_plural(len(files), 'file')}"


def _stale(cfg, c):
    p = cfg.path(c.get("file", ""))
    if not c.get("file"):
        yield FIX, "no `file =` line"
        return
    if not os.path.exists(p):
        yield FIX, f"{c['file']} does not exist"
        return
    try:
        pat = re.compile(c.get("marker", r"folded through Entry (\d+)"))
    except re.error as exc:
        yield FIX, f"marker regex does not compile: {exc}"
        return
    with open(p, encoding="utf-8", errors="replace") as fh:
        head = "".join(fh.readline() for _ in range(int(c.get("head_lines", 5))))
    m = pat.search(head)
    if not m:
        yield FIX, f"marker {pat.pattern!r} matches nothing in the first {int(c.get('head_lines', 5))} lines of {c['file']}"
        return
    if not m.groups():
        yield FIX, f"marker {pat.pattern!r} has no capture group; put the number or date in parentheses"
        return
    if m.group(1).strip().isdigit():
        n = len(log_entries(cfg)) if cfg.section("log") else 0
        if n == 0:
            yield FIX, f"{c['file']} says Entry {m.group(1)} but no [log] entries were found to measure it against"
        else:
            yield READY, f"{c['file']} says Entry {m.group(1)}; the log has {n} entries (entry mode)"
    else:
        srcs = c.get("sources", [])
        matched = _files(cfg, srcs) if srcs else []
        if srcs and not matched:
            yield FIX, f"{c['file']} says {m.group(1)}, but sources = {srcs} matches no files"
        elif srcs:
            yield READY, f"{c['file']} says {m.group(1)}; measured against {_plural(len(matched), 'source file')} (date mode)"
        else:
            yield READY, f"{c['file']} says {m.group(1)}; measured against today, grace {_plural(int(c.get('grace_days', 1)), 'day')} (date mode)"


def _stated(cfg, c):
    files = _files(cfg, c.get("files", []))
    if not files:
        yield FIX, f"files = {c.get('files')} matches nothing"
    for spec in c.get("measure", []):
        if spec.get("file") and not _exists(cfg, spec["file"]):
            yield FIX, f"measure {spec.get('name')}: {spec['file']} does not exist"
    if files:
        yield READY, f"{_plural(len(files), 'file')} scanned for stated numbers, {_plural(len(c.get('measure', [])), 'measurable')}"


def _degraded(cfg, c):
    d = cfg.path(c.get("state_dir", ""))
    if not os.path.isdir(d):
        yield FIX, f"state_dir {c.get('state_dir')!r} is not a folder"
        return
    n = len([f for f in os.listdir(d) if f.endswith(".json")])
    yield (READY if n else FIX), f"{_plural(n, 'state file')} in {c['state_dir']}" + ("" if n else "; the jobs write none, so this check has nothing to read")


def _expected(cfg, specs):
    if isinstance(specs, dict):
        specs = [specs]
    at = now(cfg)
    for spec in specs:
        name = spec.get("name", spec.get("evidence", "?"))
        if "schedule" not in spec or "evidence" not in spec:
            yield FIX, f"{name}: needs both `schedule =` and `evidence =`"
            continue
        try:
            last = expected_run._last_fire(spec["schedule"], at)
        except ValueError as exc:
            yield FIX, f"{name}: {exc}"
            continue
        if last is None:
            yield FIX, f"{name}: schedule {spec['schedule']!r} never fires"
            continue
        ev = spec["evidence"]
        paths = _files(cfg, [ev]) if any(ch in ev for ch in "*?[") else ([cfg.path(ev)] if _exists(cfg, ev) else [])
        if not paths:
            yield FIX, f"{name}: evidence {ev!r} matches no file yet (fails on the board until the job writes it)"
            continue
        if spec.get("pattern"):
            try:
                pat = re.compile(spec["pattern"])
            except re.error as exc:
                yield FIX, f"{name}: pattern does not compile: {exc}"
                continue
            hits = sum(1 for p in paths for line in (read(p) or "").splitlines() if pat.search(line))
            if not hits:
                yield FIX, f"{name}: pattern {spec['pattern']!r} matches no line in {ev}; fix the pattern or remove it"
                continue
            yield READY, f"{name}: {spec['schedule']}, last due {last.strftime('%a %d %b %H:%M')}, {_plural(hits, 'matching line')} in {ev}"
        else:
            yield READY, f"{name}: {spec['schedule']}, last due {last.strftime('%a %d %b %H:%M')}, {_plural(len(paths), 'file')} match {ev}"


def _prompts(cfg, c):
    mirrors = _files(cfg, c.get("mirrors", ["tasks/*.md"]))
    if not mirrors:
        yield FIX, f"mirrors = {c.get('mirrors')} matches nothing"
        return
    n = 0
    for m in mirrors:
        for tok in TOKEN.finditer(read(m) or ""):
            raw = tok.group(1).strip().rstrip(".,;:)")
            if _looks_like_path(raw) and not PLACEHOLDER.search(raw):
                n += 1
    if c.get("live_dir") and not os.path.isdir(cfg.path(c["live_dir"])):
        yield FIX, f"live_dir {c['live_dir']!r} is not a folder"
    yield (READY if n else FIX), f"{_plural(len(mirrors), 'prompt')}, {_plural(n, 'path')} in backticks" + ("" if n else "; nothing to resolve")


def _ledgers(cfg, specs):
    for spec in specs:
        rel = spec.get("file", "?")
        text = read(cfg.path(rel))
        if text is None:
            yield FIX, f"{rel} does not exist"
            continue
        rows = table_rows(text, spec.get("key", "ID"))
        if not rows:
            yield FIX, f"{rel}: no table whose first header cell is {spec.get('key', 'ID')!r}"
            continue
        col = spec.get("state_column")
        if col and not all(col in header for _, header, _ in rows):
            yield FIX, f"{rel}: no column named {col!r}"
            continue
        yield READY, f"{rel}: {_plural(len(rows), 'row')}, states {spec.get('states')}"


def _table_file(label):
    def f(cfg, c):
        rel = c.get("file", "?")
        text = read(cfg.path(rel))
        if text is None:
            yield FIX, f"{rel} does not exist (that fails on the board; this check is for folders that keep a {label})"
            return
        key = c.get("key", "Date" if label == "cannot list" else "Date")
        rows = table_rows(text, key)
        yield (READY if rows else FIX), f"{rel}: {_plural(len(rows), 'row')} under key {key!r}"
    return f


def _absence(cfg, c):
    files = _files(cfg, c.get("files", []))
    dirs = c.get("dirs", [])
    bad = [d for d in dirs if not os.path.isdir(cfg.path(d))]
    if bad:
        yield FIX, f"dirs that do not exist: {bad}"
    if not files and not dirs:
        yield FIX, "neither files nor dirs matches anything"
    elif not bad:
        yield READY, f"{_plural(len(files), 'file')} and {_plural(len(dirs), 'folder')} with their own cadence"


def _citations(cfg, c):
    files = _files(cfg, c.get("files", []))
    if not files:
        yield FIX, f"files = {c.get('files')} matches nothing"
        return
    pat = re.compile(c.get("pattern", r"\bE(\d{3,})\b"))
    n = sum(len(pat.findall(read(p) or "")) for p in files)
    yield (READY if n else FIX), f"{_plural(n, 'citation')} in {_plural(len(files), 'file')}" + ("" if n else "; nothing to resolve")


def _read_budget(cfg, c):
    whole = _files(cfg, c.get("opened_whole", []))
    behind = _files(cfg, c.get("behind_a_tool", []))
    if not whole and not behind:
        yield FIX, "opened_whole and behind_a_tool match nothing"
    else:
        yield READY, f"{_plural(len(whole), 'file')} opened whole, {len(behind)} behind a tool"


PROBES = {"watchman": _watchman, "log": _log, "stale_state": _stale, "stated": _stated,
          "degraded": _degraded, "expected": _expected, "prompts": _prompts,
          "ledgers": _ledgers, "interventions": _table_file("tally"), "absence": _absence,
          "citations": _citations, "cannots": _table_file("cannot list"),
          "read_budget": _read_budget}
NAMES = {section: mod.NAME for section, mod in REGISTER}
NAMES["watchman"] = "heartbeat"


def run(cfg, prog="watchman", verbose=False, advise=True):
    """Returns (lines, ready, fix): the printable report and the two counts.
    `verbose` names the checks that are off; `advise` adds the next-step line."""
    lines, ready, fix = [], 0, 0
    order = ["watchman"] + [s for s, _ in REGISTER]
    present = [s for s in order if cfg.section(s) is not None]
    for section in present:
        probe = PROBES.get(section)
        if probe is None:
            continue
        sec = cfg.section(section)
        label = f"[{section}]" if not isinstance(sec, list) else f"[[{section}]]"
        guessed = (bool(sec.get("guessed")) if isinstance(sec, dict)
                   else any(isinstance(e, dict) and e.get("guessed") for e in sec))
        try:
            results = list(probe(cfg, sec))
        except Exception as exc:                                     # noqa: BLE001
            results = [(FIX, f"could not be read: {type(exc).__name__}: {exc}")]
        per_entry = isinstance(sec, list) and len(results) == len(sec)
        for i, (status, text) in enumerate(results):
            ready += status == READY
            fix += status == FIX
            here = bool(sec[i].get("guessed")) if per_entry else guessed
            if here and status == READY:
                text = "guessed, warns but never fails until confirmed · " + text
            lines.append(f"{status:>5}  {label:<16} {NAMES.get(section, section):<18} {text}")
    off = [f"{NAMES.get(s, s)}" for s in order if cfg.section(s) is None and s != "watchman"]
    fit = len({NAMES.get(s, s) for s in present})
    lines.append("")
    lines.append(f"{ready} ready · {fix} to fix · {fit} checks fit this folder. The others need "
                 f"conventions this folder does not use, and stay off.")
    if verbose and off:
        lines.append(f"off (no section in watchman.toml): {', '.join(off)}")
    if not advise:
        return lines, ready, fix
    if fix:
        lines.append(f"Edit {cfg.rel(cfg.path('watchman.toml'))} for each `fix` line, then run "
                     f"`{prog} doctor --root {cfg.root}` again. A check that cannot run shows red "
                     f"on the board, not green.")
    else:
        lines.append(f"Run `{prog} --root {cfg.root}` for the board; `{prog} install {cfg.root}` "
                     f"does that and schedules the nightly run.")
    return lines, ready, fix
