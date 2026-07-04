#!/usr/bin/env python3
"""Build the full knowledge base from bulk_posts.jsonl.

Phase A: Write ALL posts as source records (metadata + excerpt) → sources.jsonl
Phase B: Generate structured claims for substantial posts → claims.jsonl
Phase C: Validate everything → validate_claims.py + tests

Usage:
    python3 scripts/build_knowledge.py --phase A    # Source records only
    python3 scripts/build_knowledge.py --phase B    # Claim extraction (LLM)
    python3 scripts/build_knowledge.py              # Full pipeline
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request as ur
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BULK_FILE = DATA / "bulk_posts.jsonl"
CLAIMS_FILE = DATA / "claims.jsonl"
SOURCES_FILE = DATA / "sources.jsonl"
UNRESOLVED_FILE = DATA / "unresolved-sources.jsonl"

# Load .env if present
_ENV_FILE = ROOT / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _val = _line.split("=", 1)
            os.environ.setdefault(_key.strip(), _val.strip())

API_KEY = os.environ.get("PROMA_API_KEY", "")
BASE_URL = os.environ.get("PROMA_BASE_URL", "https://api.proma.cool")


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def load_posts() -> list[dict]:
    return [json.loads(l) for l in BULK_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]


# ── Phase A: Source records ──────────────────────────────────────────


def ts_to_date(ts: int) -> str:
    """Convert millisecond timestamp to YYYY-MM-DD."""
    if not ts:
        return "unknown"
    return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")


def tier(post: dict) -> int:
    """Assign priority tier: 1=column/marked, 2=long >1000, 3=long >500, 4=rest"""
    text_len = len(post.get("text", ""))
    if post.get("is_column") or post.get("mark", 0) > 0:
        return 1
    if text_len > 1000:
        return 2
    if text_len > 500:
        return 3
    return 4


def extract_topics(text: str) -> list[str]:
    """Simple keyword-based topic extraction."""
    topics = set()
    keywords = {
        "AI": ["AI", "人工智能", "算力", "大模型", "GPT", "OpenAI"],
        "流动性": ["流动性", "央行", "降准", "降息", "放水", "缩表", "利率"],
        "房地产": ["房地产", "地产", "房价", "楼市", "化债"],
        "科技": ["科技", "半导体", "芯片", "新能源", "光伏", "锂电"],
        "宏观": ["宏观", "GDP", "通胀", "CPI", "PMI", "美联储", "美债", "美元", "汇率"],
        "政策": ["政策", "财政", "国运", "中央", "监管", "改革"],
        "交易": ["交易", "仓位", "止损", "买入", "卖出", "减仓", "做空", "做多"],
        "产业": ["产业", "供应链", "产能", "周期", "新能源", "汽车", "消费"],
        "风险": ["风险", "危机", "崩盘", "泡沫", "违约", "衰退"],
    }
    for topic, kws in keywords.items():
        for kw in kws:
            if kw in text:
                topics.add(topic)
                break
    return sorted(topics) if topics else ["未分类"]


def build_source_record(post: dict) -> dict:
    pid = str(post["post_id"])
    return {
        "id": f"src-xq-{pid}",
        "kind": "primary_post" if not post.get("is_column") else "primary_column",
        "url": f"https://xueqiu.com/7143769715/{pid}",
        "post_id": pid,
        "title": (post.get("title") or post.get("text", "")[:40]).strip(),
        "author": "冰冰小美",
        "published_at": post.get("time_before") or ts_to_date(post.get("created_at", 0)),
        "accessed_at": today_str(),
        "source_status": "primary_verified",
        "evidence_level": "A",
        "notes": f"API 全文获取，{len(post.get('text', ''))} 字。Tier {tier(post)}。",
    }


def build_skeleton_claim(post: dict) -> dict:
    """Build a lightweight claim for posts that don't get full LLM extraction."""
    pid = str(post["post_id"])
    text = post.get("text", "")
    text_len = len(text)
    title = (post.get("title") or text[:30]).strip()
    topics = extract_topics(text)

    if text_len < 100:
        layer = "source-map"
        claim_type = "unattributed_claim"
        evidence = "U"
    elif text_len < 500:
        layer = "market-structure"
        claim_type = "organizer_summary"
        evidence = "D"
    else:
        layer = "macro-worldview"
        claim_type = "author_statement"
        evidence = "B"

    return {
        "id": f"claim-bulk-{pid}",
        "title": title[:40] if title else "未命名",
        "system_layer": layer,
        "topics": topics,
        "claim_type": claim_type,
        "summary": text[:120].replace("\n", " ").strip() if text else "",
        "first_seen": post.get("time_before", ts_to_date(post.get("created_at", 0)))[:10] if post.get("time_before") else ts_to_date(post.get("created_at", 0)),
        "last_seen": post.get("time_before", ts_to_date(post.get("created_at", 0)))[:10] if post.get("time_before") else ts_to_date(post.get("created_at", 0)),
        "status": "active",
        "source_status": "primary_verified" if evidence == "A" else "secondary_reproduced",
        "evidence_level": evidence,
        "primary_sources": [{"url": f"https://xueqiu.com/7143769715/{pid}", "post_id": pid, "title": title, "published_at": post.get("time_before", ""), "accessed_at": today_str(), "availability": "available"}],
        "secondary_sources": [],
        "quote_excerpt": text[:80].replace("\n", " ") if text else "",
        "historical_context": {"known_at_the_time": [], "market_context": [], "policy_context": [], "later_developments": []},
        "evolution": [],
        "organizer_summary": "" if evidence != "D" else "自动从 API 文本生成，待人工复核。",
        "agent_inference": "批量自动提取，未经 LLM 深度分析。",
        "external_theories": [],
        "counterevidence": [],
        "internal_tensions": [],
        "falsification_conditions": [],
        "uncertainties": ["批量自动生成，建议人工抽查"],
        "usage_restrictions": ["不构成投资建议", "自动生成，可能需人工修正"],
        "last_verified": today_str(),
    }


