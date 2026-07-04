#!/usr/bin/env python3
"""Audit coverage for bingbingxiaomei-framework seed data."""

from __future__ import annotations

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BOUNDARY = "本 Skill 只能说明已覆盖的公开网页、搜索索引、用户侧整理材料和第三方整理；不能声称绝对完整。删帖、锁帖、评论、图片、直播和未索引内容仍可能存在。"


def load_claims() -> list[dict]:
    return [json.loads(line) for line in (DATA / "claims.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


def audit() -> dict:
    claims = load_claims()
    return {
        "total_claims": len(claims),
        "evidence_levels": dict(sorted(Counter(row["evidence_level"] for row in claims).items())),
        "source_statuses": dict(sorted(Counter(row["source_status"] for row in claims).items())),
        "system_layers": dict(sorted(Counter(row["system_layer"] for row in claims).items())),
        "claim_types": dict(sorted(Counter(row["claim_type"] for row in claims).items())),
        "with_primary_sources": sum(1 for row in claims if row.get("primary_sources")),
        "with_secondary_sources": sum(1 for row in claims if row.get("secondary_sources")),
        "unresolved_or_u": sum(1 for row in claims if row["evidence_level"] == "U"),
        "coverage_boundary": BOUNDARY,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON object")
    args = parser.parse_args()
    report = audit()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"total_claims: {report['total_claims']}")
        print(f"evidence_levels: {report['evidence_levels']}")
        print(f"source_statuses: {report['source_statuses']}")
        print(f"system_layers: {report['system_layers']}")
        print(report["coverage_boundary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
