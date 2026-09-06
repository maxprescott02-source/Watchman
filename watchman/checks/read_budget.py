"""What costs context is what enters the window, not what exists; files an agent opens whole are capped, and growth past the last run is a bug wherever it sits."""
# Descends from brain-ops assertion 7 (rewritten 2026-08-14, Entry 079): the check
# that measured the folder's size was exempt from measuring its own largest file.
from ._util import Result, tokens

NAME = "read-budget"


def run(cfg, previous=None):
    c = cfg.section("read_budget")
    limit = int(c.get("limit_tokens", 16_000))
    runaway = int(c.get("runaway_tokens", 250_000))
    growth = float(c.get("growth_factor", 1.5))
    whole = cfg.files(c.get("opened_whole", []))
    behind = cfg.files(c.get("behind_a_tool", []))
    prev = (previous or {}).get("sizes", {})
    sizes, problems = {}, []
    for p in whole + behind:
        rel, tok = cfg.rel(p), tokens(p)
        sizes[rel] = tok
        if p in whole and tok > limit:
            problems.append(f"{rel} ~{tok:,} is opened whole and over {limit:,}; give it a "
                            f"query tool or split it")
        elif tok > runaway:
            problems.append(f"{rel} ~{tok:,} is past {runaway:,}; behind a tool or not, that "
                            f"is a runaway")
        old = prev.get(rel)
        if old and tok > old * growth and tok - old > int(c.get("growth_min_tokens", 500)):
            problems.append(f"{rel} grew from ~{old:,} to ~{tok:,} tokens since the last run")
    floor_files = c.get("session_floor", [])
    floor = sum(tokens(cfg.path(f)) for f in floor_files)
    floor_limit = int(c.get("session_floor_limit", limit))
    missing = [f for f in floor_files if tokens(cfg.path(f)) == 0]
    if missing:
        problems.append(f"session floor member(s) missing or empty: {missing}; a missing "
                        f"member scores zero and makes this greener, which is backwards")
    if floor > floor_limit:
        problems.append(f"session floor ~{floor:,} over {floor_limit:,}; split, do not raise")
    r = Result(NAME, "FAIL" if problems else "PASS",
               " · ".join(problems) if problems else
               f"{len(whole)} file(s) opened whole under {limit:,} · {len(behind)} behind a "
               f"tool under {runaway:,} · session floor ~{floor:,}/{floor_limit:,}",
               len(whole) + len(behind), int(c.get("floor", 1)))
    r.sizes = sizes
    return r
