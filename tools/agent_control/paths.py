"""Lexical scope checks only; no filesystem access or confinement."""
from dataclasses import dataclass
from fnmatch import fnmatchcase
import unicodedata

from .types import PathKind, ValidationError


def normalize_path(value, *, directory=False):
    if type(value) is not str or not value or value != value.strip():
        raise ValidationError("Invalid relative path.")
    if any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in value):
        raise ValidationError("Control characters in path.")
    if value.startswith("/") or any(c in value for c in "\\:%") or "//" in value:
        raise ValidationError("Ambiguous relative path.")
    if directory and value.endswith("/"):
        value = value[:-1]
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValidationError("Invalid path component.")
    if unicodedata.normalize("NFC", value) != value:
        raise ValidationError("Path must use NFC Unicode.")
    return value


@dataclass(frozen=True)
class PathRule:
    kind: PathKind
    path: str

    def __post_init__(self):
        try:
            kind = PathKind(self.kind)
        except (ValueError, TypeError):
            raise ValidationError("Invalid path rule kind.") from None
        path = normalize_path(self.path, directory=kind == PathKind.DIRECTORY)
        if any(c in path for c in "?[]{}!"):
            raise ValidationError("Unsupported path/glob syntax.")
        parts = path.split("/")
        if kind != PathKind.GLOB and "*" in path:
            raise ValidationError("Wildcard requires a GLOB rule.")
        if kind == PathKind.GLOB:
            # Literal directories, then optional **, then optional basename *.
            if "*" not in path or parts.count("**") > 1:
                raise ValidationError("Invalid glob.")
            for i, part in enumerate(parts):
                if "*" in part and part != "**" and (i != len(parts) - 1 or "**" in part):
                    raise ValidationError("Unsupported glob component.")
                if part == "**" and i not in {len(parts) - 1, len(parts) - 2}:
                    raise ValidationError("Recursive glob must be terminal or precede a basename.")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "path", path)

    @classmethod
    def from_dict(cls, data):
        if type(data) is not dict or set(data) != {"kind", "path"}:
            raise ValidationError("Invalid path rule fields.")
        return cls(data["kind"], data["path"])

    def to_dict(self):
        return {"kind": self.kind.value, "path": self.path}

    def matches(self, path):
        path = normalize_path(path)
        if self.kind == PathKind.FILE:
            return self.path == path
        if self.kind == PathKind.DIRECTORY:
            return path == self.path or path.startswith(self.path + "/")
        pattern, actual = self.path.split("/"), path.split("/")
        if "**" in pattern:
            index = pattern.index("**")
            if actual[:index] != pattern[:index]:
                return False
            if index == len(pattern) - 1:
                return len(actual) >= index
            return len(actual) > index and fnmatchcase(actual[-1], pattern[-1])
        return len(pattern) == len(actual) and all(fnmatchcase(a, p) for a, p in zip(actual, pattern))

    def envelope(self):
        if self.kind != PathKind.GLOB:
            return self.kind, self.path
        literal = []
        for part in self.path.split("/"):
            if "*" in part:
                break
            literal.append(part)
        return PathKind.DIRECTORY, "/".join(literal)


def overlaps(left, right):
    """Conservative reservation overlap, including not-yet-created glob matches."""
    lk, lp = left.envelope()
    rk, rp = right.envelope()
    if not lp or not rp or lp == rp:
        return True
    return ((lk == PathKind.DIRECTORY and rp.startswith(lp + "/")) or
            (rk == PathKind.DIRECTORY and lp.startswith(rp + "/")))


def permits_write(path, allowed, read_only=(), forbidden=()):
    normalize_path(path)
    if any(rule.matches(path) for rule in (*forbidden, *read_only)):
        return False
    return any(rule.matches(path) for rule in allowed)


def contained_by(rule, parent):
    """Conservative grant-subset check; never infer inclusion from current files."""
    if rule == parent:
        return True
    kind, path = rule.envelope()
    return parent.kind == PathKind.DIRECTORY and bool(path) and (
        path == parent.path or path.startswith(parent.path + "/"))
