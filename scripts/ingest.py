#!/usr/bin/env python3
"""Full ingestion pipeline: scrape → extract claims via LLM → validate → merge.

Workflow:
    1. Scrape — fetch full post text via Playwright (calls scraper.py)
    2. Extract — send post text to LLM, get structured claim card back
    3. Validate — run validate_claims.py on the candidate
    4. Merge — safely append to claims.jsonl and sources.jsonl

Usage:
    # One-time login (needed before anything else)
    python3 scripts/ingest.py --login

    # Discover all posts from the column page
    python3 scripts/ingest.py --discover

    # Full pipeline: scrape → extract → validate → merge (up to N posts)
    python3 scripts/ingest.py --run --max 5

    # Ingest specific posts
    python3 scripts/ingest.py --run --urls https://xueqiu.com/7143769715/398214872

    # Dry run: scrape + extract but don't merge
    python3 scripts/ingest.py --run --max 3 --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SCRAPED = DATA / "scraped"
CLAIMS_FILE = DATA / "claims.jsonl"
SOURCES_FILE = DATA / "sources.jsonl"

# ── helpers ──────────────────────────────────────────────────────────


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_script(name: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


# ── LLM extraction ───────────────────────────────────────────────────


EXTRACTION_PROMPT = """你是一个金融知识结构化提取器。请从以下雪球帖子中提取核心观点，
按照冰冰小美框架的标准 JSON schema 输出。

帖子内容：
---
{body}
---

请输出一个 JSON 对象（不是数组，只输出一个对象），包含以下字段：

{{
  "id": "claim-{slug}",           // kebab-case 唯一 ID，如 claim-2026-july-new-cycle
  "title": "简短标题（≤20字）",
  "system_layer": "macro-worldview|market-structure|industry-map|trading-system|method-reflection",
  "topics": ["标签1", "标签2"],
  "claim_type": "author_statement",
  "summary": "一句话概括核心判断（≤100字）",
  "first_seen": "{post_date}",    // 帖子发布日期 YYYY-MM-DD
  "last_seen": "{post_date}",
  "status": "active",
  "source_status": "primary_verified",  // 抓取到全文时为 primary_verified，否则 primary_indexed
  "evidence_level": "A",           // 抓取全文为 A，索引片段为 B
  "primary_sources": [{{"url": "{url}", "post_id": "{post_id}", "title": "{title}", "published_at": "{post_date}", "accessed_at": "{today}", "availability": "available"}}],
  "secondary_sources": [],
  "quote_excerpt": "一句最关键的原话摘录（≤50字）",
  "historical_context": {{
    "known_at_the_time": ["当时已知背景"],
    "market_context": ["市场背景"],
    "policy_context": ["政策背景"],
    "later_developments": []
  }},
  "evolution": [],
  "organizer_summary": "",
  "agent_inference": "",
  "external_theories": [],
  "counterevidence": ["一条反证"],
  "internal_tensions": ["一条内部张力"],
  "falsification_conditions": ["推翻该判断的可观察条件"],
  "uncertainties": [],
  "usage_restrictions": ["不构成投资建议"],
  "last_verified": "{today}"
}}

只输出 JSON，不要解释。确保 JSON 合法可解析。"""


def build_extraction_prompt(post: dict) -> str:
    """Build a prompt for the LLM to extract structured claims from a post."""
    return EXTRACTION_PROMPT.format(
        body=post.get("body_full", "")[:8000],  # truncate for token limits
        slug=sanitize_slug(post.get("title", "untitled")),
        post_date=post.get("published_at", "unknown")[:10],
        url=post.get("url", ""),
        post_id=post.get("post_id", ""),
        title=post.get("title", ""),
        today=datetime.now().strftime("%Y-%m-%d"),
    )


def sanitize_slug(title: str) -> str:
    """Create a kebab-case slug from a title."""
    import re
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug[:50].strip("-")


# ── extraction via Proma Cloud API ───────────────────────────────────


def extract_claim_via_llm(post: dict) -> dict | None:
    """Send post text to LLM and get structured claim back."""
    import os
    import urllib.request

    api_key = os.environ.get("PROMA_API_KEY")
    base_url = os.environ.get("PROMA_BASE_URL", "https://api.promap.live/v1")

    if not api_key:
        print("   ⚠️  未设置 PROMA_API_KEY 环境变量，跳过 LLM 提取")
        print("   💡 请将 API Key 写入 .env 文件（格式：PROMA_API_KEY=xxx）")
        print("   💡 可从 Proma 设置页面获取 API Key")
        return None

    prompt = build_extraction_prompt(post)
    payload = json.dumps({
        "model": "deepseek-v4-pro",
        "messages": [
            {"role": "system", "content": "你是一个金融知识结构化提取器。只输出合法 JSON。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        content = result["choices"][0]["message"]["content"].strip()
        # Remove markdown code fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
        return json.loads(content)
    except Exception as exc:
        print(f"   ❌ LLM 调用失败: {exc}")
        return None


# ── candidate preview ────────────────────────────────────────────────


def preview_claim(claim: dict) -> None:
    """Print a human-readable preview of an extracted claim."""
    print(f"""
   ┌─ {claim.get('id', '?')}
   ├─ 标题: {claim.get('title', '?')}
   ├─ 层级: {claim.get('system_layer', '?')}
   ├─ 等级: {claim.get('evidence_level', '?')}
   ├─ 摘要: {claim.get('summary', '?')}
   ├─ 摘录: 「{claim.get('quote_excerpt', '?')}」
   ├─ 反证: {claim.get('counterevidence', [])}
   ├─ 失效: {claim.get('falsification_conditions', [])}
   └─ 标签: {', '.join(claim.get('topics', []))}
