import json
import subprocess
import sys
import unittest
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


class DataValidationTests(unittest.TestCase):
    def load_jsonl(self, name):
        path = DATA / name
        self.assertTrue(path.exists(), f"{name} should exist")
        rows = []
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                self.fail(f"{name}:{line_no} is invalid JSON: {exc}")
        self.assertGreater(len(rows), 0, f"{name} should not be empty")
        return rows

    def test_validate_claims_script_accepts_seed_data(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_claims.py")],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("claims_valid", result.stdout)

    def test_author_statements_have_sources_or_legal_unavailable_status(self):
        legal_unavailable = {
            "source_unavailable",
            "deleted_or_locked_possible",
            "conflicting_metadata",
        }
        for row in self.load_jsonl("claims.jsonl"):
            if row["claim_type"] != "author_statement":
                continue
            sources = row.get("primary_sources") or row.get("secondary_sources") or []
            has_source = bool(sources)
            self.assertTrue(
                has_source or row.get("source_status") in legal_unavailable,
                f"{row['id']} needs a source or a legal unavailable status",
            )

    def test_unattributed_preserved_does_not_forge_primary_source(self):
        for row in self.load_jsonl("claims.jsonl"):
            if row.get("source_status") == "unattributed_preserved":
                self.assertEqual(row.get("evidence_level"), "U")
                self.assertEqual(row.get("primary_sources"), [])
                self.assertNotIn("我在", row.get("summary", ""))

    def test_dates_are_absolute_or_unknown(self):
        for row in self.load_jsonl("claims.jsonl"):
            for field in ["first_seen", "last_seen", "last_verified"]:
                value = row.get(field)
                self.assertIsNotNone(value, f"{row['id']} missing {field}")
                if value == "unknown":
                    continue
                datetime.strptime(value[:10], "%Y-%m-%d")

    def test_primary_indexed_claims_stay_b_level_and_disclose_context_gap(self):
        for row in self.load_jsonl("claims.jsonl"):
            if row.get("source_status") != "primary_indexed":
                continue
            self.assertEqual(row.get("evidence_level"), "B", row["id"])
            uncertainty_text = " ".join(row.get("uncertainties", []))
            self.assertRegex(uncertainty_text, "全文未稳定打开|搜索索引|索引片段")
            self.assertNotIn("原帖明确写过", row.get("summary", ""))
            self.assertTrue(row.get("usage_restrictions"), row["id"])


if __name__ == "__main__":
    unittest.main()
