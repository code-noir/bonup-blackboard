from .candidates import build_prepared_term_candidates, build_sentence_candidates


def build_prepare_shadow_candidates(contract, version, run, prepared_terms, draft_text=""):
    sentence_candidates = build_sentence_candidates(contract, version, run, prepared_terms, draft_text)
    if sentence_candidates:
        return sentence_candidates
    return build_prepared_term_candidates(contract, version, run, prepared_terms)
