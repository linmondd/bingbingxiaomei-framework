import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


class LatestCorpusTests(unittest.TestCase):
    def load_jsonl(self, name):
        return [
            json.loads(line)
            for line in (DATA / name).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_latest_refresh_is_recorded(self):
        sources = self.load_jsonl("sources.jsonl")
        self.assertTrue(
            any(row.get("accessed_at") == "2026-07-04" for row in sources),
            "latest corpus refresh should include 2026-07-04 source checks",
        )

    def test_new_xueqiu_indexed_posts_are_queryable(self):
        claims = self.load_jsonl("claims.jsonl")
        ids = {row["id"] for row in claims}
        for claim_id in [
            "claim-2026-june-margin-crowding",
            "claim-2026-defensive-deleveraging",
            "claim-2026-us10y-risk-line",
            "claim-2026-auto-standard-rotation",
        ]:
            self.assertIn(claim_id, ids)

    def test_reference_repositories_are_license_bounded(self):
        sources = {
            row["id"]: row
            for row in self.load_jsonl("sources.jsonl")
            if row["id"] in {"src-github-obsidian-kb", "src-github-bbxm-kb"}
        }
        self.assertEqual(set(sources), {"src-github-obsidian-kb", "src-github-bbxm-kb"})
        for row in sources.values():
            self.assertIn("未发现许可证", row.get("notes", ""))
            self.assertIn("只作来源发现", row.get("notes", ""))

    def test_latest_trade_sensitive_claims_have_usage_restrictions(self):
        claims = {
            row["id"]: row
            for row in self.load_jsonl("claims.jsonl")
            if row["id"] in {
                "claim-2026-defensive-deleveraging",
                "claim-2026-auto-standard-rotation",
            }
        }
        self.assertIn("不得作为跟单依据", " ".join(claims["claim-2026-defensive-deleveraging"]["usage_restrictions"]))
        auto_restrictions = " ".join(claims["claim-2026-auto-standard-rotation"]["usage_restrictions"])
        for phrase in ["不得解读为买入", "目标价", "收益预期", "重新核验"]:
            self.assertIn(phrase, auto_restrictions)


if __name__ == "__main__":
    unittest.main()
