"""A number written in prose about a thing the folder can measure is measured on every run; a figure nobody has checked since it was typed is the defect."""
# Descends from brain-ops assertion 48 (2026-08-20): CLAUDE.md said can.py cost
# ~400 tokens in two places and it measured 1,287, in the file every thread read first.
import re
import subprocess

from ._util import log_entries, _plural, read, Result, tokens

NAME = "stated-vs-measured"
TOKENS = re.compile(r"~\s*([\d][\d,]*)\s*(k?)\s*tokens?\b", re.I)
ENTRIES = re.compile(r"\b([\d][\d,]*)\s+entries\b", re.I)
PASSED = re.compile(r"\b(\d+)\s+(?:passed|checks?|assertions?)\b", re.I)


def _num(m):
    return int(m.group(1).replace(",", "")) * (1000 if len(m.groups()) > 1 and m.group(2) else 1)


def _measure(cfg, spec):
    if "file" in spec:
        return tokens(cfg.path(spec["file"]))
    proc = subprocess.run(spec["command"], capture_output=True, cwd=cfg.root, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"exit {proc.returncode}")
    return len(proc.stdout) // 4


def run(cfg):
    c = cfg.section("stated")
    tol = float(c.get("tolerance", 0.30))
    measured, problems, notes = {}, [], []
    for spec in c.get("measure", []):
        try:
            n = _measure(cfg, spec)
        except Exception as exc:                                # noqa: BLE001
            problems.append(f"{spec['name']} could not be measured ({exc}); an "
                            f"unmeasurable claim is an unchecked one")
            continue
        measured[spec["name"]] = n
        if n <= 0:
            problems.append(f"{spec['name']} measured 0, which makes any claim trivially generous")
        elif n > int(spec.get("ceiling", 10 ** 9)):
            problems.append(f"{spec['name']} is ~{n:,} tokens, past its {spec['ceiling']:,} ceiling")
        notes.append(f"{spec['name']} ~{n:,}")
    entry_count = len(log_entries(cfg))
    claims = 0
    for path in cfg.files(c.get("files", [])):
        rel = cfg.rel(path)
        for i, line in enumerate((read(path) or "").splitlines(), 1):
            for m in TOKENS.finditer(line):
                claims += 1
                named = [k for k in measured if k in line]
                if len(named) != 1:
                    problems.append(f"{rel}:{i} states ~{_num(m):,} tokens and names "
                                    f"{'nothing' if not named else 'more than one thing'} "
                                    f"this can measure; teach it or delete the number")
                    continue
                got, stated = measured[named[0]], _num(m)
                if not stated * (1 - tol) <= got <= stated * (1 + tol):
                    problems.append(f"{rel}:{i} says ~{stated:,} tokens for {named[0]}, "
                                    f"measured ~{got:,}. Fix the number, not the band")
            for m in ENTRIES.finditer(line):
                claims += 1
                if int(m.group(1).replace(",", "")) != entry_count:
                    problems.append(f"{rel}:{i} says {m.group(1)} entries, the log holds "
                                    f"{entry_count}")
            if PASSED.search(line) and c.get("forbid_board_counts", True):
                claims += 1
                problems.append(f"{rel}:{i} states a count of checks. The board prints "
                                f"that number; no file may state it")
    pop = len(measured) + claims
    if problems:
        return Result(NAME, "FAIL", " · ".join(problems[:4]), pop, 1)
    return Result(NAME, "PASS", f"{_plural(len(measured), 'measurable')} under ceiling "
                  f"({' · '.join(notes)}) · {_plural(claims, 'stated number')} all within "
                  f"{int(tol * 100)}%", pop, 1)
