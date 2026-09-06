"""Loads watchman.toml. Each check reads its own section; a check with no section is off.

Nothing here knows the layout of the folder it watches. That is the point:
brain-ops hard-wired its paths into one routing table and every tool imported
it, and this package replaces the table with a file the user writes.
"""
import glob
import os

try:
    import tomllib
except ImportError:                     # Python 3.10: stdlib has no tomllib yet
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
            raise SystemExit(f"no {FILENAME} in {os.path.abspath(root)}. "
                             f"Run `watchman init {root}` to write a starter.")
        with open(p, "rb") as fh:
            return cls(root, tomllib.loads(fh.read().decode("utf-8")))

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
        return float(self.data.get("watchman", {}).get("utc_offset_hours", 0))

    @property
    def heartbeat(self):
        w = self.data.get("watchman", {})
        return self.path(w.get("heartbeat", ".watchman/heartbeat.json"))
