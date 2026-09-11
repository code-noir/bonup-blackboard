"""Validator for the JSON Schema keyword subset used by the bundled v1 schemas.

Not a general JSON Schema implementation. No remote references, network calls,
code execution, database access or package dependencies. Formats are assertions.
"""
from datetime import datetime
from functools import lru_cache
from pathlib import Path
import re
from uuid import UUID

from .paths import PathRule, normalize_path
from .serialization import canonical_json, parse_json
from .types import ValidationError

DOCS = Path(__file__).resolve().parents[2] / "docs" / "agent-control"


@lru_cache(maxsize=3)
def _document_text(name):
    if name not in {"schemas.json", "policy.json", "document-authority.json"}:
        raise ValidationError("Unknown policy document.")
    return (DOCS / name).read_text(encoding="utf-8")


def document(name):
    # Return a fresh value; callers cannot mutate cached policy/schema state.
    return parse_json(_document_text(name))


def valid_format(name, value):
    try:
        if name == "uuid":
            return str(UUID(value)) == value
        if name == "utc-time":
            return bool(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z", value)) and datetime.fromisoformat(value).utcoffset().total_seconds() == 0
        if name == "sha256":
            return bool(re.fullmatch(r"[a-f0-9]{64}", value))
        if name == "git-oid":
            return bool(re.fullmatch(r"(?:[a-f0-9]{40}|[a-f0-9]{64})", value))
        if name in {"task-id", "candidate-id", "record-id"}:
            patterns = {
                "task-id": r"ATS-([0-9]{4,})",
                "candidate-id": r"IC-ATS-([0-9]{4,})-([0-9]{2,})",
                "record-id": r"(?:FINDING|CONFLICT|DECISION)-([0-9]{4,})",
            }
            match = re.fullmatch(patterns[name], value)
            return bool(match) and all(int(n) > 0 and (len(n) <= width or not n.startswith("0")) for n, width in zip(match.groups(), [4, 2]))
        if name == "agent-id":
            return bool(re.fullmatch(r"(?:ARCH|FE|BE|QA|PROD|RES|BI|CX|MKT|SEC|DOC|EDU)-(?:0[1-9]|[1-9][0-9]+)", value))
        if name == "money":
            return bool(re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,6})?", value))
        if name == "relative-path":
            return PathRule("FILE", value).path == value
        if name == "absolute-path":
            return value.startswith("/") and normalize_path(value[1:]) == value[1:] and not any(c in value for c in "*?[]{}!")
        if name == "branch":
            return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]*", value)) and ".." not in value and "//" not in value and all(p and not p.startswith(".") and not p.endswith((".", ".lock")) for p in value.split("/"))
        if name == "resource-key":
            return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}", value))
    except (ValueError, TypeError, OverflowError):
        return False
    raise ValidationError("Unknown schema format.")


def _check(value, spec, definitions, location):
    if "$ref" in spec:
        prefix = "#/$defs/"
        reference = spec["$ref"]
        if not reference.startswith(prefix) or reference[len(prefix):] not in definitions:
            raise ValidationError("Invalid local schema reference.")
        return _check(value, definitions[reference[len(prefix):]], definitions, location)
    if "anyOf" in spec:
        for option in spec["anyOf"]:
            try:
                _check(value, option, definitions, location)
                return
            except ValidationError:
                continue
        raise ValidationError(f"Invalid nullable field: {location}.")
    types = {"string": str, "integer": int, "boolean": bool, "object": dict, "array": list, "null": type(None)}
    if type(value) is not types[spec["type"]]:
        raise ValidationError(f"Invalid field type: {location}.")
    if "const" in spec and value != spec["const"] or "enum" in spec and value not in spec["enum"]:
        raise ValidationError(f"Invalid enum/version: {location}.")
    if type(value) is str:
        if len(value) < spec.get("minLength", 0) or len(value) > spec.get("maxLength", 4096):
            raise ValidationError(f"Invalid field length: {location}.")
        if "format" in spec and not valid_format(spec["format"], value):
            raise ValidationError(f"Invalid field format: {location}.")
    if type(value) is int and value < spec.get("minimum", value):
        raise ValidationError(f"Invalid field minimum: {location}.")
    if type(value) is list:
        if len(value) < spec.get("minItems", 0):
            raise ValidationError(f"Empty required list: {location}.")
        if spec.get("uniqueItems") and len({canonical_json(v) for v in value}) != len(value):
            raise ValidationError(f"Duplicate list entry: {location}.")
        for item in value:
            _check(item, spec["items"], definitions, location + "[]")
    if type(value) is dict:
        properties = spec.get("properties", {})
        if any(key not in value for key in spec.get("required", [])):
            raise ValidationError(f"Missing field: {location}.")
        for key, item in value.items():
            if "propertyNames" in spec:
                _check(key, spec["propertyNames"], definitions, location + ".<key>")
            rule = properties.get(key, spec.get("additionalProperties", False))
            if rule is False:
                raise ValidationError(f"Unexpected field: {location}.")
            _check(item, rule, definitions, location + "." + (key if key in properties else "<value>"))


def validate_schema(name, data):
    canonical_json(data)
    definitions = document("schemas.json")["$defs"]
    if name not in definitions:
        raise ValidationError("Unknown record schema.")
    _check(data, definitions[name], definitions, name)


def timestamp(value):
    return datetime.fromisoformat(value)