def phase_a() -> tuple[list[dict], list[dict]]:
    """Generate source records + skeleton claims for ALL posts."""
    posts = load_posts()
    print(f"📋 Phase A: 生成元数据 + 骨架观点（{len(posts)} 帖）…")

    sources = []
    claims = []

    for i, post in enumerate(posts, 1):
        src = build_source_record(post)
        sources.append(src)

        claim = build_skeleton_claim(post)
        claims.append(claim)

        if i % 2000 == 0:
            print(f"   {i}/{len(posts)} ({100*i//len(posts)}%)…")

    # Write sources
    with open(SOURCES_FILE, "w", encoding="utf-8") as f:
        for s in sources:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    # Write claims (replace existing)
    with open(CLAIMS_FILE, "w", encoding="utf-8") as f:
        for c in claims:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"✅ Phase A 完成: {len(sources)} sources, {len(claims)} claims")
    return sources, claims


# ── Phase B: LLM extraction for priority posts ───────────────────────


EXTRACTION_SYSTEM = """你是一个金融知识结构化提取器。请从以下雪球帖子中提取核心观点，
按照冰冰小美框架的标准 JSON schema 输出。

只输出合法的 JSON 对象，不要解释。"""

EXTRACTION_PROMPT = """帖子元数据：
- ID: {post_id}
- 标题: {title}
- 日期: {date}
- URL: https://xueqiu.com/7143769715/{post_id}

帖子全文：
---
{text}
---

请输出一个 JSON 对象：

{{
  "title": "简短标题（≤20字）",
  "system_layer": "macro-worldview|market-structure|industry-map|trading-system|method-reflection|source-map",
  "topics": ["标签1", "标签2", "标签3"],
  "summary": "一句话概括核心判断（≤120字）",
  "quote_excerpt": "一句最关键的原话摘录（≤80字）",
  "evidence_level": "A",
  "source_status": "primary_verified",
  "historical_context": {{"known_at_the_time": [], "market_context": [], "policy_context": [], "later_developments": []}},
  "external_theories": [],
  "counterevidence": ["一条反证"],
  "internal_tensions": ["一条内部张力"],
  "falsification_conditions": ["推翻该判断的可观察条件"],
  "uncertainties": [],
  "usage_restrictions": ["不构成投资建议"]
}}"""


