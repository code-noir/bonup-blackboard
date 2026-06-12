import json
import re
from html import unescape


def _coerce_snapshot(content_snapshot):
    if isinstance(content_snapshot, dict):
        return content_snapshot
    if content_snapshot is None:
        return {}
    raw = str(content_snapshot or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {"content_html": raw} if raw.startswith("<") else {"raw_content": raw}
    return parsed if isinstance(parsed, dict) else {}


def _text(value):
    if value is None:
        return ""
    return str(value).strip()


def _slug(value):
    normalized = unescape(_text(value)).lower()
    normalized = re.sub(r"<[^>]+>", " ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return normalized or "section"


def _section_items(raw_sections):
    if isinstance(raw_sections, list):
        return raw_sections
    if isinstance(raw_sections, dict):
        items = []
        for key, value in raw_sections.items():
            if isinstance(value, dict):
                item = dict(value)
            else:
                item = {"body": value}
            item.setdefault("id", key)
            item.setdefault("key", key)
            items.append(item)
        return items
    return []


def _title_for(section, index):
    return _text(
        section.get("title")
        or section.get("heading")
        or section.get("name")
        or section.get("label")
        or section.get("section_title")
        or section.get("display_name")
        or f"Section {index}"
    )


def _body_for(section):
    return _text(
        section.get("content_html")
        or section.get("html")
        or section.get("body_html")
        or section.get("body")
        or section.get("text")
        or section.get("content")
        or section.get("source_text")
        or section.get("editor_html")
    )


def normalize_contract_sections(content_snapshot):
    snapshot = _coerce_snapshot(content_snapshot)
    normalized = []
    seen_ids = set()
    for index, section in enumerate(_section_items(snapshot.get("sections")), start=1):
        if not isinstance(section, dict):
            continue
        title = _title_for(section, index)
        raw_id = _text(section.get("id") or section.get("section_id") or section.get("key") or section.get("slug"))
        base_id = _slug(raw_id or f"{index}-{title}")
        section_id = base_id
        suffix = 2
        while section_id in seen_ids:
            section_id = f"{base_id}-{suffix}"
            suffix += 1
        seen_ids.add(section_id)
        order = section.get("order") or section.get("number") or section.get("position") or index
        try:
            order = int(order)
        except (TypeError, ValueError):
            order = index
        body = _body_for(section)
        normalized.append({
            "id": section_id,
            "section_id": section_id,
            "title": title,
            "name": title,
            "order": order,
            "number": order,
            "anchor_id": f"contract-section-{section_id}",
            "body": body,
            "text": body,
            "content_html": body,
            "html": body,
            "has_body": bool(body),
            "metadata": {k: v for k, v in section.items() if k not in {"body", "text", "content", "html", "content_html", "body_html", "editor_html"}},
        })
    return normalized
