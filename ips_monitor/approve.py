"""Human approval step: candidate rules -> versioned, approved rule set."""
from datetime import datetime, timezone


def approve(candidates, approver, effective_date, version):
    if not approver:
        raise ValueError("An approver name is required; rules cannot self-activate.")
    return {
        "version": version,
        "effective_date": effective_date,
        "approved_by": approver,
        "approved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rules": candidates,
    }
