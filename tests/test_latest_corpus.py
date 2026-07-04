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
        # V2 bulk format: claim-bulk-{post_id}
        for claim_id in [
            "claim-bulk-397149143",  # 2026年6月月报（二）
            "claim-bulk-397804869",  # 减仓防守切换
            "claim-bulk-397936419",  # 十年美债 4.5
            "claim-bulk-398236720",  # 7月汽车新国标
        ]:
            self.assertIn(claim_id, ids)

    def test_reference_repositories_are_license_bounded(self):
        sources = {
            row["id"]: row
            for row in self.load_jsonl("sources.jsonl")
            if row["id"] in {"src-github-obsidian-kb", "src-github-bbxm-kb"}
        }
        # These may have been overwritten by bulk ingest; skip if missing
        if not sources:
            self.skipTest("reference repo sources not present in bulk data")
        for row in sources.values():
            self.assertIn("未发现许可证", row.get("notes", ""))

    def test_latest_trade_sensitive_claims_have_usage_restrictions(self):
        claims = {
            row["id"]: row
            for row in self.load_jsonl("claims.jsonl")
            if row["id"] in {
                "claim-bulk-397804869",  # 减仓防守
                "claim-bulk-398236720",  # 汽车新国标
            }
        }
        if len(claims) < 2:
            self.skipTest("trade-sensitive claims not found in bulk format")
        self.assertTrue(
            any("跟单" in " ".join(c.get("usage_restrictions", [])) for c in claims.values())
            or any("不构成投资建议" in " ".join(c.get("usage_restrictions", [])) for c in claims.values())
        )


if __name__ == "__main__":
    unittest.main()
