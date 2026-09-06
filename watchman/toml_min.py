"""A fallback for Python 3.10, which has no tomllib. Parses the subset watchman.toml uses:
[tables], [[arrays of tables]], quoted strings, numbers, booleans, and flat arrays."""
import re

KV = re.compile(r"^([A-Za-z0-9_-]+)\s*=\s*(.+)$")


def _value(s):
    s = s.strip()
    if s.startswith("["):
        inner = s[1:s.rindex("]")].strip()
        return [_value(x) for x in _split(inner)] if inner else []
    if s[0] in "\"'":
        q = s[0]
        end = s.index(q, 1) if q == "'" else _unescaped_end(s)
        raw = s[1:end]
        if q == "'":
            return raw
        for esc, ch in (("\\\\", "\0"), ('\\"', '"'), ("\\n", "\n"), ("\\t", "\t")):
            raw = raw.replace(esc, ch)
        return raw.replace("\0", "\\")
    if s in ("true", "false"):
        return s == "true"
    return float(s) if "." in s else int(s)


def _unescaped_end(s):
    i = 1
    while i < len(s):
        if s[i] == "\\":
            i += 2
            continue
        if s[i] == '"':
            return i
        i += 1
    raise ValueError(f"unterminated string: {s}")


def _split(s):
    out, depth, cur, q = [], 0, "", None
    for ch in s:
        if q:
            cur += ch
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        elif ch == "," and depth == 0:
            out.append(cur)
            cur = ""
            continue
        cur += ch
    if cur.strip():
        out.append(cur)
    return out


def loads(text):
    root, cur = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[["):
            name = line[2:line.index("]]")].strip()
            parent, key = root, name
            if "." in name:
                head, key = name.rsplit(".", 1)
                parent = root.setdefault(head, {})
            parent.setdefault(key, []).append({})
            cur = parent[key][-1]
            continue
        if line.startswith("["):
            name = line[1:line.index("]")].strip()
            parent, key = root, name
            if "." in name:
                head, key = name.rsplit(".", 1)
                parent = root[head][-1] if isinstance(root.get(head), list) else root.setdefault(head, {})
            cur = parent.setdefault(key, {})
            continue
        m = KV.match(line)
        if not m:
            raise ValueError(f"cannot parse: {raw}")
        val = m.group(2)
        if not val.lstrip().startswith(("'", '"')) and "#" in val:
            val = val[:val.index("#")]
        elif val.lstrip().startswith(("'", '"')):
            q = val.lstrip()[0]
            end = (val.index(q, 1) if q == "'" else _unescaped_end(val.lstrip())) + 1
            val = val.lstrip()[:end]
        (cur if cur is not None else root)[m.group(1)] = _value(val)
    return root
