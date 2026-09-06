"""Runs every configured check and prints the board. The counts are computed here and stated nowhere else.

Above the check lines sit the incidents: one line per underlying thing that is
wrong, folded from every check line about it, with a state against the previous
run (new, ongoing since a date, or resolved). The operator reads the incidents;
the check lines under the rule are the evidence.
"""
# brain-ops retired the assertion that kept a written count in sync across two
# documents (ids 28 and 31) and made the runner print the number instead.
import datetime
import json
import os
import traceback

from .checks import REGISTER, heartbeat, no_vacuous_pass, read_budget
from .checks._util import Result, now, today

MARK = {"PASS": "  ok  ", "WARN": " warn ", "FAIL": " FAIL "}
RULE = "-" * 72
DEFAULT_ATTENTION = "WATCHMAN.md"
BOARD_FILE = ".watchman/last-board.txt"
# Check lines whose incident folds first: the job name leads, the file follows.
_ORDER = {"expected-run": 0, "stale-state": 1}


class Results(list):
    """The board's results, with the incidents the runner folded from them."""
    incidents = ()


class Incident:
    def __init__(self, keys, members):
        self.keys = sorted(keys)
        self.members = members                          # [(check, item dict)]
        self.status = "FAIL" if any(s == "FAIL" for s, _ in members) else "WARN"
        self.state, self.since = "new", None

    @property
    def text(self):
        return "; ".join(m["text"] for _, m in self.members)

    @property
    def short(self):
        """The fact without its parentheses, for the one resolved line."""
        return "; ".join(m["text"].split(" (")[0] for _, m in self.members)

    @property
    def action(self):
        return next((m["action"] for _, m in self.members if m.get("action")), "")

    @property
    def label(self):
        return f"ongoing (since {self.since})" if self.state == "ongoing" else self.state

    def line(self):
        return f"{self.label + ':':<12} {self.text}. {self.action}".rstrip()


def _guessed(section):
    """A section is guessed when its dict says so, or every entry of a list does."""
    if isinstance(section, dict):
        return bool(section.get("guessed"))
    if isinstance(section, list) and section:
        return all(isinstance(e, dict) and e.get("guessed") for e in section)
    return False


def _any_guessed(section):
    if isinstance(section, list):
        return any(isinstance(e, dict) and e.get("guessed") for e in section)
    return _guessed(section)


def run_all(cfg, write=True):
    previous = heartbeat.read(cfg)
    results, sizes = Results([heartbeat.run(cfg)]), {}
    for section, mod in REGISTER:
        c = cfg.section(section)
        if c is None:
            continue
        try:
            r = mod.run(cfg, previous) if mod is read_budget else mod.run(cfg)
        except Exception as exc:                                # noqa: BLE001
            r = Result(mod.NAME, "FAIL", f"the check itself raised {type(exc).__name__}: "
                       f"{exc}. A check that crashes is not a check that passed",
                       0, 1)
            r.trace = traceback.format_exc()
        r.guessed = _any_guessed(c)
        if _guessed(c) and r.status == "FAIL":
            # A guess can be wrong, so a guessed section never fails: it warns,
            # and the line says it is unconfirmed until the operator says otherwise.
            r.status = "WARN"
            if not r.message.startswith("unconfirmed:"):
                r.message = "unconfirmed: " + r.message
        sizes.update(getattr(r, "sizes", {}))
        results.append(r)
    no_vacuous_pass.enforce(results)
    results.append(no_vacuous_pass.audit(results))
    results.incidents = incidents(results, previous, today(cfg))
    if write:
        heartbeat.write(cfg, results, sizes, results.incidents)
        board_path = cfg.path(BOARD_FILE)
        os.makedirs(os.path.dirname(board_path), exist_ok=True)
        with open(board_path, "w", encoding="utf-8") as fh:
            fh.write(render(results) + "\n")
        write_attention(cfg, results)
    return results


def _items(results):
    """(check, status, item) for every non-green line; a line with no items of
    its own becomes one item keyed on the check."""
    out = []
    for r in results:
        if r.status == "PASS" or r.check == no_vacuous_pass.NAME:
            continue
        if r.items:
            for it in r.items:
                out.append((r.check, r.status, it))
        else:
            sentences = [s for s in r.message.rstrip(".").split(". ") if s]
            action = sentences[-1] + "." if len(sentences) > 1 else ""
            fact = ". ".join(sentences[:-1]) if len(sentences) > 1 else r.message
            out.append((r.check, r.status, {"keys": [f"check:{r.check}"], "text": fact,
                                            "action": action}))
    return out


def incidents(results, previous=None, when=None):
    """Fold the board's non-green items into incidents: two items sharing a file
    or a job key (a file's stem is a job key) are one incident. Then set each
    incident's state against the previous heartbeat, and append the incidents
    that were open last run and are gone now, marked resolved."""
    rows = _items(results)
    groups = []                                     # [(set of keys, [members])]
    for check, status, it in rows:
        keys = set(it["keys"]) or {f"check:{check}:{len(groups)}"}
        hit = [g for g in groups if g[0] & keys]
        merged = (set().union(*(g[0] for g in hit)) | keys,
                  sum((g[1] for g in hit), []) + [(status, it, check)])
        groups = [g for g in groups if g not in hit] + [merged]
    out = []
    for keys, members in groups:
        members.sort(key=lambda m: _ORDER.get(m[2], 9))
        out.append(Incident(keys, [(s, it) for s, it, _ in members]))
    prev = (previous or {}).get("incidents", []) if previous else []
    when = (when or datetime.date.today()).isoformat()
    matched = set()
    for inc in out:
        hits = [i for i, p in enumerate(prev) if set(p.get("keys", [])) & set(inc.keys)]
        if hits:
            inc.state = "ongoing"
            inc.since = min(prev[i].get("since") or when for i in hits)
            matched.update(hits)
        else:
            inc.since = when
    for i, p in enumerate(prev):
        if i in matched:
            continue
        gone = Incident(p.get("keys", []), [("WARN", {"text": p.get("short") or p.get("text", ""),
                                                        "action": ""})])
        gone.state, gone.since = "resolved", p.get("since")
        out.append(gone)
    return out


