#!/usr/bin/env python3
"""Quality scoring for all 10,745 posts — grade S/A/B/C, none discarded.

S: Column posts, marked posts, long-form >2000 with high engagement → deep knowledge
A: Long-form >1000, or substantial content with engagement → structured claims
B: Medium 200-1000 chars → auto-summarize
C: Short <200 chars, or minimal content → language DNA only

ALL posts are retained. Lower tiers contribute to expression DNA (vocabulary,
sentence patterns, rhythm) even if they don't become standalone knowledge nodes.

Output:
    data/post_quality.jsonl   — every post with quality_score + tier
    data/dna_corpus.jsonl      — C-tier posts assembled for style analysis
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BULK_FILE = DATA / "bulk_posts.jsonl"
CLAIMS_FILE = DATA / "claims.jsonl"
QUALITY_FILE = DATA / "post_quality.jsonl"
DNA_FILE = DATA / "dna_corpus.jsonl"


def load_posts() -> list[dict]:
    if BULK_FILE.exists():
        return [json.loads(l) for l in BULK_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    # Fallback: extract from claims
    claims = [json.loads(l) for l in CLAIMS_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    posts = []
    for c in claims:
        pid = c["id"].replace("claim-bulk-", "")
        srcs = c.get("primary_sources", [])
        posts.append({
            "post_id": pid,
            "title": c.get("title", ""),
            "text": c.get("summary", "") + " " + c.get("quote_excerpt", ""),
            "created_at": 0,
            "time_before": c.get("first_seen", ""),
            "is_column": c.get("system_layer") == "source-map",
            "mark": 0,
            "retweet_count": 0,
            "reply_count": 0,
            "fav_count": 0,
            "like_count": 0,
            "stock_correlation": [],
            "truncated": False,
            "source": "",
        })
    return posts


# ── scoring factors ──────────────────────────────────────────────────


def text_length_score(text: str) -> float:
    """0-25 points: text volume."""
    length = len(text)
    if length >= 3000: return 25
    if length >= 2000: return 22
    if length >= 1000: return 18
    if length >= 500:  return 14
    if length >= 200:  return 8
    if length >= 100:  return 4
    return 1


def engagement_score(post: dict) -> float:
    """0-20 points: social engagement signals quality."""
    retweet = post.get("retweet_count", 0) or 0
    reply = post.get("reply_count", 0) or 0
    like = post.get("like_count", 0) or 0
    fav = post.get("fav_count", 0) or 0
    total = retweet * 2 + reply * 1.5 + like + fav * 1.5
    return min(20, math.log2(total + 2) * 3)


def content_richness_score(text: str) -> float:
    """0-15 points: vocabulary diversity, structure markers."""
    if len(text) < 50: return 1
    words = text.replace("\n", " ").split()
    unique = len(set(words))
    total = len(words)
    ratio = unique / max(total, 1)
    # Has numbered points?
    has_structure = any(marker in text for marker in ["1.", "2.", "一、", "二、", "①", "②"])
    structure_bonus = 5 if has_structure else 0
    return min(15, ratio * 15 + structure_bonus)


def authority_score(post: dict) -> float:
    """0-25 points: author's own quality signals."""
    score = 0.0
    if post.get("is_column"): score += 20
    if (post.get("mark") or 0) > 0: score += 10
    if post.get("title", "").strip(): score += 3
    if not post.get("truncated", False): score += 2
    return min(25, score)


def topic_signal_score(post: dict) -> float:
    """0-15 points: has stock/industry correlation, topic clarity."""
    score = 0.0
    if post.get("stock_correlation"): score += 8
    text = post.get("text", "")
    topic_keywords = [
        "宏观", "流动性", "央行", "财政", "利率", "汇率", "美债", "美元",
        "AI", "科技", "半导体", "新能源", "产业", "周期",
        "交易", "仓位", "止损", "买入", "卖出",
        "风险", "危机", "泡沫", "国运", "政策",
    ]
    matches = sum(1 for kw in topic_keywords if kw in text)
    score += min(7, matches * 1.0)
    return min(15, score)


