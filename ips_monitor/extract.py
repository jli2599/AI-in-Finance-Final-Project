"""Policy text -> candidate rules (regex baseline).

Each candidate cites the exact clause it came from. Candidates are NOT active
until a person approves them (see approve.py). An LLM extractor can later be
added behind the same output schema and compared against this baseline.
"""
import re

PCT = r"(\d+(?:\.\d+)?)\s*%"

PATTERNS = [
    ("max_issuer_weight", re.compile(r"single issuer[^.]*?exceed\s+" + PCT, re.I)),
    ("max_sector_weight", re.compile(r"sector[^.]*?(?:exceed|more than)\s+" + PCT, re.I)),
    ("min_cash", re.compile(r"(?:minimum cash|cash[^.]*?at least)[^.]*?" + PCT, re.I)),
]
PROHIBITED = re.compile(r"shall not hold securities of the following issuers:\s*([A-Z0-9 ,.]+)", re.I)


def _sentences(text):
    # Split into sentence-level clauses, keeping the clause number if present.
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\d+(?:\.\d+)*)\s+(.*)$", line)
        ref, body = (m.group(1), m.group(2)) if m else (None, line)
        yield ref, body


def extract_rules(text, source_doc):
    candidates = []
    for ref, clause in _sentences(text):
        for rule_type, pat in PATTERNS:
            m = pat.search(clause)
            if m:
                candidates.append({
                    "type": rule_type,
                    "value": float(m.group(1)) / 100,
                    "clause_ref": ref,
                    "clause_text": clause,
                    "source_doc": source_doc,
                    "extractor": "regex_baseline",
                })
        m = PROHIBITED.search(clause)
        if m:
            tickers = [t.strip(" .").upper() for t in m.group(1).split(",") if t.strip(" .")]
            candidates.append({
                "type": "prohibited_issuers",
                "value": tickers,
                "clause_ref": ref,
                "clause_text": clause,
                "source_doc": source_doc,
                "extractor": "regex_baseline",
            })
    for i, c in enumerate(candidates, 1):
        c["id"] = f"R{i}"
    return candidates


def verify_citations(candidates, text):
    """Every candidate's clause must appear verbatim in the source text."""
    return [c for c in candidates if c["clause_text"] not in text]