def _counts_line(results, incs):
    counts = {s: sum(1 for r in results if r.status == s) for s in MARK}
    live = [i for i in incs if i.state != "resolved"]
    states = {s: sum(1 for i in live if i.state == s) for s in ("new", "ongoing")}
    resolved = sum(1 for i in incs if i.state == "resolved")
    parts = []
    if live:
        inner = ", ".join(f"{n} {s}" for s, n in states.items() if n)
        parts.append(f"{len(live)} incident{'s' if len(live) != 1 else ''} ({inner})")
    else:
        parts.append("0 incidents")
    if resolved:
        parts.append(f"{resolved} resolved")
    parts.append(f"{counts['FAIL']} check{'s' if counts['FAIL'] != 1 else ''} failed")
    if counts["WARN"]:
        parts.append(f"{counts['WARN']} warned")
    unconfirmed = sum(1 for r in results if getattr(r, "guessed", False))
    ran = f"{len(results)} ran"
    if unconfirmed:
        ran += f" ({len(results) - unconfirmed} confirmed, {unconfirmed} unconfirmed)"
    parts.append(ran)
    return " · ".join(parts)


def render(results, quiet=False):
    incs = list(getattr(results, "incidents", None) or incidents(results))
    lines = [i.line() for i in incs]
    if lines:
        lines.append(RULE)
    for r in results:
        if quiet and r.status == "PASS":
            continue
        lines.append(f"[{MARK[r.status]}] {r.check:<22} {r.message}")
    lines.append("")
    lines.append(_counts_line(results, incs))
    return "\n".join(lines)


def render_json(results):
    incs = list(getattr(results, "incidents", None) or incidents(results))
    return json.dumps({"incidents": [{"state": i.state, "since": i.since, "status": i.status,
                                      "keys": i.keys, "text": i.text, "action": i.action}
                                     for i in incs],
                       "results": [r.as_dict() for r in results],
                       "counts": {s: sum(1 for r in results if r.status == s) for s in MARK}},
                      indent=1)


def exit_code(results):
    return 1 if any(r.status == "FAIL" for r in results) else 0


def attention_path(cfg):
    """Where WATCHMAN.md goes, or None when the operator turned it off
    (`attention_file = ""` or `false` under [watchman])."""
    w = cfg.section("watchman") or {}
    name = w.get("attention_file", DEFAULT_ATTENTION)
    if name is False or not name:
        return None
    return cfg.path(str(name))


def zone(cfg):
    return f"UTC{cfg.utc_offset:+.0f}" if cfg.utc_offset else "UTC"


def render_attention(cfg, results):
    """WATCHMAN.md: the moment it was written first, so a reader can tell when
    watchman itself has stopped; then only the unresolved incidents, each with its
    state and one action, or one line saying nothing needs you; then the board's
    path. The file exists either way, because an operator who sees it vanish
    thinks the tool died."""
    incs = [i for i in getattr(results, "incidents", []) if i.state != "resolved"]
    lines = [f"Last checked: {now(cfg).strftime('%Y-%m-%d %H:%M')} {zone(cfg)}", ""]
    for inc in incs:
        lines.append(f"- {inc.label}: {inc.text}. {inc.action}".rstrip())
    if not incs:
        lines.append("Healthy: nothing needs you.")
    lines += ["", f"full board: {cfg.rel(cfg.path(BOARD_FILE))}"]
    return "\n".join(lines) + "\n"


def write_attention(cfg, results):
    dest = attention_path(cfg)
    if dest is None:
        return None
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(render_attention(cfg, results))
    return dest


def render_findings(results, cfg, title=None):
    """The audit deliverable: the board as a findings report, one section per line
    that is not green, each carrying the check's own reason for existing. This is
    what a client pays for; the board is what the operator reads."""
    title = title or f"Findings: {os.path.basename(cfg.root) or cfg.root}"
    why = {}
    for _section, mod in REGISTER + [("heartbeat", heartbeat), ("no_vacuous_pass", no_vacuous_pass)]:
        why[mod.NAME] = (mod.__doc__ or "").strip().split("\n")[0]
    passed = [r for r in results if r.status == "PASS"]
    bad = [r for r in results if r.status != "PASS"]
    incs = [i for i in getattr(results, "incidents", []) if i.state != "resolved"]
    out = [f"# {title}", "",
           f"*watchman {__import__('watchman').__version__} over `{cfg.root}`, "
           f"{datetime.date.today().isoformat()}. {len(passed)} passed, "
           f"{sum(1 for r in results if r.status == 'WARN')} warned, "
           f"{sum(1 for r in results if r.status == 'FAIL')} failed, {len(results)} ran.*", ""]
    if incs:
        out += ["## Incidents", ""] + [f"- {i.label}: {i.text}. {i.action}".rstrip() for i in incs] + [""]
    if not bad:
        out += ["Nothing to report. Every configured check passed over a population at or above its floor.", ""]
    for r in sorted(bad, key=lambda r: (r.status != "FAIL", r.check)):
        out += [f"## {r.status}: {r.check}", "", r.message, "",
                f"**Why this check exists.** {why.get(r.check, '')}", ""]
    if passed:
        out += ["## Passed", "", ", ".join(r.check for r in passed), ""]
    return "\n".join(out)
