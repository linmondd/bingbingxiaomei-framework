#!/usr/bin/env python3
"""Validate bingbingxiaomei-framework claim data."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

CLAIM_TYPES = {
    "author_statement",
    "organizer_summary",
    "agent_inference",
    "external_theory",
    "unattributed_claim",
}
SOURCE_STATUS = {
    "primary_verified",
    "primary_indexed",
    "secondary_archived",
    "secondary_reproduced",
    "source_unavailable",
    "deleted_or_locked_possible",
    "unattributed_preserved",
    "conflicting_metadata",
}
EVIDENCE_LEVELS = {"A", "B", "C", "D", "U"}
LEGAL_AUTHOR_WITHOUT_SOURCE = {
    "source_unavailable",
    "deleted_or_locked_possible",
    "conflicting_metadata",
}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        raise ValueError(f"missing file: {path}")
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}:{line_no}: invalid JSON: {exc}") from exc
    if not rows:
        raise ValueError(f"{path.name}: empty data file")
    return rows


def require_date(value: str, field: str, row_id: str) -> None:
    if value == "unknown":
        return
    if not DATE_RE.match(value[:10]):
        raise ValueError(f"{row_id}: {field} must be YYYY-MM-DD or unknown")


def validate_claim(row: dict) -> None:
    required = [
        "id",
        "title",
        "system_layer",
        "topics",
        "claim_type",
        "summary",
        "first_seen",
        "last_seen",
        "source_status",
        "evidence_level",
        "primary_sources",
        "secondary_sources",
        "uncertainties",
        "last_verified",
    ]
    for key in required:
        if key not in row:
            raise ValueError(f"{row.get('id', '<missing id>')}: missing {key}")

    if row["claim_type"] not in CLAIM_TYPES:
        raise ValueError(f"{row['id']}: invalid claim_type {row['claim_type']}")
    if row["source_status"] not in SOURCE_STATUS:
        raise ValueError(f"{row['id']}: invalid source_status {row['source_status']}")
    if row["evidence_level"] not in EVIDENCE_LEVELS:
        raise ValueError(f"{row['id']}: invalid evidence_level {row['evidence_level']}")
    if not isinstance(row["topics"], list) or not row["topics"]:
        raise ValueError(f"{row['id']}: topics must be a non-empty list")
    if not isinstance(row["primary_sources"], list) or not isinstance(row["secondary_sources"], list):
        raise ValueError(f"{row['id']}: sources must be lists")

    require_date(row["first_seen"], "first_seen", row["id"])
    require_date(row["last_seen"], "last_seen", row["id"])
    require_date(row["last_verified"], "last_verified", row["id"])

    sources = row["primary_sources"] + row["secondary_sources"]
    if row["claim_type"] == "author_statement" and not sources:
        if row["source_status"] not in LEGAL_AUTHOR_WITHOUT_SOURCE:
            raise ValueError(f"{row['id']}: author_statement lacks source or legal unavailable status")

    if row["source_status"] == "primary_verified":
        if not row["primary_sources"]:
            raise ValueError(f"{row['id']}: primary_verified needs primary_sources")
        for source in row["primary_sources"]:
            for field in ["url", "title", "published_at", "accessed_at"]:
                if not source.get(field):
                    raise ValueError(f"{row['id']}: primary source missing {field}")

    if row["source_status"] == "unattributed_preserved":
        if row["evidence_level"] != "U":
            raise ValueError(f"{row['id']}: unattributed_preserved must be U")
        if row["primary_sources"]:
            raise ValueError(f"{row['id']}: unattributed_preserved cannot have primary_sources")
        if "我在" in row["summary"] or "原话" in row["summary"]:
            raise ValueError(f"{row['id']}: unattributed summary must not masquerade as author wording")

    if row["source_status"] == "primary_indexed":
        if row["evidence_level"] != "B":
            raise ValueError(f"{row['id']}: primary_indexed claims must stay B level")
        uncertainty_text = " ".join(row.get("uncertainties", []))
        if not any(marker in uncertainty_text for marker in ["全文未稳定打开", "搜索索引", "索引片段"]):
            raise ValueError(f"{row['id']}: primary_indexed claims must disclose context gap")
        if "原帖明确写过" in row.get("summary", ""):
            raise ValueError(f"{row['id']}: primary_indexed summary overstates source certainty")


def main() -> int:
    try:
        claims = load_jsonl(DATA / "claims.jsonl")
        load_jsonl(DATA / "sources.jsonl")
        load_jsonl(DATA / "unresolved-sources.jsonl")
        for claim in claims:
            validate_claim(claim)
    except ValueError as exc:
        print(f"claims_invalid: {exc}", file=sys.stderr)
        return 1

    levels = Counter(row["evidence_level"] for row in claims)
    statuses = Counter(row["source_status"] for row in claims)
    print(
        json.dumps(
            {
                "status": "claims_valid",
                "total_claims": len(claims),
                "evidence_levels": dict(sorted(levels.items())),
                "source_statuses": dict(sorted(statuses.items())),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
