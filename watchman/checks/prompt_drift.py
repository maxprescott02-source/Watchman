"""A scheduled prompt that names a path which no longer exists fails silently at 4am; a mirror that drifts from the live prompt is worse than no mirror."""
# Descends from brain-ops assertion 23 (2026-08-14): three of six prompts kept
# renamed paths for two days, and assertion 14 (mirrors that had never been compared).
import glob
import os
import re

from ._util import item, _plural, read, Result

NAME = "prompt-drift"
TOKEN = re.compile(r"`([^`\n]+)`")
PLACEHOLDER = re.compile(r"YYYY|MM-DD|<|>|\[n|\*|\{")
EXTS = (".md", ".py", ".json", ".toml", ".html", ".xlsx", ".csv", ".txt")


def _looks_like_path(s):
    if not s or s.startswith(("/", "~", "http")) or '"' in s or "'" in s or " " in s:
        return False
    return "/" in s or s.endswith(EXTS)


def _resolves(cfg, rel):
    target = cfg.path(rel)
    if os.path.exists(target) or glob.glob(target):
        return True
    if "/" in rel:
        return False
    return bool(glob.glob(os.path.join(cfg.root, "**", rel), recursive=True))


def run(cfg):
    c = cfg.section("prompts")
    mirrors = cfg.files(c.get("mirrors", ["tasks/*.md"]))
    floor = int(c.get("floor", 1))
    exempt = set(c.get("exempt", []))
    dead, drift, extracted, items = [], [], 0, []
    live_dir = cfg.path(c["live_dir"]) if c.get("live_dir") else None
    for m in mirrors:
        text = read(m) or ""
        rel = cfg.rel(m)
        here = 0
        for tok in TOKEN.finditer(text):
            raw = tok.group(1).strip().rstrip(".,;:)")
            if not _looks_like_path(raw) or PLACEHOLDER.search(raw) or raw in exempt:
                continue
            here += 1
            if not _resolves(cfg, raw):
                dead.append(f"{rel} -> {raw}")
                items.append(item(f"{rel} names {raw}, which does not exist",
                                  f"Fix the path in {rel} or create {raw}.", files=[rel]))
        extracted += here
        if here == 0:
            dead.append(f"{rel} -> no paths extracted at all (mirror or pattern broken)")
            items.append(item(f"{rel} names no paths in backticks at all",
                              f"Open {rel}: either it is not a prompt, so take it out of "
                              f"[prompts] mirrors, or its paths are not in backticks.", files=[rel]))
        if live_dir:
            name = os.path.splitext(os.path.basename(m))[0]
            live = os.path.join(live_dir, name, c.get("live_file", "SKILL.md"))
            if not os.path.exists(live):
                drift.append(f"{rel} mirrored but not live")
            elif read(live) != text:
                drift.append(f"{rel} differs from the live prompt")
    if dead:
        return Result(NAME, "FAIL", f"{_plural(len(dead), 'dead path')} in {_plural(len(mirrors), 'prompt')}: "
                      + " · ".join(sorted(dead)[:6]) + ". The agent is told to read something "
                      "that is not there. Fix the path in the prompt or create what it names.",
                      len(mirrors), floor, items=items)
    if drift:
        return Result(NAME, "FAIL", " · ".join(drift[:6]) + ". A stale mirror is the only "
                      "automated view of the prompt. Re-mirror it from the live prompt.",
                      len(mirrors), floor,
                      items=[item(d, "Re-mirror it from the live prompt.",
                                  files=[d.split(" ")[0]]) for d in drift])
    note = "compared byte for byte with live" if live_dir else "no live_dir set, mirrors unverified"
    return Result(NAME, "PASS", f"{_plural(extracted, 'path')} across {_plural(len(mirrors), 'prompt')} all "
                  f"resolve · {note}", len(mirrors), floor)
