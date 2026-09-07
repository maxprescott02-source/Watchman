"""Shared helpers. One parser per shape, so two checks cannot disagree about what a row is.

The ledger parser lived inside brain-ops' check.py until a second consumer needed
it; two copies of a parser is a sync problem exactly like two copies of a rule.
"""
import datetime
import os
import re

DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


class Result:
    """One line of the board.

    population and floor are compulsory. A check that passed over fewer items
    than its floor is flipped to FAIL by the runner, never by the check's own
    good manners (brain-ops assertions 1, 13, 14: three green checks over empty
    input, found 2026-08-14).
    """

    def __init__(self, check, status, message, population, floor=1, items=None):
        self.check, self.status, self.message = check, status, message
        self.population, self.floor = population, floor
        # items: the things this line is about, one dict each, so the runner can
        # fold two lines about the same file or job into one incident. Keys:
        # `keys` (a list like ["file:inbox-summary.md", "job:inbox-summary"]),
        # `text` (the fact, short) and `action` (what the operator does).
        self.items = list(items or [])
        # set by the runner when the section that switched the check on is guessed
        self.guessed = False

    def as_dict(self):
        return {"check": self.check, "status": self.status, "message": self.message,
                "population": self.population, "floor": self.floor, "guessed": self.guessed,
                "items": self.items}


def item(text, action, files=(), jobs=(), links=(), **extra):
    """One thing a board line is about. `files` are paths relative to root, `jobs`
    are job names; a file's stem is also a job key, so "inbox-summary.md" and the
    job "inbox-summary" describe the same thing. `links` are keys this item folds
    with when another item carries them as keys, but never link to link: an
    expected-run item links to its evidence file, so a stale-state item about
    that file joins it, while two jobs sharing one log stay two incidents.
    `extra` fields (say, what a stale file says) ride along for the runner."""
    keys = []
    for f in files:
        f = f.replace(os.sep, "/").rstrip("/")
        keys.append("file:" + f)
        stem = os.path.splitext(os.path.basename(f))[0]
        if stem:
            keys.append("job:" + stem.lower())
    for j in jobs:
        keys.append("job:" + j.strip().lower())
    out = {"keys": keys, "text": text, "action": action}
    if links:
        out["links"] = list(links)
    out.update(extra)
    return out


def _plural(n, word, plural=None):
    """`1 day`, `2 days`, `1 entry`, `2 entries`: the count and the word agree."""
    return f"{n} {word if n == 1 else (plural or word + 's')}"


def now(cfg):
    tz = datetime.timezone(datetime.timedelta(hours=cfg.utc_offset))
    return datetime.datetime.now(tz)


def today(cfg):
    return now(cfg).date()


def parse_date(s):
    try:
        return datetime.date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def tokens(path):
    """Bytes over four. Crude, stable, and the same estimate every check uses."""
    try:
        return os.path.getsize(path) // 4
    except OSError:
        return 0


def table_rows(text, key):
    """[(heading, header_cells, row_cells)] for every markdown table whose header
    starts with `key`. Tables keyed on anything else are data about the ledger,
    not rows in it, and are skipped by construction."""
    out, heading, header = [], None, None
    for line in (text or "").splitlines():
        if line.startswith("## "):
            heading, header = line[3:].strip(), None
            continue
        if not line.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == key:
            header = cells
            continue
        if header is None or set("".join(cells)) <= set("-: "):
            continue
        out.append((heading, header, cells))
    return out


def log_entries(cfg):
    """[(path, lineno, number, date)] across every configured log file.

    The heading regex is the log's contract and lives in one place: the config.
    brain-ops copied it into four files and a format change would have made
    zero entries parse everywhere at once.
    """
    log = cfg.section("log") or {}
    pat = re.compile(log.get("heading", r"^##\s+(?P<date>\d{4}-\d{2}-\d{2}).*?Entry\s+(?P<n>\d+)"))
    rows = []
    for p in cfg.files(log.get("files", [])):
        for i, line in enumerate((read(p) or "").splitlines(), 1):
            m = pat.match(line)
            if m:
                rows.append((p, i, int(m.group("n")), m.group("date")))
    return rows
