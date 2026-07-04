#!/usr/bin/env python3
"""Query claim evidence + full-text search for bingbingxiaomei-framework.

Default mode: search claims.jsonl (structured summaries).
Full-text mode (--fulltext): search bulk_posts.jsonl (original post content).

Examples:
    python3 scripts/query_evidence.py "AI" --json
    python3 scripts/query_evidence.py "流动性 三层" --level A
    python3 scripts/query_evidence.py "中央加杠杆" --fulltext --context 200
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BULK_FILE = DATA / "bulk_posts.jsonl"


def load_claims() -> list[dict]:
    rows: list[dict] = []
    for line in (DATA / "claims.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_posts() -> dict[str, dict]:
    """Load bulk posts into a post_id → post dict (lazy, only if --fulltext)."""
    posts: dict[str, dict] = {}
    if not BULK_FILE.exists():
        return posts
    for line in BULK_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        p = json.loads(line)
        posts[p["post_id"]] = p
    return posts


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


def fulltext_search(keyword: str, context_chars: int = 200) -> list[dict]:
    """Search full text in bulk_posts.jsonl. Returns matched excerpts with context."""
    posts = load_posts()
    results = []
    kw = keyword.lower()
    for pid, post in posts.items():
        text = post.get("text", "")
        idx = text.lower().find(kw)
        if idx < 0:
            continue
        # Extract context window
        start = max(0, idx - context_chars)
        end = min(len(text), idx + len(kw) + context_chars)
        excerpt = text[start:end]
        if start > 0:
            excerpt = "…" + excerpt
        if end < len(text):
            excerpt = excerpt + "…"

        results.append({
            "post_id": pid,
            "title": (post.get("title") or text[:40]).strip()[:60],
            "time_before": post.get("time_before", ""),
            "text_length": len(text),
            "excerpt": excerpt,
            "url": f"https://xueqiu.com/7143769715/{pid}",
        })

    results.sort(key=lambda r: -r["text_length"])
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("keyword", nargs="?", help="Keyword or topic to search")
    parser.add_argument("--level", choices=["A", "B", "C", "D", "U"], help="Filter by evidence level")
    parser.add_argument("--status", help="Filter by source_status")
    parser.add_argument("--layer", help="Filter by system_layer")
    parser.add_argument("--json", action="store_true", help="Emit JSON array")
    parser.add_argument("--fulltext", action="store_true", help="Search full original post text (slower)")
    parser.add_argument("--context", type=int, default=200, help="Context chars around match (fulltext only)")
    parser.add_argument("--limit", type=int, default=30, help="Max results (fulltext only)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    keyword = args.keyword.lower() if args.keyword else ""

    # ── Full-text mode ──────────────────────────────────────────
    if args.fulltext:
        if not keyword:
            print("❌ fulltext 模式需要关键词")
            return 1
        if not BULK_FILE.exists():
            print("❌ bulk_posts.jsonl 不存在，请先运行 bulk_ingest.py --phase 1")
            return 1

        print(f"🔍 全文检索: \"{args.keyword}\"…")
        results = fulltext_search(keyword, args.context)[:args.limit]

        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print(f"{'='*60}")
            print(f"  找到 {len(results)} 篇匹配帖子")
            print(f"{'='*60}")
            for i, r in enumerate(results, 1):
                print(f"\n[{i}] {r['post_id']} | {r['time_before']} | {len(r['excerpt'])}字")
                print(f"    标题: {r['title'][:60]}")
                print(f"    链接: {r['url']}")
                print(f"    {r['excerpt'][:500]}")
                if len(r['excerpt']) > 500:
                    print(f"    …（{len(r['excerpt'])-500} 字省略）")
        return 0

    # ── Claims search mode ──────────────────────────────────────
    claims = load_claims()
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
