import re
from html import unescape


def normalize_source(text):
    text = unescape(text or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(div|p|h[1-6]|li|tr|section)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\r?\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def prepared_source_text(prepared_terms, draft_text):
    if draft_text:
        return draft_text
    descriptions = []
    for key in ("payment_terms", "service_obligations", "milestones"):
        for term in prepared_terms.get(key) or []:
            if isinstance(term, dict) and term.get("description"):
                descriptions.append(str(term["description"]))
    return "\n".join(descriptions)


def split_sentences(source_text):
    normalized = normalize_source(source_text)
    normalized = re.sub(r"\n{2,}", "\n", normalized)
    parts = re.split(r"(?<=[.!?])\s+|\n+", normalized)
    return [part.strip() for part in parts if len(part.strip()) > 8]
