import copy
import json
import re
from html import escape


REPLACE_ACTIONS = {"replace_clause", "replace_section", "modify_section"}
ADD_ACTIONS = {"add_clause", "add_obligation", "clarify_clause"}


def apply_request_to_snapshot(current_snapshot, request, accepted_text=None):
    snapshot = _snapshot_dict(current_snapshot)
    text = accepted_text if accepted_text is not None else getattr(request, "proposed_text", "")
    text = str(text or "").strip()
    action_type = getattr(request, "action_type", "") or ""
    sections = snapshot.get("sections")
    if not isinstance(sections, list):
        sections = []
        snapshot["sections"] = sections

    section, matched_by = _find_section(sections, request)
    original_body = _section_body_value(section) if section else ""
    has_full_body = bool(_full_contract_body(snapshot))
    section_has_body = bool(original_body.strip())
    can_update_section = bool(section and (section_has_body or not has_full_body))

    if can_update_section and action_type in REPLACE_ACTIONS:
        _set_section_body(section, _html_from_text(text))
        fallback_used = False
        application_status = "section_replaced"
    elif can_update_section and action_type in ADD_ACTIONS:
        _append_section_body(section, text)
        fallback_used = False
        application_status = "section_appended"
    else:
        _append_fallback_section(snapshot, request, text)
        if not can_update_section:
            matched_by = None
        fallback_used = True
        application_status = "fallback_appended"

    if not fallback_used:
        _sync_editor_html(snapshot, sections, original_body, _section_body_value(section))

    metadata = {
        "source": "agreement_exchange",
        "request_id": str(getattr(request, "id", "")),
        "target_section_id": getattr(request, "target_section_id", None),
        "target_section_title": getattr(request, "target_section_title", ""),
        "request_category": getattr(request, "request_category", ""),
        "action_type": action_type,
        "proposed_text": text,
        "matched_by": matched_by,
        "fallback_used": fallback_used,
        "application_status": application_status,
    }
    updates = snapshot.get("agreement_exchange_updates")
    if not isinstance(updates, list):
        updates = []
    snapshot["agreement_exchange_updates"] = [*updates, metadata]
    snapshot["agreement_exchange_latest_update"] = metadata
    return snapshot


def _snapshot_dict(value):
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {"content_html": value, "sections": []}
        if isinstance(parsed, dict):
            return copy.deepcopy(parsed)
    return {"content_html": str(value or ""), "sections": []}


def _find_section(sections, request):
    target_id = str(getattr(request, "target_section_id", "") or "").strip()
    if target_id:
        for section in sections:
            if not isinstance(section, dict):
                continue
            section_ids = [
                section.get("id"),
                section.get("section_id"),
                section.get("uuid"),
                section.get("key"),
            ]
            if any(str(value or "").strip() == target_id for value in section_ids):
                return section, "id"

    target_title = _normalize_title(getattr(request, "target_section_title", ""))
    if target_title:
        for section in sections:
            if not isinstance(section, dict):
                continue
            section_titles = [
                section.get("name"),
                section.get("title"),
                section.get("heading"),
                section.get("label"),
            ]
            if any(_normalize_title(value) == target_title for value in section_titles):
                return section, "title"
    return None, None


def _normalize_title(value):
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _section_body_key(section):
    for key in ("content_html", "html", "body", "text"):
        if key in section:
            return key
    return "content_html"


def _section_body_value(section):
    if not isinstance(section, dict):
        return ""
    return str(section.get(_section_body_key(section)) or "")


def _set_section_body(section, html):
    section[_section_body_key(section)] = html


def _append_section_body(section, text):
    key = _section_body_key(section)
    current = str(section.get(key) or "")
    addition = _html_from_text(text) if key in {"content_html", "html", "body"} or current.lstrip().startswith("<") else text
    if not current:
        section[key] = addition
    elif key == "text" and not current.lstrip().startswith("<"):
        section[key] = f"{current.rstrip()}\n\n{text}"
    else:
        section[key] = f"{current}{addition}"


def _full_contract_body(snapshot):
    for key in ("editor_html", "final_editor_html", "content_html", "html", "body", "text"):
        value = snapshot.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _append_fallback_section(snapshot, request, text):
    sections = snapshot.setdefault("sections", [])
    if not isinstance(sections, list):
        sections = []
        snapshot["sections"] = sections
    content = (
        f'<p><strong>Target section:</strong> {escape(getattr(request, "target_section_title", "") or "General")}</p>'
        f'<p><strong>Action:</strong> {escape((getattr(request, "action_type", "") or "").replace("_", " "))}</p>'
        f"{_html_from_text(text)}"
    )
    sections.append({
        "id": f"agreement-exchange-updates-{getattr(request, 'id', '')}",
        "number": len(sections) + 1,
        "name": "Agreement Exchange Updates",
        "content_html": content,
        "agreement_exchange_fallback": True,
        "source_request_id": str(getattr(request, "id", "")),
    })
    base_html = _full_contract_body(snapshot)
    if base_html and not str(base_html).lstrip().startswith("<"):
        base_html = _html_from_text(base_html)
    fallback_html = (
        '<section data-agreement-exchange-fallback="true" '
        f'data-request-id="{escape(str(getattr(request, "id", "")))}">'
        "<h2>Agreement Exchange Updates</h2>"
        f"{content}"
        "</section>"
    )
    snapshot["editor_html"] = f"{base_html}{fallback_html}"


def _render_editor_html_from_sections(sections):
    html = []
    has_body = False
    for section in sections:
        if not isinstance(section, dict):
            continue
        title = section.get("name") or section.get("title") or section.get("heading") or "Section"
        body = section.get("content_html") or section.get("html") or section.get("body") or section.get("text") or ""
        if str(body).strip():
            has_body = True
        if body and not str(body).lstrip().startswith("<"):
            body = _html_from_text(body)
        html.append(f"<h2>{escape(str(title))}</h2>{body}")
    return "".join(html) if has_body else ""


def _sections_have_body_for_full_render(sections):
    body_sections = [section for section in sections if isinstance(section, dict) and not section.get("agreement_exchange_fallback")]
    return bool(body_sections) and all(_section_body_value(section).strip() for section in body_sections)


def _sync_editor_html(snapshot, sections, original_body, updated_body):
    base_html = _full_contract_body(snapshot)
    should_render_from_sections = _sections_have_body_for_full_render(sections) or not base_html
    rendered = _render_editor_html_from_sections(sections) if should_render_from_sections else ""
    if rendered:
        snapshot["editor_html"] = rendered
        return

    if original_body and original_body in str(base_html):
        snapshot["editor_html"] = str(base_html).replace(original_body, updated_body, 1)
    else:
        snapshot["editor_html"] = str(base_html)


def _html_from_text(value):
    lines = [line.strip() for line in str(value or "").splitlines()]
    blocks = []
    current = []
    for line in lines:
        if line:
            current.append(line)
        elif current:
            blocks.append(" ".join(current))
            current = []
    if current:
        blocks.append(" ".join(current))
    if not blocks and value:
        blocks = [str(value)]
    return "".join(f"<p>{escape(block)}</p>" for block in blocks)