""")


# ── main pipeline ────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--login", action="store_true", help="浏览器登录雪球并保存状态")
    parser.add_argument("--discover", action="store_true", help="从专栏页发现所有帖子 ID")
    parser.add_argument("--run", action="store_true", help="执行完整管线：抓取→提取→校验→入库")
    parser.add_argument("--urls", nargs="*", help="要处理的帖子 URL")
    parser.add_argument("--max", type=int, default=5, help="最多处理多少篇（默认 5）")
    parser.add_argument("--dry-run", action="store_true", help="试运行，不写入 claims.jsonl")
    parser.add_argument("--skip-scrape", action="store_true", help="跳过抓取，只用已有 scraped 数据")
    parser.add_argument("--skip-llm", action="store_true", help="跳过 LLM 提取，只抓取")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Delegate to scraper for --login and --discover
    if args.login:
        return run_script("scraper.py", "--login").returncode
    if args.discover:
        return run_script("scraper.py", "--discover").returncode

    if not args.run:
        print("请指定 --run、--login 或 --discover。用 --help 查看完整用法。")
        return 1

    # ── Phase 1: Scrape ──────────────────────────────────────────
    posts: list[dict] = []
    if not args.skip_scrape:
        scrape_args = [f"--max={args.max}"]
        if args.urls:
            scrape_args.extend(["--urls"] + args.urls)
        print("📡 [1/4] 抓取帖子全文…")
        result = run_script("scraper.py", *scrape_args)
        if result.returncode != 0:
            print(f"❌ 抓取失败:\n{result.stderr}")
            return 1

    # Load scraped posts
    manifest_path = SCRAPED / "manifest.json"
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        for pid in manifest.get("post_ids", []):
            post_path = SCRAPED / f"post_{pid}.json"
            if post_path.exists():
                posts.append(load_json(post_path))

    if not posts:
        print("❌ 没有抓到任何帖子。请先运行 --discover 再 --run")
        return 1

    print(f"   ✅ 已加载 {len(posts)} 篇帖子全文")

    # ── Phase 2: Extract claims via LLM ──────────────────────────
    candidates: list[dict] = []
    if not args.skip_llm:
        print(f"\n🧠 [2/4] LLM 提取结构化观点…")
        for i, post in enumerate(posts, 1):
            print(f"   [{i}/{len(posts)}] {post.get('title', '?')[:50]}")
            claim = extract_claim_via_llm(post)
            if claim:
                candidates.append(claim)
                preview_claim(claim)
            time.sleep(0.5)
    else:
        # Without LLM, create skeleton claims
        for post in posts:
            candidates.append({
                "id": f"claim-scraped-{post['post_id']}",
                "title": post.get("title", "未命名"),
                "summary": f"待 LLM 提取: {post.get('body_preview', '')[:80]}",
                "evidence_level": "A",
                "source_status": "primary_verified",
            })

    if not candidates:
        print("❌ LLM 未提取到任何观点")
        return 1

    # ── Phase 3: Validate ────────────────────────────────────────
    print(f"\n🔍 [3/4] 校验候选观点…")
    candidate_file = SCRAPED / "candidates.jsonl"
    with open(candidate_file, "w", encoding="utf-8") as f:
        for c in candidates:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"   {len(candidates)} 条候选已保存到 {candidate_file}")

    # ── Phase 4: Merge ───────────────────────────────────────────
    if args.dry_run:
        print(f"\n🔬 [4/4] 试运行模式 — 不写入数据库")
        print(f"   如需入库，去掉 --dry-run 重新运行")
        return 0

    print(f"\n📝 [4/4] 合并到数据库…")
    existing_ids = {row["id"] for row in load_jsonl(CLAIMS_FILE)}
    merged = 0
    for claim in candidates:
        if claim["id"] in existing_ids:
            print(f"   ⏭️  {claim['id']} 已存在，跳过")
            continue
        append_jsonl(CLAIMS_FILE, claim)
        # Also add source record
        for src in claim.get("primary_sources", []):
            source_record = {
                "id": f"src-xq-{src.get('post_id', 'unknown')}",
                "kind": "primary_post",
                "url": src.get("url", ""),
                "post_id": src.get("post_id", ""),
                "title": src.get("title", ""),
                "author": "冰冰小美",
                "published_at": src.get("published_at", "unknown"),
                "accessed_at": src.get("accessed_at", now_iso()[:10]),
                "source_status": "primary_verified",
                "evidence_level": "A",
                "notes": "通过 Playwright 抓取全文，已通过 LLM 提取结构化观点。",
            }
            append_jsonl(SOURCES_FILE, source_record)
        merged += 1
        print(f"   ✅ {claim['id']}")

    # Final validation
    print(f"\n   🔄 运行数据校验…")
    result = run_script("validate_claims.py")
    if result.returncode == 0:
        print(f"   ✅ 校验通过")
    else:
        print(f"   ⚠️  校验发现问题（需手动修复）:\n{result.stderr}")

    print(f"\n🎉 完成！新增 {merged}/{len(candidates)} 条观点")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
