# AI-in-Finance-Final-Project

MVP for IPS (Investment Policy Statement) monitoring and exception triage
(MGT 8803, Asset Management track). Plain Python 3.10+ with no dependencies.

## Pipeline

```
IPS text -> extract candidate rules (+ clause citations) -> citation check
         -> human approval (versioned rule set)
portfolio snapshot -> data-quality checks -> deterministic limit checks
         -> rules-first triage -> case summary -> audit log (disposition PENDING)
```

| Module | Role |
|---|---|
| `ips_monitor/extract.py` | Regex baseline extractor; every rule cites its clause |
| `ips_monitor/approve.py` | Human approval → versioned rule set |
| `ips_monitor/checks.py` | NAV weights, 4 rule types; stale/missing data is never a pass |
| `ips_monitor/triage.py` | DATA_ISSUE / PERMITTED_EXCEPTION / POTENTIAL_BREACH + summary |
| `ips_monitor/audit.py` | Append-only JSONL audit log |

Rule types: `max_issuer_weight`, `max_sector_weight`, `min_cash`, `prohibited_issuers`.

## Run

```bash
python data/make_snapshots.py   # (re)generate labeled synthetic snapshots
python main.py demo             # full pipeline + category accuracy vs labels
python -m unittest discover tests
```

Step by step:

```bash
python main.py extract data/ips/sample_ips_a.txt
python main.py approve output/candidate_rules.json --by "Compliance Officer" --version 1
python main.py check output/approved_rules_v1.json data/portfolios/issuer_breach.json
```

## Next steps (not in MVP)

- LLM extractor with the same output schema, compared against the regex baseline
- LLM category suggestion for alerts the rules can't sort, plus richer case summaries
- More IPS documents (synthetic + public, e.g. LACERS) and 50–100 labeled snapshots
- Prompt-injection and conflicting-amendment tests
