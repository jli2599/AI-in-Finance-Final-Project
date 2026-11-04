"""IPS monitoring MVP command line.

  python main.py extract data/ips/sample_ips_a.txt
  python main.py approve output/candidate_rules.json --by "Compliance Officer" --version 1
  python main.py check output/approved_rules_v1.json data/portfolios/issuer_breach.json
  python main.py demo        # whole pipeline over every snapshot + label accuracy
"""
import argparse
import json
import sys
from pathlib import Path

from ips_monitor import approve as approve_mod
from ips_monitor import audit, checks, extract, triage

OUT = Path("output")
AUDIT = OUT / "audit_log.jsonl"
WAIVERS = Path("data/waivers/waivers.json")


def load(p):
    return json.loads(Path(p).read_text())


def save(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, indent=2))


def cmd_extract(ips_path, out=OUT / "candidate_rules.json"):
    text = Path(ips_path).read_text()
    cands = extract.extract_rules(text, source_doc=str(ips_path))
    unsupported = extract.verify_citations(cands, text)
    if unsupported:
        sys.exit(f"Unsupported citations, refusing to continue: {unsupported}")
    save(out, cands)
    audit.log(AUDIT, "extract", source=str(ips_path), n_rules=len(cands), extractor="regex_baseline")
    print(f"{len(cands)} candidate rules -> {out}")
    for c in cands:
        print(f"  {c['id']} {c['type']:<20} {c['value']!s:<20} (clause {c['clause_ref']})")
    return cands


def cmd_approve(cand_path, by, version, effective_date="2026-01-01"):
    rule_set = approve_mod.approve(load(cand_path), by, effective_date, version)
    out = OUT / f"approved_rules_v{version}.json"
    save(out, rule_set)
    audit.log(AUDIT, "approve", version=version, approved_by=by, n_rules=len(rule_set["rules"]))
    print(f"Rule set v{version} approved by {by} -> {out}")
    return rule_set


def cmd_check(rule_set, snapshot, name, waivers, verbose=True):
    nav, results = checks.run_checks(rule_set, snapshot)
    alerts = []
    for r in results:
        cat = triage.triage(r, waivers, snapshot["as_of"])
        if cat:
            alerts.append({"rule_id": r["rule_id"], "type": r["type"], "category": cat,
                           "summary": triage.case_summary(r, cat, rule_set, name)})
    audit.log(AUDIT, "check", snapshot=name, snapshot_hash=audit.snapshot_hash(snapshot),
              rule_version=rule_set["version"], nav=round(nav, 2),
              results=[{k: r[k] for k in ("rule_id", "status", "offenders")} for r in results],
              alerts=[{k: a[k] for k in ("rule_id", "category")} for a in alerts],
              disposition="PENDING")
    if verbose:
        print(f"\n== {name}  (NAV {nav:,.0f}, rules v{rule_set['version']})")
        for r in results:
            print(f"  {r['rule_id']} {r['type']:<20} {r['status']}")
        for a in alerts:
            print("  --- case ---\n  " + a["summary"].replace("\n", "\n  "))
    return alerts


def cmd_demo():
    cmd_extract("data/ips/sample_ips_a.txt")
    rule_set = cmd_approve(OUT / "candidate_rules.json", by="Demo Compliance Officer", version=1)
    waivers = load(WAIVERS)
    correct = total = 0
    for snap_path in sorted(Path("data/portfolios").glob("*.json")):
        snap = load(snap_path)
        alerts = cmd_check(rule_set, snap, snap_path.stem, waivers)
        got = {a["type"]: a["category"] for a in alerts}
        exp = snap.get("expected", {})
        for t in {r["type"] for r in rule_set["rules"]}:
            total += 1
            correct += got.get(t) == exp.get(t)
        print(f"  expected={exp or 'no alerts'}  {'OK' if got == exp else 'MISMATCH'}")
    print(f"\nRule-level category accuracy: {correct}/{total}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract"); e.add_argument("ips")
    a = sub.add_parser("approve"); a.add_argument("candidates"); a.add_argument("--by", required=True)
    a.add_argument("--version", type=int, required=True)
    c = sub.add_parser("check"); c.add_argument("rules"); c.add_argument("snapshot")
    sub.add_parser("demo")
    args = ap.parse_args()
    if args.cmd == "extract":
        cmd_extract(args.ips)
    elif args.cmd == "approve":
        cmd_approve(args.candidates, args.by, args.version)
    elif args.cmd == "check":
        cmd_check(load(args.rules), load(args.snapshot), Path(args.snapshot).stem, load(WAIVERS))
    else:
        cmd_demo()


if __name__ == "__main__":
    main()
