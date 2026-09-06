"""The command line.

    watchman [report] [--root DIR] [--json] [--quiet] [--no-write]
    watchman init [DIR]
    watchman intervene "what" [--cost ...] [--fix ...]
    watchman log "title" [--body ...]
    watchman heartbeat            # for a second runner: fails if the mark is stale or missing

Nothing runs on import, and `--help` reads nothing. brain-ops' check.py once ran
the whole board, writes included, on `--help`.
"""
import argparse
import datetime
import sys

from . import __version__, report
from .checks import append_only_log, heartbeat, intervention_tally
from .config import Config
from .init import write_fixture


def main(argv=None):
    ap = argparse.ArgumentParser(prog="watchman",
                                 description="a reliability layer for agents that run on a folder")
    ap.add_argument("--version", action="version", version=__version__)
    ap.add_argument("--root", default=".", help="folder holding watchman.toml")
    ap.add_argument("--config", default=None, help="config file to use instead of ROOT/watchman.toml; paths inside it are still relative to ROOT")
    ap.add_argument("--json", action="store_true", help="machine output")
    ap.add_argument("--findings", metavar="FILE", default=None,
                    help="also write the board as a findings report (markdown) to FILE")
    ap.add_argument("--quiet", action="store_true", help="only warnings and failures")
    ap.add_argument("--no-write", action="store_true", help="do not touch the heartbeat")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("report", help="run every configured check and print the board")
    hb = sub.add_parser("heartbeat", help="read the last run's mark; exit 1 if stale")
    hb.add_argument("--max-age-hours", type=float, default=None)
    ini = sub.add_parser("init", help="write a starter watchman.toml and fixture files")
    ini.add_argument("dir", nargs="?", default="demo")
    ini.add_argument("--utc-offset-hours", type=float, default=0)
    iv = sub.add_parser("intervene", help="record that the human did the agent's job")
    iv.add_argument("what")
    iv.add_argument("--cost", default="")
    iv.add_argument("--fix", default="none")
    lg = sub.add_parser("log", help="append a numbered entry under a lock")
    lg.add_argument("title")
    lg.add_argument("--body", default="")
    a = ap.parse_args(argv)
    cmd = a.cmd or "report"

    if cmd == "init":
        t = (datetime.datetime.now(datetime.timezone.utc)
             + datetime.timedelta(hours=a.utc_offset_hours)).date()
        wrote = write_fixture(a.dir, t, a.utc_offset_hours)
        print(f"wrote {len(wrote)} files into {a.dir}/ · run: watchman --root {a.dir}")
        return 0

    cfg = Config.load(a.root, a.config)
    if cmd == "intervene":
        d, n = intervention_tally.add(cfg, a.what, a.cost, a.fix)
        print(f"recorded {d} · {n} row(s) in {cfg.section('interventions')['file']}")
        return 0
    if cmd == "log":
        n, target = append_only_log.append(cfg, a.title, a.body)
        print(f"Entry {n} appended to {cfg.rel(target)}")
        return 0
    if cmd == "heartbeat":
        if a.max_age_hours is not None:
            cfg.data.setdefault("watchman", {})["heartbeat_max_age_hours"] = a.max_age_hours
        r = heartbeat.run(cfg, first_run_ok=False)
        print(report.render_json([r]) if a.json else f"[{report.MARK[r.status]}] {r.check:<22} {r.message}")
        return 1 if r.status == "FAIL" else 0
    results = report.run_all(cfg, write=not a.no_write)
    print(report.render_json(results) if a.json else report.render(results, a.quiet))
    if a.findings:
        with open(a.findings, "w", encoding="utf-8") as fh:
            fh.write(report.render_findings(results, cfg))
    return report.exit_code(results)
