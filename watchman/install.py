"""`watchman install-cron`: make the board run nightly without the operator learning cron.

Prints the crontab line for the folder. On macOS it also prints (or with --write,
writes) a launchd plist under ~/Library/LaunchAgents, because cron on a Mac does
not run while the machine sleeps and launchd catches up when it wakes. Nothing is
loaded or scheduled by `install-cron` itself; the last line says what to run.

`schedule()` is the half that does act: `watchman install` calls it to load the
plist or append the crontab line. With WATCHMAN_DRY_SCHEDULE=1 in the environment
it prints what it would do instead, which is how the tests stay off the crontab.
"""
import os
import re
import shutil
import subprocess
import sys

from . import __version__

PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/sh</string>
    <string>-c</string>
    <string>{command}</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>{hour}</integer><key>Minute</key><integer>{minute}</integer></dict>
  <key>StandardOutPath</key><string>{log}</string>
  <key>StandardErrorPath</key><string>{log}</string>
</dict>
</plist>
"""


def _slug(root):
    s = re.sub(r"[^A-Za-z0-9]+", "-", os.path.basename(os.path.abspath(root))).strip("-").lower()
    return s or "folder"


DEFAULT_FINDINGS = "{root}/.watchman/findings-{date}.md"


def _q(s):
    return "'" + s.replace("'", "'\\''") + "'"


def command_for(roots, python=None, findings=None, config=None):
    """(command, log path) a scheduler runs. `cd` into the package's parent so
    `python -m watchman` works whether or not it was pip-installed. With one
    root the findings and the board land in its `.watchman/`; with several, or
    an explicit --findings, the reports go where the pattern says and the board
    text beside them."""
    roots = [os.path.abspath(r) for r in roots]
    python = python or sys.executable
    pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    findings = findings or DEFAULT_FINDINGS
    report_dir = os.path.dirname(findings.format(root=roots[0], name="x", date="x")) or "."
    if findings == DEFAULT_FINDINGS or "{root}" in report_dir:
        log = os.path.join(roots[0], ".watchman", "last-board.txt")
        dirs = [os.path.join(r, ".watchman") for r in roots]
    else:
        log = os.path.join(os.path.abspath(report_dir), "last-board.txt")
        dirs = [os.path.abspath(report_dir)]
    parts = ["mkdir -p " + " ".join(_q(d) for d in dirs), "&&", f"cd {_q(pkg_parent)}", "&&",
             _q(python), "-m", "watchman"]
    for r in roots:
        parts += ["--root", _q(r)]
    if config:
        parts += ["--config", _q(os.path.abspath(config))]
    parts += ["--findings", _q(findings)]
    return " ".join(parts), log


def plan(roots, at="01:31", write=False, python=None, config=None, platform=None, findings=None):
    """Returns (lines to print, path written or None)."""
    if isinstance(roots, str):
        roots = [roots]
    m = re.match(r"^(\d{1,2}):(\d{2})$", at)
    if not m:
        raise SystemExit(f"--at wants HH:MM, got {at!r}")
    hour, minute = int(m.group(1)), int(m.group(2))
    roots = [os.path.abspath(r) for r in roots]
    root = roots[0]
    cmd, log = command_for(roots, python, findings, config)
    cron = f"{minute} {hour} * * * {cmd} > {_q(log)} 2>&1"
    platform = platform or sys.platform
    over = root if len(roots) == 1 else f"{len(roots)} folders"
    lines = [f"# watchman {__version__} nightly over {over} at {hour:02d}:{minute:02d}", "",
             "The crontab line (any Linux or Mac with cron):", "", f"  {cron}", "",
             "To install it: run `crontab -e`, paste the line, save. If that opens vi, press i, paste, "
             "then Esc, then :wq and Enter. `crontab -l` shows what is installed.",
             f"Each run leaves the board text in {log} and a findings report per folder"
             f" ({findings or DEFAULT_FINDINGS}).", ""]
    written = None
    if platform == "darwin":
        label = f"com.watchman.{_slug(root) if len(roots) == 1 else 'clients-' + _slug(root)}"
        dest = os.path.expanduser(f"~/Library/LaunchAgents/{label}.plist")
        body = PLIST.format(label=label, command=cmd.replace("&", "&amp;").replace("<", "&lt;"),
                            hour=hour, minute=minute, log=log)
        if write:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(body)
            written = dest
            lines += [f"On a Mac, launchd is the scheduler that survives sleep. Wrote {dest}.",
                      "To start it (once):", "", f"  launchctl load {dest}", "",
                      f"To stop it later: launchctl unload {dest}"]
        else:
            lines += ["On a Mac, launchd is the scheduler that survives sleep. Rerun with --write to save this as",
                      f"{dest} and it will tell you the one launchctl line to run:", ""]
            lines += ["  " + l for l in body.splitlines()]
    return lines, written


def _dry():
    return os.environ.get("WATCHMAN_DRY_SCHEDULE", "") not in ("", "0")


def cron_line(roots, at="01:31", python=None, config=None, findings=None):
    """The one crontab line for these folders: (line, command, log path)."""
    if isinstance(roots, str):
        roots = [roots]
    m = re.match(r"^(\d{1,2}):(\d{2})$", at)
    if not m:
        raise SystemExit(f"--at wants HH:MM, got {at!r}")
    hour, minute = int(m.group(1)), int(m.group(2))
    roots = [os.path.abspath(r) for r in roots]
    cmd, log = command_for(roots, python, findings, config)
    return f"{minute} {hour} * * * {cmd} > {_q(log)} 2>&1", cmd, log


def _loaded(label):
    """True only if launchd lists the label after the load."""
    done = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    return done.returncode == 0 and any(l.split()[-1:] == [label] for l in done.stdout.splitlines())


def _in_crontab(cmd):
    """True only if `crontab -l` shows the command now."""
    done = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return done.returncode == 0 and cmd in done.stdout


def schedule(roots, at="01:31", python=None, config=None, platform=None, findings=None):
    """Put the nightly run in place. macOS: write the plist and `launchctl load` it.
    Elsewhere: append the crontab line if `crontab` exists, otherwise print it.
    Returns (lines to print, what was done: "launchd", "crontab", "printed" or "dry").
    "launchd" and "crontab" are only returned after reading the schedule back
    (`launchctl list` shows the label, or `crontab -l` shows the line); anything
    short of that is "printed", and the caller prints the line to paste."""
    if isinstance(roots, str):
        roots = [roots]
    roots = [os.path.abspath(r) for r in roots]
    cron, cmd, log = cron_line(roots, at, python, config, findings)
    minute, hour = (int(x) for x in cron.split()[:2])
    platform = platform or sys.platform
    dry = _dry()
    if platform == "darwin":
        label = f"com.watchman.{_slug(roots[0]) if len(roots) == 1 else 'clients-' + _slug(roots[0])}"
        dest = os.path.expanduser(f"~/Library/LaunchAgents/{label}.plist")
        body = PLIST.format(label=label, command=cmd.replace("&", "&amp;").replace("<", "&lt;"),
                            hour=hour, minute=minute, log=log)
        if dry:
            return [f"would write {dest} and run: launchctl load {dest}"], "dry"
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(body)
        subprocess.run(["launchctl", "unload", dest], capture_output=True)
        done = subprocess.run(["launchctl", "load", dest], capture_output=True, text=True)
        if done.returncode != 0:
            return [f"wrote {dest} but `launchctl load` failed: {done.stderr.strip()}. "
                    f"Run it by hand (launchctl load {dest}), or use cron:"], "printed"
        if not _loaded(label):
            return [f"wrote {dest} and `launchctl load` returned 0, but `launchctl list` does "
                    f"not show {label}. Run it by hand (launchctl load {dest}), or use cron:"], "printed"
        return [f"scheduled with launchd: {dest} (to stop: launchctl unload {dest})"], "launchd"
    if dry:
        return [f"would append to crontab: {cron}"], "dry"
    if not shutil.which("crontab"):
        return ["no `crontab` on this machine. Put this line in whatever runs things nightly:"], "printed"
    if _in_crontab(cmd):
        return [f"crontab already has the line for {roots[0]}; left as is"], "crontab"
    pipeline = "crontab -l 2>/dev/null | { cat; echo " + _q(cron) + "; } | crontab -"
    done = subprocess.run(["/bin/sh", "-c", pipeline], capture_output=True, text=True)
    if done.returncode != 0:
        return [f"`crontab -` refused the line: {done.stderr.strip()}. Put it in by hand "
                f"with `crontab -e`:"], "printed"
    if not _in_crontab(cmd):
        return ["`crontab -` returned 0 but `crontab -l` does not show the line. Put it in by "
                "hand with `crontab -e`:"], "printed"
    return [f"added to crontab (`crontab -l` shows it): {cron}"], "crontab"