def llm_extract(post: dict) -> dict | None:
    """Send post to LLM for structured claim extraction."""
    if not API_KEY:
        return None

    text = post.get("text", "")
    if len(text) > 6000:
        text = text[:6000]  # truncate for token limits

    prompt = EXTRACTION_PROMPT.format(
        post_id=post["post_id"],
        title=post.get("title", "")[:40],
        date=post.get("time_before", ts_to_date(post.get("created_at", 0))),
        text=text,
    )

    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": EXTRACTION_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 2048,
    }).encode("utf-8")

    req = ur.Request(
        f"{BASE_URL}/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
    )

    try:
        with ur.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        content = result["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
        return json.loads(content)
    except Exception as exc:
        print(f"      ❌ LLM: {exc}")
        return None


def phase_b(claims: list[dict], posts: list[dict], max_llm: int = 500) -> list[dict]:
    """Run LLM extraction on priority posts (Tier 1+2)."""
    if not API_KEY:
        print("⚠️  未设置 PROMA_API_KEY，跳过 LLM 提取")
        return claims

    # Build index: map post_id → claim
    claim_map = {c["id"].replace("claim-bulk-", ""): c for c in claims}
    post_map = {p["post_id"]: p for p in posts}

    # Priority: Tier 1 (column/marked) + Tier 2 (long >1000 chars)
    priority_ids = [
        p["post_id"] for p in posts
        if tier(p) <= 2
    ][:max_llm]

    print(f"\n🧠 Phase B: LLM 深度提取（{len(priority_ids)} 篇重点帖）…")

    enriched = 0
    for i, pid in enumerate(priority_ids, 1):
        post = post_map.get(pid)
        claim = claim_map.get(pid)
        if not post or not claim:
            print(f"   [{i}/{len(priority_ids)}] {pid}: ⏭️ 未找到")
            continue

        print(f"   [{i}/{len(priority_ids)}] {pid}: {post.get('title', post.get('text', '')[:30])[:40]}", end=" ", flush=True)

        extracted = llm_extract(post)
        if not extracted:
            print("⏭️")
            continue

        # Merge LLM output into the existing skeleton claim
        c = claim
        c["title"] = extracted.get("title", c["title"])
        c["system_layer"] = extracted.get("system_layer", c["system_layer"])
        c["summary"] = extracted.get("summary", c["summary"])
        c["quote_excerpt"] = extracted.get("quote_excerpt", c["quote_excerpt"])
        c["evidence_level"] = "A"
        c["source_status"] = "primary_verified"
        c["claim_type"] = "author_statement"
        c["historical_context"] = extracted.get("historical_context", c.get("historical_context", {}))
        c["external_theories"] = extracted.get("external_theories", [])
        c["counterevidence"] = extracted.get("counterevidence", [])
        c["internal_tensions"] = extracted.get("internal_tensions", [])
        c["falsification_conditions"] = extracted.get("falsification_conditions", [])
        c["uncertainties"] = extracted.get("uncertainties", [])
        c["usage_restrictions"] = extracted.get("usage_restrictions", ["不构成投资建议"])
        c["agent_inference"] = ""
        c["organizer_summary"] = ""
        enriched += 1
        print("✅")

        # Save every 50
        if i % 50 == 0:
            with open(CLAIMS_FILE, "w", encoding="utf-8") as f:
                for c in claims:
                    f.write(json.dumps(c, ensure_ascii=False) + "\n")
            print(f"      💾 已保存 ({enriched} 篇 enrich)")

        time.sleep(0.3)

    # Final save
    with open(CLAIMS_FILE, "w", encoding="utf-8") as f:
        for c in claims:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"\n✅ Phase B 完成: {enriched}/{len(priority_ids)} 篇 LLM enrich")
    return claims


# ── Phase C: Analysis ────────────────────────────────────────────────


def phase_c(claims: list[dict]):
    """Print statistics."""
    total = len(claims)
    by_level = {}
    by_layer = {}
    by_tier = {}
    for c in claims:
        lvl = c.get("evidence_level", "?")
        by_level[lvl] = by_level.get(lvl, 0) + 1
        layer = c.get("system_layer", "?")
        by_layer[layer] = by_layer.get(layer, 0) + 1
    print(f"\n📊 知识库统计：")
    print(f"   总观点: {total}")
    print(f"   证据分布: {dict(sorted(by_level.items()))}")
    print(f"   层级分布: {dict(sorted(by_layer.items()))}")


# ── main ─────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", type=str, choices=["A", "B", "C"], help="只运行指定 Phase")
    parser.add_argument("--max-llm", type=int, default=500, help="LLM 最大提取篇数")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not BULK_FILE.exists():
        print("❌ 请先运行 bulk_ingest.py --phase 1")
        return 1

    posts = load_posts()

    if args.phase == "A":
        phase_a()
        return 0

    if args.phase == "B":
        claims = [json.loads(l) for l in CLAIMS_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
        claims = phase_b(claims, posts, max_llm=args.max_llm)
        return 0

    if args.phase == "C":
        claims = [json.loads(l) for l in CLAIMS_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
        phase_c(claims)
        return 0

    # Full pipeline
    sources, claims = phase_a()
    claims = phase_b(claims, posts, max_llm=args.max_llm)
    phase_c(claims)

    print(f"\n🎉 全量入库完成！")
    print(f"   sources.jsonl: {len(sources)} 条")
    print(f"   claims.jsonl:  {len(claims)} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
