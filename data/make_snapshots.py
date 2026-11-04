"""Generate small labeled synthetic portfolio snapshots.

Each snapshot carries `expected`: the exception categories a reviewer would
assign, keyed by rule type. Rule ids come from extraction order, so labels use
rule types instead. Run: python data/make_snapshots.py
"""
import copy
import json
from pathlib import Path

OUT = Path(__file__).parent / "portfolios"
AS_OF = "2026-11-02"
SECTORS = {
    "Information Technology": ["AAPL", "MSFT", "NVDA", "ORCL"],
    "Health Care": ["JNJ", "UNH", "PFE", "MRK"],
    "Financials": ["JPM", "BAC", "GS", "MS"],
    "Industrials": ["CAT", "HON", "GE", "UPS"],
    "Consumer Staples": ["PG", "KO", "PEP", "WMT"],
}


def base():
    positions = [
        {"ticker": t, "issuer": t, "sector": s, "quantity": 488, "price": 100.0, "price_date": AS_OF}
        for s, ts in SECTORS.items() for t in ts
    ]
    return {"as_of": AS_OF, "cash": 24000.0, "positions": positions, "expected": {}}


def pos(snap, ticker):
    return next(p for p in snap["positions"] if p["ticker"] == ticker)


def build():
    snaps = {}
    snaps["clean"] = base()

    s = base(); pos(s, "AAPL")["quantity"] = 700
    s["expected"] = {"max_issuer_weight": "POTENTIAL_BREACH"}
    snaps["issuer_breach"] = s

    s = copy.deepcopy(snaps["issuer_breach"]); s["as_of"] = "2026-10-15"
    for p in s["positions"]:
        p["price_date"] = "2026-10-15"
    s["expected"] = {"max_issuer_weight": "PERMITTED_EXCEPTION"}
    snaps["issuer_breach_waived"] = s

    s = base(); p = pos(s, "KO"); p.update(ticker="MO", issuer="MO")
    s["expected"] = {"prohibited_issuers": "POTENTIAL_BREACH"}
    snaps["prohibited_holding"] = s

    s = base(); s["cash"] = 5000.0
    s["expected"] = {"min_cash": "POTENTIAL_BREACH"}
    snaps["low_cash"] = s

    s = base(); pos(s, "GE")["price_date"] = "2026-10-20"
    s["expected"] = {t: "DATA_ISSUE" for t in
                     ("max_issuer_weight", "max_sector_weight", "min_cash", "prohibited_issuers")}
    snaps["stale_price"] = s

    s = base(); pos(s, "PFE")["sector"] = None
    s["expected"] = copy.deepcopy(snaps["stale_price"]["expected"])
    snaps["missing_sector"] = s

    # AAPL exactly 5.00% of NAV (50,000 / 1,000,000): equal to the limit should pass.
    s = base(); pos(s, "AAPL")["quantity"] = 500; s["cash"] = 22800.0
    snaps["threshold_equal"] = s

    return snaps


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for name, snap in build().items():
        (OUT / f"{name}.json").write_text(json.dumps(snap, indent=2))
        print("wrote", OUT / f"{name}.json")
