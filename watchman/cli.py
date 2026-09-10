"""The command line.

    watchman install FOLDER [--at HH:MM] [--no-schedule]     # discover, doctor, board, WATCHMAN.md, nightly run
    watchman [report] [--root DIR ...] [--json] [--quiet] [--no-write] [--findings PATTERN]
    watchman init [--discover | --demo] [DIR]
    watchman doctor [--root DIR] [--verbose]
    watchman confirm [--root DIR] [--all]
    watchman install-cron [--root DIR] [--at HH:MM] [--write]
    watchman intervene "what" [--cost ...] [--fix ...]
    watchman log "title" [--body ...]
    watchman heartbeat            # for a second runner: fails if the mark is stale or missing

Nothing runs on import, and `--help` reads nothing. brain-ops' check.py once ran
the whole board, writes included, on `--help`.
"""
import argparse
import datetime
import os
import sys

from . import __version__, report
from .checks import append_only_log, heartbeat, intervention_tally
from .config import FILENAME, Config
from .init import write_fixture
from .checks._util import _plural, read as read_text

NOT_SCHEDULED = ("WATCHMAN IS NOT SCHEDULED. Paste the line above into crontab (crontab -e) "
                 "before you close this terminal. Everything else is in place.")

# heartbeat is watchman's own liveness and no-vacuous-pass is a guard over the other
# checks. Neither reads a file the operator cares about, so if they are the only two
# that ran, nothing in this folder is being watched at all.
SELF_CHECKS = ("heartbeat", "no-vacuous-pass")

NOTHING_TO_WATCH = (
    "NOTHING HERE IS BEING WATCHED. Every check that reads your files stayed off, because "
    "nothing in this folder carries a timestamp, a dated line or a rebuilt file that a "
    "scheduled job leaves behind. Watchman would run every night, find nothing to look at, "
    "and say `Healthy: nothing needs you.` every morning for as long as you left it running. "
    "A green light over nothing is the exact failure this tool exists to catch, so it will "
    "not schedule itself here.")


def _findings_path(pattern, root):
    """`{name}` is the folder's own name, `{date}` today, `{root}` the absolute path."""
    root = os.path.abspath(root)
    return pattern.format(name=os.path.basename(root) or "root", date=datetime.date.today().isoformat(),
                          root=root)


GLOBAL_WITH_VALUE = ("--root", "--config", "--findings")
GLOBAL_FLAGS = ("--json", "--quiet", "--no-write")


def _hoist(argv):
    """`watchman doctor --root DIR` reads as naturally as `watchman --root DIR doctor`;
    argparse only accepts the second, so the global options are moved to the front."""
    front, rest, i = [], [], 0
    while i < len(argv):
        tok = argv[i]
        if tok in GLOBAL_WITH_VALUE and i + 1 < len(argv):
            front += [tok, argv[i + 1]]
            i += 2
            continue
        if tok in GLOBAL_FLAGS or any(tok.startswith(g + "=") for g in GLOBAL_WITH_VALUE):
            front.append(tok)
        else:
            rest.append(tok)
        i += 1
    return front + rest


def _prog():
    """How the user is invoking this: the pip script or `python3 -m watchman`."""
    return "watchman" if os.path.basename(sys.argv[0] or "") == "watchman" else "python3 -m watchman"


def _init(a):
    codes = [_init_one(a, d) for d in (a.dir or ["."])]
    return max(codes)


def _init_one(a, d):
    prog = _prog()
    has_files = os.path.isdir(d) and any(f != FILENAME for f in os.listdir(d))
    mode = "discover" if a.discover else "demo" if a.demo else ("discover" if has_files else "demo")
    if mode == "demo":
        if has_files:
            print(f"{d} already has files in it. `{prog} init --demo` writes a demo folder of its own "
                  f"files and will not do that on top of yours.\n"
                  f"  {prog} init --discover {d}    proposes a watchman.toml from what is there\n"
                  f"  {prog} init --demo {d}        writes the demo files anyway")
            return 2
        t = (datetime.datetime.now(datetime.timezone.utc)
             + datetime.timedelta(hours=a.utc_offset_hours)).date()
        wrote = write_fixture(d, t, a.utc_offset_hours)
        print(f"wrote {len(wrote)} demo files into {d}/ · run: {prog} --root {d}")
        return 0
    from .discover import discover
    if not os.path.isdir(d):
        print(f"{d} is not a folder. `{prog} init --discover DIR` reads DIR and proposes a "
              f"config; give it the folder your agent works over.")
        return 2
    text, guesses = discover(d)
    dest = os.path.join(d, FILENAME)
    if os.path.exists(dest) and not a.force:
        dest = os.path.join(d, "watchman.proposed.toml")
        note = (f"{FILENAME} already exists, so the proposal went to watchman.proposed.toml. "
                f"Compare, then rename it, or rerun with --force to overwrite.")
    else:
        note = None
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"looked at {os.path.abspath(d)} and guessed:")
    for g in guesses:
        print(f"  {g}")
    print(f"wrote {dest} · sections marked `guessed = true` warn but never fail until you "
          f"confirm them (`{prog} confirm --root {d}`)")
    if note:
        print(note)
    if not getattr(a, "inside_install", False):
        print(f"next: {prog} doctor --root {d}    (says what each section can and cannot check)")
    return 0


