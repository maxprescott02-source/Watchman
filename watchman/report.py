"""Runs every configured check and prints the board. The counts are computed here and stated nowhere else."""
# brain-ops retired the assertion that kept a written count in sync across two
# documents (ids 28 and 31) and made the runner print the number instead.
import json
import traceback

from .checks import REGISTER, heartbeat, no_vacuous_pass, read_budget
from .checks._util import Result

MARK = {"PASS": "  ok  ", "WARN": " warn ", "FAIL": " FAIL "}


def run_all(cfg, write=True):
    previous = heartbeat.read(cfg)
    results, sizes = [heartbeat.run(cfg)], {}
    for section, mod in REGISTER:
        if cfg.section(section) is None:
            continue
        try:
            r = mod.run(cfg, previous) if mod is read_budget else mod.run(cfg)
        except Exception as exc:                                # noqa: BLE001
            r = Result(mod.NAME, "FAIL", f"the check itself raised {type(exc).__name__}: "
                       f"{exc}. A check that crashes is not a check that passed",
                       0, 1)
            r.trace = traceback.format_exc()
        sizes.update(getattr(r, "sizes", {}))
        results.append(r)
    no_vacuous_pass.enforce(results)
    results.append(no_vacuous_pass.audit(results))
    if write:
        heartbeat.write(cfg, results, sizes)
    return results


def render(results, quiet=False):
    lines = []
    for r in results:
        if quiet and r.status == "PASS":
            continue
        lines.append(f"[{MARK[r.status]}] {r.check:<22} {r.message}")
    counts = {s: sum(1 for r in results if r.status == s) for s in MARK}
    lines.append("")
    lines.append(f"{counts['PASS']} passed · {counts['WARN']} warnings · "
                 f"{counts['FAIL']} failed · {len(results)} checks ran")
    return "\n".join(lines)


def render_json(results):
    return json.dumps({"results": [r.as_dict() for r in results],
                       "counts": {s: sum(1 for r in results if r.status == s) for s in MARK}},
                      indent=1)


def exit_code(results):
    return 1 if any(r.status == "FAIL" for r in results) else 0


def render_findings(results, cfg, title="Findings"):
    """The audit deliverable: the board as a findings report, one section per line
    that is not green, each carrying the check's own reason for existing. This is
    what a client pays for; the board is what the operator reads."""
    import datetime
    why = {}
    for _section, mod in REGISTER + [("heartbeat", heartbeat), ("no_vacuous_pass", no_vacuous_pass)]:
        why[mod.NAME] = (mod.__doc__ or "").strip().split("\n")[0]
    passed = [r for r in results if r.status == "PASS"]
    bad = [r for r in results if r.status != "PASS"]
    out = [f"# {title}", "",
           f"*watchman {__import__('watchman').__version__} over `{cfg.root}`, "
           f"{datetime.date.today().isoformat()}. {len(passed)} passed, "
           f"{sum(1 for r in results if r.status == 'WARN')} warned, "
           f"{sum(1 for r in results if r.status == 'FAIL')} failed, {len(results)} ran.*", ""]
    if not bad:
        out += ["Nothing to report. Every configured check passed over a population at or above its floor.", ""]
    for r in sorted(bad, key=lambda r: (r.status != "FAIL", r.check)):
        out += [f"## {r.status}: {r.check}", "", r.message, "",
                f"**Why this check exists.** {why.get(r.check, '')}", ""]
    if passed:
        out += ["## Passed", "", ", ".join(r.check for r in passed), ""]
    return "\n".join(out)
