"""Canonical v1 JSON: UTF-8, sorted keys, compact separators, integers only.

Money is represented by decimal strings. No floats, NaN, custom objects or
implicit stringification. This is a project format, not an RFC 8785 claim.
"""
import hashlib
import json

from .types import ValidationError


def _json_value(value):
    if value is None or type(value) in (str, int, bool):
        if type(value) is str:
            try:
                value.encode("utf-8")
            except UnicodeError:
                raise ValidationError("Invalid Unicode in record.") from None
        return
    if type(value) is list:
        for item in value:
            _json_value(item)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for key, item in value.items():
            _json_value(key)
            _json_value(item)
        return
    raise ValidationError("Record contains a non-JSON or non-integer numeric value.")


def canonical_json(value):
    _json_value(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def parse_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValidationError("Duplicate JSON field.")
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=pairs)
        _json_value(value)
        return value
    except (ValueError, TypeError, RecursionError):
        raise ValidationError("Invalid control JSON.") from None
