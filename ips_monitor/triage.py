"""Rules-first exception triage and a template case summary.

Categories: DATA_ISSUE, PERMITTED_EXCEPTION, POTENTIAL_BREACH.
An LLM may later suggest categories for alerts the rules can't sort, and draft
richer summaries, but a person always confirms the disposition.
"""
from datetime import date


def triage(result, waivers, as_of):
    if result["status"] == "PASS":
        return None
    if result["data_issues"]:
        # Can't trust a FAIL (or a pass) computed on bad data: send to operations.
        return "DATA_ISSUE"
    d = date.fromisoformat(as_of)
    for w in waivers:
        if (w["rule_id"] == result["rule_id"]
                and set(result["offenders"]) <= set(w["applies_to"])
                and date.fromisoformat(w["valid_from"]) <= d <= date.fromisoformat(w["valid_to"])):
            return "PERMITTED_EXCEPTION"
    return "POTENTIAL_BREACH"


def case_summary(result, category, rule_set, snapshot_name):
    offenders = ", ".join(f"{k} {w:.2%}" for k, w in result["offenders"].items()) or "n/a"
    lines = [
        f"Alert: rule {result['rule_id']} ({result['type']}, limit {result['limit']}) "
        f"from clause {result['clause_ref']} of rule set v{rule_set['version']}.",
        f"Snapshot: {snapshot_name}. Offenders: {offenders}.",
        f"Suggested category: {category}.",
    ]
    if result["data_issues"]:
        lines.append("Data issues: " + "; ".join(result["data_issues"]))
    lines.append("Disposition: PENDING human review (compliance officer).")
    return "\n".join(lines)
