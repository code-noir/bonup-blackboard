"""Canonical v1 JSON: UTF-8, sorted keys, compact separators, integers only.

Money is represented by decimal strings. No floats, NaN, custom objects or
implicit stringification. This is a project format, not an RFC 8785 claim.
"""
import hashlib
import json

from .types import ValidationError


class JSONDecodeFailure(ValidationError):
    """JSON syntax failure carrying only code-owned bounded metadata."""

    def __init__(self, category, line, column, position, character_count):
        super().__init__("Invalid control JSON.")
        self.category = category
        self.line = line
        self.column = column
        self.position = position
        self.character_count = character_count


class StrictJSONValidationFailure(ValidationError):
    """Strict canonical JSON rejection without provider-derived detail."""

    def __init__(self):
        super().__init__("Strict JSON validation failed.")


def _json_error_category(message):
    if message == "Expecting value":
        return "EXPECTING_VALUE"
    if message == "Expecting property name enclosed in double quotes":
        return "EXPECTING_PROPERTY_NAME"
    if message == "Expecting ':' delimiter":
        return "EXPECTING_COLON"
    if message == "Expecting ',' delimiter":
        return "EXPECTING_COMMA"
    if message.startswith("Unterminated string"):
        return "UNTERMINATED_STRING"
    if message.startswith("Invalid \\escape"):
        return "INVALID_ESCAPE"
    if message.startswith("Invalid control character"):
        return "INVALID_CONTROL_CHARACTER"
    if message == "Extra data":
        return "EXTRA_DATA"
    return "OTHER_JSON_SYNTAX"


def _json_value(value):
    if value is None or type(value) in (str, int, bool):
        if type(value) is str:
            try:
                value.encode("utf-8")
            except UnicodeError:
                raise StrictJSONValidationFailure() from None
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
    raise StrictJSONValidationFailure()


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
                raise StrictJSONValidationFailure()
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=pairs)
        _json_value(value)
        return value
    except json.JSONDecodeError as error:
        raise JSONDecodeFailure(
            _json_error_category(error.msg), error.lineno, error.colno,
            error.pos, len(text) if type(text) is str else 0,
        ) from None
    except (ValueError, TypeError, RecursionError):
        raise StrictJSONValidationFailure() from None
