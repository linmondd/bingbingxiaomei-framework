import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AuditCoverageTests(unittest.TestCase):
    def test_audit_reports_counts_and_boundary(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "audit_coverage.py"), "--json"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertGreaterEqual(report["total_claims"], 12)
        self.assertIn("A", report["evidence_levels"])
        self.assertIn("U", report["evidence_levels"])
        self.assertIn("trading-system", report["system_layers"])
        self.assertIn("macro-worldview", report["system_layers"])
        self.assertIn("不能声称绝对完整", report["coverage_boundary"])


if __name__ == "__main__":
    unittest.main()
