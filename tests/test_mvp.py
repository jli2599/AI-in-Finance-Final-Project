import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data"))

from ips_monitor import checks, extract  # noqa: E402
import make_snapshots  # noqa: E402

RULES = {"version": 1, "rules": extract.extract_rules(
    (ROOT / "data/ips/sample_ips_a.txt").read_text(), "sample_ips_a.txt")}


def statuses(snap):
    return {r["type"]: r["status"] for r in checks.run_checks(RULES, snap)[1]}


class TestMVP(unittest.TestCase):
    def setUp(self):
        self.snaps = make_snapshots.build()

    def test_extracts_four_rules_with_citations(self):
        types = {r["type"]: r["value"] for r in RULES["rules"]}
        self.assertEqual(types["max_issuer_weight"], 0.05)
        self.assertEqual(types["max_sector_weight"], 0.25)
        self.assertEqual(types["min_cash"], 0.02)
        self.assertEqual(types["prohibited_issuers"], ["MO", "PM", "BTI"])
        self.assertTrue(all(r["clause_ref"] for r in RULES["rules"]))

    def test_clean_passes(self):
        self.assertEqual(set(statuses(self.snaps["clean"]).values()), {"PASS"})

    def test_threshold_equal_passes(self):
        self.assertEqual(statuses(self.snaps["threshold_equal"])["max_issuer_weight"], "PASS")

    def test_breaches_fail(self):
        self.assertEqual(statuses(self.snaps["issuer_breach"])["max_issuer_weight"], "FAIL")
        self.assertEqual(statuses(self.snaps["low_cash"])["min_cash"], "FAIL")
        self.assertEqual(statuses(self.snaps["prohibited_holding"])["prohibited_issuers"], "FAIL")

    def test_bad_data_never_passes(self):
        for name in ("stale_price", "missing_sector"):
            self.assertNotIn("PASS", statuses(self.snaps[name]).values(), name)


if __name__ == "__main__":
    unittest.main()
