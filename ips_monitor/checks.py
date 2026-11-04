"""Deterministic checks. Missing or stale data is an exception, never a pass."""
from collections import defaultdict
from datetime import date

STALE_DAYS = 3
TOL = 1e-9  # weight exactly at the limit passes


def data_quality(snapshot):
    issues = []
    as_of = date.fromisoformat(snapshot["as_of"])
    for p in snapshot["positions"]:
        for field in ("ticker", "issuer", "sector", "quantity", "price", "price_date"):
            if p.get(field) in (None, ""):
                issues.append(f"{p.get('ticker', '?')}: missing {field}")
        if p.get("price_date"):
            age = (as_of - date.fromisoformat(p["price_date"])).days
            if age > STALE_DAYS:
                issues.append(f"{p['ticker']}: price is {age} days old")
    if snapshot.get("cash") is None:
        issues.append("portfolio: missing cash balance")
    return issues


def weights(snapshot):
    mv = {p["ticker"]: p["quantity"] * p["price"] for p in snapshot["positions"]
          if p.get("quantity") is not None and p.get("price") is not None}
    nav = sum(mv.values()) + (snapshot.get("cash") or 0)
    by_issuer, by_sector = defaultdict(float), defaultdict(float)
    for p in snapshot["positions"]:
        if p["ticker"] in mv:
            by_issuer[p.get("issuer") or p["ticker"]] += mv[p["ticker"]] / nav
            by_sector[p.get("sector") or "UNKNOWN"] += mv[p["ticker"]] / nav
    return nav, by_issuer, by_sector, (snapshot.get("cash") or 0) / nav


def run_checks(rule_set, snapshot):
    """Return one result per rule: PASS, FAIL, or DATA_ISSUE."""
    dq = data_quality(snapshot)
    nav, by_issuer, by_sector, cash_w = weights(snapshot)
    tickers = {p["ticker"] for p in snapshot["positions"]}
    results = []
    for r in rule_set["rules"]:
        t, v = r["type"], r["value"]
        if t == "max_issuer_weight":
            bad = {k: w for k, w in by_issuer.items() if w > v + TOL}
        elif t == "max_sector_weight":
            bad = {k: w for k, w in by_sector.items() if w > v + TOL}
        elif t == "min_cash":
            bad = {"cash": cash_w} if cash_w < v - TOL else {}
        elif t == "prohibited_issuers":
            bad = {k: by_issuer.get(k, 0.0) for k in tickers & set(v)}
        else:
            raise ValueError(f"Unknown rule type {t}")
        status = "FAIL" if bad else ("DATA_ISSUE" if dq else "PASS")
        results.append({"rule_id": r["id"], "type": t, "limit": v, "status": status,
                        "offenders": {k: round(w, 4) for k, w in bad.items()},
                        "data_issues": dq, "clause_ref": r.get("clause_ref")})
    return nav, results