def compute_quality(post: dict) -> dict:
    """Return {tier, quality_score, factor_breakdown, usage}."""
    text = post.get("text", "") or post.get("description", "") or ""

    tl = text_length_score(text)
    eg = engagement_score(post)
    cr = content_richness_score(text)
    au = authority_score(post)
    ts = topic_signal_score(post)

    total = tl + eg + cr + au + ts

    if total >= 75: tier = "S"
    elif total >= 55: tier = "A"
    elif total >= 30: tier = "B"
    else: tier = "C"

    usage = {
        "S": "深度知识提取 + 结构化观点 + 反证/失效条件 + 表达 DNA",
        "A": "结构化 claims + counterevidence + 表达 DNA",
        "B": "自动归纳 summary + 表达 DNA",
        "C": "语言 DNA 素材（词汇、句式、节奏、论证指纹）",
    }[tier]

    return {
        "post_id": post.get("post_id", ""),
        "tier": tier,
        "quality_score": round(total, 1),
        "factors": {
            "text_length": round(tl, 1),
            "engagement": round(eg, 1),
            "content_richness": round(cr, 1),
            "authority": round(au, 1),
            "topic_signal": round(ts, 1),
        },
        "text_length": len(text),
        "title": (post.get("title") or text[:30]).strip()[:60],
        "time_before": post.get("time_before", ""),
        "usage": usage,
    }


# ── DNA corpus build ────────────────────────────────────────────────


def build_dna_corpus(posts: list[dict], quality: dict[str, dict]) -> list[dict]:
    """Assemble C-tier posts into a DNA corpus for style analysis."""
    dna = []
    for p in posts:
        pid = p.get("post_id", "")
        q = quality.get(pid, {})
        if q.get("tier") in ("C", "B"):
            text = p.get("text", "")
            if len(text) > 20:
                dna.append({
                    "post_id": pid,
                    "text": text,
                    "tier": q.get("tier", "C"),
                    "time_before": p.get("time_before", ""),
                })
    return dna


# ── reports ──────────────────────────────────────────────────────────


def print_report(quality: dict[str, dict], dna_count: int):
    tiers = Counter(q["tier"] for q in quality.values())
    total = sum(tiers.values())
    print(f"\n{'='*50}")
    print(f"📊 质量分级完成 — {total} 帖，零丢弃")
    print(f"{'='*50}")
    print(f"  S 级 (深度知识):    {tiers.get('S', 0):>6}  ({100*tiers.get('S',0)/total:.1f}%)")
    print(f"  A 级 (结构化观点):   {tiers.get('A', 0):>6}  ({100*tiers.get('A',0)/total:.1f}%)")
    print(f"  B 级 (自动归纳):     {tiers.get('B', 0):>6}  ({100*tiers.get('B',0)/total:.1f}%)")
    print(f"  C 级 (语言 DNA):     {tiers.get('C', 0):>6}  ({100*tiers.get('C',0)/total:.1f}%)")
    print(f"{'='*50}")
    print(f"  DNA 语料库:          {dna_count:>6} 帖 (C+B 级)")
    print(f"  知识提取候选:         {tiers.get('S',0)+tiers.get('A',0):>6} 帖 (S+A 级)")
    print()

    # Show S-tier samples
    s_posts = [(pid, q) for pid, q in quality.items() if q["tier"] == "S"]
    s_posts.sort(key=lambda x: -x[1]["quality_score"])
    print("🏆 S 级 Top 10:")
    for pid, q in s_posts[:10]:
        print(f"  [{q['quality_score']:.0f}] {pid}: {q['title'][:50]}")


# ── main ─────────────────────────────────────────────────────────────


def main() -> int:
    print("📊 正在加载帖子…")
    posts = load_posts()
    print(f"   已加载 {len(posts)} 帖")

    print("🔢 正在计算质量分…")
    quality: dict[str, dict] = {}
    for i, post in enumerate(posts, 1):
        pid = post.get("post_id", str(i))
        q = compute_quality(post)
        quality[pid] = q
        if i % 2000 == 0:
            print(f"   {i}/{len(posts)} ({100*i//len(posts)}%)…")

    # Write quality scores
    with open(QUALITY_FILE, "w", encoding="utf-8") as f:
        for q in sorted(quality.values(), key=lambda x: -x["quality_score"]):
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    # Write DNA corpus
    dna = build_dna_corpus(posts, quality)
    with open(DNA_FILE, "w", encoding="utf-8") as f:
        for d in dna:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    print_report(quality, len(dna))
    print(f"✅ 输出文件:")
    print(f"   {QUALITY_FILE} — 全量质量分级")
    print(f"   {DNA_FILE} — 语言 DNA 素材库")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
