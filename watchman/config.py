"""Loads watchman.toml. Each check reads its own section; a check with no section is off.

Nothing here knows the layout of the folder it watches. That is the point:
brain-ops hard-wired its paths into one routing table and every tool imported
it, and this package replaces the table with a file the user writes.
"""
import glob
import os

try:
    import tomllib
except ImportError:                     # Python 3.10 and earlier: stdlib has no tomllib
    from . import toml_min as tomllib

FILENAME = "watchman.toml"


class Config:
    def __init__(self, root, data):
        self.root = os.path.abspath(root)
        self.data = data

    @classmethod
    def load(cls, root, config=None):
        p = config or os.path.join(root, FILENAME)
        if not os.path.exists(p):
            raise SystemExit(f"no {FILENAME} in {os.path.abspath(root)}. Run "
                             f"`watchman init --discover {root}` to propose one from the "
                             f"files that are there, then `watchman doctor --root {root}` "
                             f"to see what each section can check.")
        with open(p, "rb") as fh:
            try:
                data = tomllib.loads(fh.read().decode("utf-8"))
            except Exception as exc:                                  # noqa: BLE001
                raise SystemExit(f"{p} is not readable as TOML: {exc}. Every line is "
                                 f"`key = value`, strings in quotes, sections in [brackets]; "
                                 f"`watchman doctor` cannot run until it parses.")
            return cls(root, data)

    def section(self, name):
        return self.data.get(name)

    def path(self, rel):
        rel = os.path.expanduser(rel)
        return rel if os.path.isabs(rel) else os.path.join(self.root, rel)

    def rel(self, path):
        return os.path.relpath(path, self.root)

    def files(self, patterns):
        """Every file matching any pattern, sorted, relative patterns rooted here."""
        out = set()
        for pat in patterns:
            out.update(p for p in glob.glob(self.path(pat), recursive=True)
                       if os.path.isfile(p))
        return sorted(out)

    @property
    def utc_offset(self):
        """Hours east of UTC. Unset means this machine's own zone: an operator
        reading "due 06:00" expects their own clock, not Greenwich."""
        w = self.data.get("watchman", {})
        if "utc_offset_hours" in w:
            return float(w["utc_offset_hours"])
        return local_utc_offset()

    @property
    def heartbeat(self):
        w = self.data.get("watchman", {})
        return self.path(w.get("heartbeat", ".watchman/heartbeat.json"))


def local_utc_offset():
    import datetime
    off = datetime.datetime.now().astimezone().utcoffset()
    return off.total_seconds() / 3600 if off else 0.0
