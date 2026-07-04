#!/usr/bin/env python3
"""Full bulk ingestion: discover ALL posts → enrich long-form via Playwright → save.

PHASE 1 (fast): Paginate through ALL API pages, collect every post's text.
PHASE 2 (enrich): For posts with substantial text (>200 chars) scrape full article via Playwright.
PHASE 3 (save): Write everything to data/bulk_posts.jsonl.

Usage:
    python3 scripts/bulk_ingest.py              # Full pipeline
    python3 scripts/bulk_ingest.py --phase 1    # API discovery only
    python3 scripts/bulk_ingest.py --phase 2    # Enrich only (requires Phase 1)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SCRAPED = DATA / "scraped"
BULK_FILE = DATA / "bulk_posts.jsonl"
PROGRESS_FILE = SCRAPED / "bulk_progress.json"

XUEQIU_UID = "7143769715"
API_URL = f"https://xueqiu.com/statuses/user_timeline.json?user_id={XUEQIU_UID}&page={{page}}"
POST_URL = f"https://xueqiu.com/{XUEQIU_UID}/{{post_id}}"


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    return {"phase1_done": False, "last_page": 0, "total_posts": 0, "phase2_done": False, "enriched": 0}


def save_progress(state: dict) -> None:
    SCRAPED.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ── cookie helpers ───────────────────────────────────────────────────


def get_cookie_str() -> str:
    import browser_cookie3
    cj = browser_cookie3.chrome(domain_name="xueqiu.com")
    return "; ".join(f"{c.name}={c.value}" for c in cj)


def api_get(url: str) -> dict:
    import urllib.request as ur
    req = ur.Request(url, headers={
        "Cookie": get_cookie_str(),
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        "Referer": f"https://xueqiu.com/{XUEQIU_UID}/column",
    })
    with ur.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


# ── Phase 1: API bulk discovery ──────────────────────────────────────


def phase1_discover_all() -> list[dict]:
    """Paginate through ALL API pages. Returns list of all post dicts."""
    progress = load_progress()
    all_posts: list[dict] = []

    # Get page 1 to learn total
    print("📡 Phase 1: 全量 API 发现…")
    data = api_get(API_URL.format(page=1))
    total_pages = data.get("maxPage", 0)
    total_count = data.get("total", 0)
    print(f"   📊 {total_pages} 页，约 {total_count} 帖")

    start_page = 1
    if progress.get("phase1_done"):
        print("   ✅ Phase 1 已完成，跳过")
        # Reload from bulk file
        if BULK_FILE.exists():
            return [json.loads(l) for l in BULK_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
        return []

    # Collect all
    errors = 0
    for page in range(start_page, total_pages + 1):
        try:
            data = api_get(API_URL.format(page=page))
            items = data.get("statuses", [])
            for item in items:
                all_posts.append({
                    "post_id": str(item.get("id", "")),
                    "title": (item.get("title") or item.get("rawTitle") or "").strip(),
                    "created_at": item.get("created_at", 0),
                    "time_before": item.get("timeBefore", ""),
                    "text": (item.get("text") or "").strip(),
                    "description": (item.get("description") or "").strip(),
                    "truncated": item.get("truncated", False),
                    "retweet_count": item.get("retweet_count", 0),
                    "reply_count": item.get("reply_count", 0),
                    "fav_count": item.get("fav_count", 0),
                    "like_count": item.get("like_count", 0),
                    "target": item.get("target", ""),
                    "source": item.get("source", ""),
                    "is_column": item.get("is_column", False),
                    "stock_correlation": item.get("stockCorrelation", []),
                    "mark": item.get("mark", 0),
                    "source_link": item.get("source_link", ""),
                    "phase1_scraped": True,
                })
        except Exception as exc:
            errors += 1
            if errors > 10:
                print(f"\n   ❌ 连续 {errors} 次错误，暂停")
                break
            time.sleep(1)
            continue

        errors = 0

        if page % 50 == 0 or page == total_pages:
            print(f"   📄 {page}/{total_pages} 页 ({100*page//total_pages}%) — 已收集 {len(all_posts)} 帖")

        # Save progress every 50 pages
        if page % 50 == 0:
            save_progress({"phase1_done": False, "last_page": page, "total_posts": len(all_posts)})
            # Write incrementally
            with open(BULK_FILE, "w", encoding="utf-8") as f:
                for p in all_posts:
                    f.write(json.dumps(p, ensure_ascii=False) + "\n")

        time.sleep(0.15)  # be gentle

    # Final save
    with open(BULK_FILE, "w", encoding="utf-8") as f:
        for p in all_posts:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    save_progress({"phase1_done": True, "last_page": total_pages, "total_posts": len(all_posts)})
    print(f"\n✅ Phase 1 完成：{len(all_posts)}/{total_count} 帖")
    return all_posts


# ── Phase 2: Enrich long-form posts via Playwright ───────────────────


def phase2_enrich(posts: list[dict]) -> list[dict]:
    """For posts with significant text content, scrape the full article via Playwright."""
    progress = load_progress()
    if progress.get("phase2_done"):
        print("   ✅ Phase 2 已完成，跳过")
        return posts

    # Find posts that need enrichment: long-form, column posts, or marked posts
    to_enrich = []
    for p in posts:
        text_len = len(p.get("text", ""))
        desc_len = len(p.get("description", ""))
        is_long = text_len > 500 or desc_len > 500
        is_column = p.get("is_column", False)
        is_marked = p.get("mark", 0) > 0
        has_stock = bool(p.get("stock_correlation"))

        if is_long or is_column or is_marked:
            to_enrich.append(p)

    if not to_enrich:
        print("   没有需要 enrich 的帖子")
        return posts

    print(f"\n🔎 Phase 2: Playwright 抓取长文（{len(to_enrich)} 篇）…")

    import browser_cookie3
    from playwright.sync_api import sync_playwright

    cj = browser_cookie3.chrome(domain_name="xueqiu.com")
    cookies = [{"name": str(c.name), "value": str(c.value), "domain": str(c.domain) if c.domain else ".xueqiu.com", "path": str(c.path) if c.path else "/", "secure": bool(c.secure) if c.secure is not None else False} for c in cj]

    p = sync_playwright().start()
    b = p.chromium.launch(channel="chrome", headless=False, args=["--window-position=-2000,-2000"])
    ctx = b.new_context(viewport={"width": 1280, "height": 800}, locale="zh-CN")
    ctx.add_cookies(cookies)

    enriched = 0
    for i, post in enumerate(to_enrich, 1):
        pid = post["post_id"]
        page = ctx.new_page()
        try:
            page.goto(POST_URL.format(post_id=pid), wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(2000)

            page_title = page.title()
            if "验证" in page_title:
                print(f"   [{i}/{len(to_enrich)}] {pid}: CAPTCHA")
                page.close()
                continue

            # Get article body
            article = page.query_selector("article")
            if article:
                full_text = article.inner_text().strip()
                if len(full_text) > len(post.get("text", "")):
                    post["text"] = full_text
                    post["enriched"] = True
                    enriched += 1
                    print(f"   [{i}/{len(to_enrich)}] {pid}: ✅ {len(full_text)} 字 — {(post.get('title') or full_text)[:40]}")
                else:
                    print(f"   [{i}/{len(to_enrich)}] {pid}: ⏭️  API 内容已完整")
            else:
                # Try body fallback
                body_text = page.evaluate("document.body.innerText") or ""
                if len(body_text) > len(post.get("text", "")):
                    post["text"] = body_text
                    post["enriched"] = True
                    enriched += 1
        except Exception as exc:
            print(f"   [{i}/{len(to_enrich)}] {pid}: ❌ {exc}")
        finally:
            page.close()

        if i % 10 == 0:
            # Incremental save
            with open(BULK_FILE, "w", encoding="utf-8") as f:
                for pp in posts:
                    f.write(json.dumps(pp, ensure_ascii=False) + "\n")
            save_progress({**progress, "enriched": enriched})

        time.sleep(1)

    ctx.close()
    b.close()
    p.stop()

    # Final save
    with open(BULK_FILE, "w", encoding="utf-8") as f:
        for pp in posts:
            f.write(json.dumps(pp, ensure_ascii=False) + "\n")
    save_progress({**progress, "phase2_done": True, "enriched": enriched})
    print(f"\n✅ Phase 2 完成：{enriched} 篇 enrich")
    return posts


# ── main ─────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", type=int, choices=[1, 2], help="只运行指定 Phase")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    SCRAPED.mkdir(parents=True, exist_ok=True)

    if args.phase == 1:
        posts = phase1_discover_all()
        print(f"\n📦 已保存 {len(posts)} 帖到 {BULK_FILE}")
        return 0

    if args.phase == 2:
        if not BULK_FILE.exists():
            print("❌ 请先运行 Phase 1")
            return 1
        posts = [json.loads(l) for l in BULK_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
        posts = phase2_enrich(posts)
        return 0

    # Full pipeline
    posts = phase1_discover_all()
    posts = phase2_enrich(posts)

    # Stats
    total = len(posts)
    with_text = sum(1 for p in posts if len(p.get("text", "")) > 50)
    enriched = sum(1 for p in posts if p.get("enriched"))
    long_form = sum(1 for p in posts if len(p.get("text", "")) > 500)

    print(f"\n{'='*50}")
    print(f"📊 全量统计：")
    print(f"   总帖数:     {total}")
    print(f"   有内容:     {with_text}")
    print(f"   长文(>500字): {long_form}")
    print(f"   Playwright enrich: {enriched}")
    print(f"   输出文件:   {BULK_FILE}")
    print(f"{'='*50}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
