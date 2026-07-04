#!/usr/bin/env python3
"""Query claim evidence for bingbingxiaomei-framework."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def load_claims() -> list[dict]:
    rows: list[dict] = []
    for line in (DATA / "claims.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def searchable(row: dict) -> str:
    parts = [
        row.get("title", ""),
        row.get("summary", ""),
        row.get("system_layer", ""),
        row.get("quote_excerpt", ""),
        " ".join(row.get("topics", [])),
    ]
    return " ".join(parts).lower()


def compact(row: dict) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "system_layer": row["system_layer"],
        "claim_type": row["claim_type"],
        "summary": row["summary"],
        "first_seen": row["first_seen"],
        "last_seen": row["last_seen"],
        "source_status": row["source_status"],
        "evidence_level": row["evidence_level"],
        "primary_sources": row.get("primary_sources", []),
        "secondary_sources": row.get("secondary_sources", []),
        "uncertainties": row.get("uncertainties", []),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("keyword", nargs="?", help="Keyword or topic to search")
    parser.add_argument("--level", choices=["A", "B", "C", "D", "U"], help="Filter by evidence level")
    parser.add_argument("--status", help="Filter by source_status")
    parser.add_argument("--layer", help="Filter by system_layer")
    parser.add_argument("--json", action="store_true", help="Emit JSON array")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    claims = load_claims()
    keyword = args.keyword.lower() if args.keyword else ""
    results = []
    for row in claims:
        if keyword and keyword not in searchable(row):
            continue
        if args.level and row["evidence_level"] != args.level:
            continue
        if args.status and row["source_status"] != args.status:
            continue
        if args.layer and row["system_layer"] != args.layer:
            continue
        results.append(compact(row))

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for row in results:
            print(f"{row['id']} | {row['evidence_level']} | {row['source_status']} | {row['title']}")
            print(f"  {row['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
