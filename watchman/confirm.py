"""`watchman confirm`: the guessed sections of watchman.toml, one by one, and how to
confirm each; `--all` confirms every one in place.

`init --discover` writes `guessed = true` into every section it inferred rather
than read. A guessed check can warn but never fail, and its line starts with
"unconfirmed:". Confirming is deleting that one line; this command does the
deleting so the operator does not open the file.
"""
import os
import re
from .checks._util import _plural

HEADER = re.compile(r"^\s*(\[\[?)([^\]]+)\]\]?\s*(?:#\s*(.*))?$")
GUESSED = re.compile(r"^\s*guessed\s*=\s*true\b.*$")
NAME = re.compile(r"^\s*(?:name|file)\s*=\s*[\"']([^\"']*)[\"']")
TODO = re.compile(r"^\s*([^#\s][^#]*?)\s*#\s*TODO confirm\b")


def guessed_sections(text):
    """One dict per guessed section: `label` ([stale_state], [[expected]]), `name`
    (its name or file, or None), `line` (of the `guessed = true` line), `evidence`
    (the comment discover wrote on the section header: what it saw), `header`
    (the header's line number) and `edits` ([(line number, toml line)] for every
    line in the section discover marked `# TODO confirm`)."""
    out, cur = [], None
    for i, line in enumerate(text.splitlines(), 1):
        h = HEADER.match(line)
        if h:
            cur = {"label": f"{h.group(1)}{h.group(2).strip()}{']' * len(h.group(1))}",
                   "name": None, "line": None, "evidence": (h.group(3) or "").strip(),
                   "header": i, "edits": []}
            continue
        if cur is None:
            cur = {"label": "(top)", "name": None, "line": None, "evidence": "", "header": 1,
                   "edits": []}
        n = NAME.match(line)
        if n and cur["name"] is None:
            cur["name"] = n.group(1)
        if GUESSED.match(line):
            cur["line"] = i
            out.append(cur)
            continue
        t = TODO.match(line)
        if t:
            cur["edits"].append((i, t.group(1).strip()))
    return out


def strip_guessed(text):
    """The same text without its `guessed = true` lines. Returns (text, removed)."""
    kept, removed = [], 0
    for line in text.splitlines(keepends=True):
        if GUESSED.match(line):
            removed += 1
            continue
        kept.append(line)
    return "".join(kept), removed


def run(path, everything=False, prog="watchman"):
    """Returns the lines to print. Rewrites `path` only with `everything`."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    found = guessed_sections(text)
    if not found:
        return [f"nothing in {path} is marked guessed; every section is confirmed"]
    if everything:
        new, removed = strip_guessed(text)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new)
        return [f"confirmed {_plural(removed, 'section')} in {path}: every `guessed = true` line is gone. "
                f"Their checks can now fail as well as warn."]
    root = os.path.dirname(os.path.abspath(path))
    base = os.path.basename(path)
    accept = f"{prog} confirm --all --root {root}"
    lines = [f"{_plural(len(found), 'guessed section')} in {path}. Each can warn but never fail until "
             f"you confirm it. One line each: what it is, what it was guessed from, and the "
             f"two ways to settle it.", ""]
    for g in found:
        who = f"{g['label']} {g['name']}" if g["name"] else g["label"]
        evidence = f"guessed from: {g['evidence']}" if g["evidence"] else "guessed with no evidence written down"
        if g["edits"]:
            change = " or ".join(f"line {n} of {base} ({toml})" for n, toml in g["edits"])
        else:
            change = f"the section at line {g['header']} of {base}"
        lines.append(f"{who} ({base} line {g['header']}): {evidence}. To accept: {accept}. "
                     f"To change: edit {change}, then delete line {g['line']} (guessed = true).")
    return lines