def _install(a, roots):
    """discover (unless a toml exists), doctor, the board, WATCHMAN.md, the schedule."""
    from .confirm import guessed_sections
    from .doctor import run as doctor
    from .install import cron_line, schedule
    prog = _prog()
    folder = a.folder or (roots[0] if a.root else None)
    if folder is None:
        print(f"which folder? {prog} install FOLDER, where FOLDER is the one your agent works over")
        return 2
    if not os.path.isdir(folder):
        print(f"{folder} is not a folder. `{prog} install FOLDER` reads FOLDER and sets the "
              f"watch up; give it the folder your agent works over.")
        return 2
    folder = os.path.abspath(folder)
    toml = a.config or os.path.join(folder, FILENAME)
    if os.path.exists(toml):
        print(f"using the {os.path.basename(toml)} already in {folder}")
    else:
        a.discover, a.demo, a.force, a.inside_install = True, False, False, True
        code = _init_one(a, folder)
        if code:
            return code
    print()
    cfg = Config.load(folder, a.config)
    lines, _ready, fix = doctor(cfg, prog, verbose=False, advise=False)
    print("\n".join(lines))
    if fix:
        print(f"({_plural(fix, 'section')} {'needs' if fix == 1 else 'need'} a fix; the board runs "
              f"anyway and shows {'it' if fix == 1 else 'them'} red)")
    print()
    results = report.run_all(cfg, write=True)
    print(report.render(results))
    print()
    dest = report.attention_path(cfg)
    if not [r for r in results if r.check not in SELF_CHECKS]:
        # Do not hand back a morning habit and a nightly schedule over a folder with
        # nothing in it to check. Say so, and stop, whatever --no-schedule says.
        print(NOTHING_TO_WATCH)
        print()
        print(f"If your scheduled jobs write somewhere else, point it there instead: "
              f"`{prog} install THAT-FOLDER`.")
        print(f"If you have no job that runs on a schedule and leaves a file behind, this "
              f"tool has nothing to offer you, and index.html says so on its first screen.")
        if dest:
            print(f"{cfg.rel(dest)} was written and says healthy. It is not evidence of "
                  f"anything; delete it.")
        return 4
    if dest:
        print(f"wrote {cfg.rel(dest)} in {folder}, which lists only what needs you. Whatever maintains "
              f"this folder can read the same thing from `{prog} --root {folder} --json`, which exits 1 "
              f"when something is wrong.")
    guessed = len(guessed_sections(read_text(toml)))
    if guessed:
        print(f"{_plural(guessed, 'rule')} {'was' if guessed == 1 else 'were'} guessed and will only warn until you confirm {'it' if guessed == 1 else 'them'}: "
              f"{prog} confirm --root {folder}")
    if a.no_schedule:
        print(f"Not scheduled (--no-schedule). Everything else is in place; the nightly line is "
              f"`{prog} install-cron --root {folder}`.")
        return 0
    else:
        lines, how = schedule([folder], a.at, a.python, a.config)
        print("\n".join(lines))
        if how == "printed":
            # Nothing was read back from the scheduler, so the run is not in place.
            # The line to paste is the last thing but one on the screen, on purpose.
            print()
            print(f"  {cron_line([folder], a.at, a.python, a.config)[0]}")
            print(NOT_SCHEDULED)
            return 3
    print(f"Done. Watchman checks {folder} every night at {a.at} and writes "
          f"{os.path.basename(dest) if dest else 'the board'} when something needs you.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="watchman",
                                 description="a reliability layer for agents that run on a folder")
    ap.add_argument("--version", action="version", version=__version__)
    ap.add_argument("--root", action="append", default=None, metavar="DIR",
                    help="folder holding watchman.toml; repeat for several folders")
    ap.add_argument("--config", default=None, help="config file to use instead of ROOT/watchman.toml; paths inside it are still relative to ROOT")
    ap.add_argument("--json", action="store_true", help="machine output")
    ap.add_argument("--findings", metavar="PATTERN", default=None,
                    help="also write the board as a findings report (markdown); {name}, {date} and {root} expand, e.g. reports/{name}-{date}.md")
    ap.add_argument("--quiet", action="store_true", help="only warnings and failures")
    ap.add_argument("--no-write", action="store_true", help="do not touch the heartbeat")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("report", help="run every configured check and print the board")
    dr = sub.add_parser("doctor", help="say what each section of watchman.toml can check here, and what is missing")
    dr.add_argument("--verbose", action="store_true", help="also name the checks that are off")
    cf = sub.add_parser("confirm", help="list the guessed sections of watchman.toml; --all confirms every one")
    cf.add_argument("--all", action="store_true", help="remove every `guessed = true` line in place")
    ins = sub.add_parser("install", help="one command: discover, doctor, the board, WATCHMAN.md, and the nightly run")
    ins.add_argument("folder", nargs="?", default=None, help="the folder your agent works over")
    ins.add_argument("--at", default="01:31", help="HH:MM, local time (default 01:31)")
    ins.add_argument("--no-schedule", action="store_true", help="do everything except schedule the nightly run")
    ins.add_argument("--python", default=None, help="interpreter for the nightly run (default: this one)")
    hb = sub.add_parser("heartbeat", help="read the last run's mark; exit 1 if stale")
    hb.add_argument("--max-age-hours", type=float, default=None)
    ini = sub.add_parser("init", help="propose a watchman.toml from the folder's files (--discover), or write a demo folder (--demo)")
    ini.add_argument("dir", nargs="*", help="folders; default the current one")
    ini.add_argument("--discover", action="store_true", help="read DIR and propose a config; asks nothing")
    ini.add_argument("--demo", action="store_true", help="write the demo fixture into DIR (an empty or new folder)")
    ini.add_argument("--force", action="store_true", help="overwrite an existing watchman.toml")
    ini.add_argument("--utc-offset-hours", type=float, default=0)
    ic = sub.add_parser("install-cron", help="print the line that runs the board nightly; on a Mac, --write saves a launchd plist")
    ic.add_argument("--at", default="01:31", help="HH:MM, local time (default 01:31)")
    ic.add_argument("--write", action="store_true", help="write the launchd plist to ~/Library/LaunchAgents (macOS)")
    ic.add_argument("--python", default=None, help="interpreter to run with (default: this one)")
    iv = sub.add_parser("intervene", help="record that the human did the agent's job")
    iv.add_argument("what")
    iv.add_argument("--cost", default="")
    iv.add_argument("--fix", default="none")
    lg = sub.add_parser("log", help="append a numbered entry under a lock")
    lg.add_argument("title")
    lg.add_argument("--body", default="")
    a = ap.parse_args(_hoist(argv if argv is not None else sys.argv[1:]))
    cmd = a.cmd or "report"
    roots = a.root or ["."]

    if cmd == "init":
        return _init(a)
    if cmd == "install":
        return _install(a, roots)
    if cmd == "confirm":
        from .confirm import run as confirm
        if len(roots) > 1:
            print("`watchman confirm` takes one --root")
            return 2
        cfg = Config.load(roots[0], a.config)
        print("\n".join(confirm(a.config or os.path.join(cfg.root, FILENAME), a.all, _prog())))
        return 0
    if cmd == "install-cron":
        from .install import plan
        lines, _written = plan(roots, a.at, a.write, a.python, a.config, findings=a.findings)
        print("\n".join(lines))
        return 0
    if cmd == "doctor":
        from .doctor import run as doctor
        for root in roots:
            cfg = Config.load(root, a.config)
            if len(roots) > 1:
                print(f"== {cfg.root}")
            lines, _ready, _fix = doctor(cfg, _prog(), verbose=a.verbose)
            print("\n".join(lines[:-1] if len(roots) > 1 else lines))
        return 0

    if cmd in ("intervene", "log", "heartbeat"):
        if len(roots) > 1:
            print(f"`watchman {cmd}` takes one --root")
            return 2
        cfg = Config.load(roots[0], a.config)
        if cmd == "intervene":
            d, n = intervention_tally.add(cfg, a.what, a.cost, a.fix)
            print(f"recorded {d} · {_plural(n, 'row')} in {cfg.section('interventions')['file']}")
            return 0
        if cmd == "log":
            n, target = append_only_log.append(cfg, a.title, a.body)
            print(f"Entry {n} appended to {cfg.rel(target)}")
            return 0
        if a.max_age_hours is not None:
            cfg.data.setdefault("watchman", {})["heartbeat_max_age_hours"] = a.max_age_hours
        r = heartbeat.run(cfg, first_run_ok=False)
        print(report.render_json([r]) if a.json else f"[{report.MARK[r.status]}] {r.check:<22} {r.message}")
        return 1 if r.status == "FAIL" else 0

    worst = 0
    for root in roots:
        cfg = Config.load(root, a.config)
        results = report.run_all(cfg, write=not a.no_write)
        if len(roots) > 1 and not a.json:
            print(f"== {cfg.root}")
        print(report.render_json(results) if a.json else report.render(results, a.quiet))
        if a.findings:
            dest = _findings_path(a.findings, cfg.root)
            os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(report.render_findings(results, cfg))
            if not a.json:
                print(f"findings written to {dest}")
        worst = max(worst, report.exit_code(results))
        if len(roots) > 1 and not a.json:
            print()
    return worst
