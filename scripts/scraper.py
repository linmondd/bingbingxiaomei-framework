#!/usr/bin/env python3
"""Scrape Xueqiu posts using a persistent browser profile.

Setup (one-time):
    python3 scripts/scraper.py --login

This opens your system Chrome. Log in + solve CAPTCHA once.
The persistent profile at data/browser-profile/ preserves your session.
Subsequent runs reuse it — no more CAPTCHA needed.

Scrape specific posts:
    python3 scripts/scraper.py --urls https://xueqiu.com/7143769715/398214872 ...

Auto-discover from column page:
    python3 scripts/scraper.py --discover

Scrape new posts from discovered list:
    python3 scripts/scraper.py --max 10

Tech: uses launch_persistent_context with channel='chrome' so it runs
your actual installed Chrome, not Playwright's Chromium. The persistent
profile preserves cookies, localStorage, and session data across runs.
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
PROFILE = DATA / "browser-profile"

XUEQIU_COLUMN = "https://xueqiu.com/7143769715/column"
POST_URL_RE = re.compile(r"https?://xueqiu\.com/\d+/(\d+)")

# ── helpers ──────────────────────────────────────────────────────────


def ensure_dirs() -> None:
    SCRAPED.mkdir(parents=True, exist_ok=True)
    PROFILE.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


# ── browser context ──────────────────────────────────────────────────


def launch_context(headless: bool = True):
    """Create a persistent browser context using the system Chrome.

    The persistent profile at data/browser-profile/ preserves cookies,
    localStorage, and session state across runs. Once you log in once
    (via --login with headless=False), subsequent headless runs reuse
    the session without triggering CAPTCHA.
    """
    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE),
        channel="chrome",
        headless=headless,
        viewport={"width": 1280, "height": 800},
        locale="zh-CN",
        args=["--disable-blink-features=AutomationControlled"] if not headless else [],
    )
    return p, context


# ── login flow ───────────────────────────────────────────────────────


def login() -> None:
    """Open a visible Chrome window. Log in + solve CAPTCHA, then press Enter."""
    ensure_dirs()
    print("🔐 正在打开 Chrome…")
    print("    👉 如果需要滑动验证码，请手动滑过去")
    print("    👉 请在浏览器中登录雪球（扫码或账号密码）")
    print("    👉 登录成功后，回到终端按 Enter")

    p, context = launch_context(headless=False)
    page = context.new_page()
    page.goto("https://xueqiu.com/", wait_until="domcontentloaded")
    try:
        input("    ⏎ 按 Enter 保存并关闭…")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        page.close()
        context.close()
        p.stop()
    print(f"✅ 登录态已保存到 {PROFILE}")


# ── scraping ─────────────────────────────────────────────────────────


def scrape_post(post_id: str, context) -> dict | None:
    """Scrape a single Xueqiu post. Returns structured dict or None on failure."""
    url = f"https://xueqiu.com/7143769715/{post_id}"
    page = context.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(2000)

        # Title
        title_el = page.query_selector("article h1, .article__title, h1")
        title = title_el.inner_text().strip() if title_el else ""

        # Date
        date_el = page.query_selector("article .date, .article__date, .publish-time, time")
        published_at = ""
        if date_el:
            published_at = date_el.get_attribute("datetime") or date_el.inner_text().strip()

        # Body
        body_el = page.query_selector(
            "article .article__content, article .content, .article-content, article"
        )
        body = body_el.inner_text().strip() if body_el else ""

        if not title and not body:
            print(f"   ⚠️  {post_id}: 未能提取内容（可能需要重新 --login）")
            return None

        return {
            "post_id": post_id,
            "url": url,
            "title": title,
            "published_at": published_at,
            "body_preview": body[:500],
            "body_full": body,
            "scraped_at": now_iso(),
        }
    except Exception as exc:
        print(f"   ❌ {post_id}: {exc}")
        return None
    finally:
        page.close()


def discover_post_ids(context) -> list[str]:
    """Scrape the column page to discover all post IDs."""
    page = context.new_page()
    ids: list[str] = []
    try:
        page.goto(XUEQIU_COLUMN, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(3000)
        for _ in range(15):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.6)
        links = page.query_selector_all("a[href]")
        seen = set()
        for link in links:
            href = link.get_attribute("href") or ""
            m = POST_URL_RE.search(href)
            if m:
                pid = m.group(1)
                if pid not in seen:
                    seen.add(pid)
                    ids.append(pid)
        print(f"   🔍 在专栏页发现 {len(ids)} 个帖子")
    except Exception as exc:
        print(f"   ⚠️  发现帖子失败: {exc}")
    finally:
        page.close()
    return ids


# ── main ─────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--login", action="store_true", help="打开 Chrome 登录雪球并保存会话")
    group.add_argument("--discover", action="store_true", help="从专栏页发现所有帖子 ID")
    parser.add_argument("--urls", nargs="*", help="要抓取的雪球帖子 URL 列表")
    parser.add_argument("--max", type=int, default=20, help="从已发现列表中最多抓取多少篇（默认 20）")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_dirs()

    if args.login:
        login()
        return 0

    # ── Discover mode ──────────────────────────────────────────────
    if args.discover:
        print("🔍 正在发现专栏帖子…")
        p, ctx = launch_context(headless=True)
        try:
            ids = discover_post_ids(ctx)
            save_json(SCRAPED / "discovered_posts.json", {
                "discovered_at": now_iso(),
                "count": len(ids),
                "post_ids": ids,
            })
            print(f"✅ 发现 {len(ids)} 个帖子，已保存")
        finally:
            ctx.close()
            p.stop()
        return 0

    # ── Scrape mode ────────────────────────────────────────────────
    urls = args.urls or []
    post_ids: list[str] = []
    for u in urls:
        m = POST_URL_RE.search(u)
        if m:
            post_ids.append(m.group(1))
        else:
            print(f"⚠️  跳过无效 URL: {u}")

    # If no URLs provided, read from discovered list
    discovered_file = SCRAPED / "discovered_posts.json"
    if not post_ids and discovered_file.exists():
        discovered = load_json(discovered_file)
        existing = {p.stem.replace("post_", "") for p in SCRAPED.glob("post_*.json")}
        post_ids = [
            pid for pid in discovered.get("post_ids", []) if pid not in existing
        ][:args.max]

    if not post_ids:
        print("没有要抓取的帖子。请提供 --urls 或先运行 --discover")
        return 1

    print(f"📡 准备抓取 {len(post_ids)} 篇帖子…")
    p, ctx = launch_context(headless=True)
    results: list[dict] = []
    try:
        for i, pid in enumerate(post_ids, 1):
            print(f"   [{i}/{len(post_ids)}] {pid}…", end=" ", flush=True)
            result = scrape_post(pid, ctx)
            if result:
                results.append(result)
                save_json(SCRAPED / f"post_{pid}.json", result)
                print(f"✅ {len(result['body_full'])} 字 — {result['title'][:40]}")
            else:
                print("⏭️  跳过")
            time.sleep(1.5)
    finally:
        ctx.close()
        p.stop()

    save_json(SCRAPED / "manifest.json", {
        "updated_at": now_iso(),
        "total_scraped": len(results),
        "post_ids": [r["post_id"] for r in results],
    })
    print(f"\n✅ 抓取完成：{len(results)}/{len(post_ids)} 篇成功")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
