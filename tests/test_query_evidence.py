import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class QueryEvidenceTests(unittest.TestCase):
    def run_query(self, *args):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "query_evidence.py"), *args, "--json"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_queries_core_nodes(self):
        for keyword in ["三要素", "中央加杠杆", "AI", "猪周期"]:
            with self.subTest(keyword=keyword):
                rows = self.run_query(keyword)
                self.assertGreaterEqual(len(rows), 1)
                for row in rows:
                    self.assertIn("id", row)
                    self.assertIn("title", row)
                    self.assertIn("evidence_level", row)
                    self.assertIn("source_status", row)

    def test_level_filter_returns_u_records_only(self):
        rows = self.run_query("--level", "U")
        self.assertGreaterEqual(len(rows), 1)
        self.assertTrue(all(row["evidence_level"] == "U" for row in rows))

    def test_short_keyword_does_not_match_internal_claim_prefix(self):
        rows = self.run_query("AI")
        ids = {row["id"] for row in rows}
        self.assertIn("claim-ai-dollar-strategy", ids)
        self.assertIn("claim-ai-finance-bound", ids)
        self.assertNotIn("claim-identity-homepage", ids)
        self.assertLess(len(rows), 8)


if __name__ == "__main__":
    unittest.main()
