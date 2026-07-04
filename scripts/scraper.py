#!/usr/bin/env python3
"""Scrape Xueqiu posts using real Chrome cookies + Playwright.

HOW IT WORKS
    Reads your actual Chrome cookies for xueqiu.com (via browser_cookie3),
    injects them into a Playwright headful browser, then scrapes posts.
    Because the cookies come from your real browser session, no CAPTCHA.
    Because Playwright runs JavaScript, no WAF block.

SETUP (one-time)
    Make sure you're logged into xueqiu.com in your regular Chrome.
    pip3 install browser-cookie3

USAGE
    python3 scripts/scraper.py --discover           # Find all posts
    python3 scripts/scraper.py --max 10             # Scrape 10 new posts
    python3 scripts/scraper.py --urls https://...    # Scrape specific posts
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

XUEQIU_COLUMN = "https://xueqiu.com/7143769715/column"
POST_URL_RE = re.compile(r"https?://xueqiu\.com/\d+/(\d+)")


# ── helpers ──────────────────────────────────────────────────────────


def ensure_dirs() -> None:
    SCRAPED.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


# ── cookie loading ───────────────────────────────────────────────────


def load_chrome_cookies() -> list[dict]:
    """Read xueqiu.com cookies from the user's real Chrome.

    Returns a list of cookie dicts compatible with Playwright's
    context.add_cookies() format: {name, value, domain, path, ...}
    """
    import browser_cookie3

    cj = browser_cookie3.chrome(domain_name="xueqiu.com")
    cookies: list[dict] = []
    for c in cj:
        cookies.append({
            "name": str(c.name),
            "value": str(c.value),
            "domain": str(c.domain) if c.domain else ".xueqiu.com",
            "path": str(c.path) if c.path else "/",
            "secure": bool(c.secure) if c.secure is not None else False,
        })
    return cookies


# ── browser context ──────────────────────────────────────────────────


def launch_context():
    """Create a headful Playwright browser with Chrome cookies injected.

    Uses headless=False because Xueqiu WAF requires JS execution
    and detects headless browsers. Window is positioned offscreen.
    """
    from playwright.sync_api import sync_playwright

    cookies = load_chrome_cookies()
    if not cookies:
        raise RuntimeError(
            "未找到 xueqiu.com 的 Chrome Cookie。请先在 Chrome 中登录雪球。"
        )
    print(f"   🍪 加载了 {len(cookies)} 个 Cookie")

    p = sync_playwright().start()
    browser = p.chromium.launch(
        channel="chrome",
        headless=False,
        args=[
            "--window-position=-2000,-2000",
            "--disable-blink-features=AutomationControlled",
        ],
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="zh-CN",
    )
    context.add_cookies(cookies)
    return p, browser, context


# ── scraping ─────────────────────────────────────────────────────────


def scrape_post(post_id: str, context) -> dict | None:
    """Scrape a single Xueqiu post. Returns structured dict or None on failure."""
    url = f"https://xueqiu.com/7143769715/{post_id}"
    page = context.new_page()
    try:
        # Use domcontentloaded (not networkidle) — faster and less prone to timeout
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        except Exception:
            # Retry with load event
            page.goto(url, wait_until="load", timeout=45_000)
        page.wait_for_timeout(2500)

        page_title = page.title()
        if "验证" in page_title:
            print(f"   ⚠️  {post_id}: CAPTCHA — 请在 Chrome 中刷新雪球页面后重试")
            return None

        # Title from article heading, fallback to page title
        title_el = page.query_selector("article h1, .article__title, h1, .status-title")
        post_title = title_el.inner_text().strip() if title_el else ""
        if not post_title:
            post_title = page_title.replace(" - 雪球", "").strip()

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

        if not post_title and not body:
            # Try fallback: get all visible text
            body = page.evaluate("document.body.innerText") or ""
            if len(body) < 100:
                print(f"   ⚠️  {post_id}: 内容不足")
                return None

        return {
            "post_id": post_id,
            "url": url,
            "title": post_title,
            "published_at": published_at,
            "body_preview": body[:500] if body else "",
            "body_full": body,
            "scraped_at": now_iso(),
        }
    except Exception as exc:
        print(f"   ❌ {post_id}: {exc}")
        return None
    finally:
        page.close()


def discover_post_ids_via_api(max_pages: int = 100) -> list[str]:
    """Discover all post IDs via the Xueqiu user timeline API.

    Uses the same Chrome cookies as the browser context. Much faster
    than scraping the column page — can discover thousands of posts
    in seconds.
    """
    cookies = load_chrome_cookies()
    cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)

    ids: list[str] = []
    seen = set()
    for page_num in range(1, max_pages + 1):
        url = (
            f"https://xueqiu.com/statuses/user_timeline.json"
            f"?user_id=7143769715&page={page_num}"
        )
        req = urllib_request(url, cookie_str)
        try:
            data = json.loads(req)
        except Exception:
            break

        items = data.get("statuses", [])
        if not items:
            break

        for item in items:
            pid = str(item.get("id", ""))
            if pid and pid not in seen:
                seen.add(pid)
                ids.append(pid)

        if page_num == 1:
            total_pages = data.get("maxPage", "?")
            print(f"   📊 共 {total_pages} 页，约 {data.get('total', '?')} 帖")

        if page_num % 50 == 0:
            print(f"   📄 已扫描 {page_num} 页，发现 {len(ids)} 帖…")
        time.sleep(0.3)

    print(f"   🔍 共发现 {len(ids)} 个帖子")
    return ids


def urllib_request(url: str, cookie_str: str) -> bytes:
    """Make a cookie-authenticated HTTP request."""
    import urllib.request as ur

    req = ur.Request(url, headers={
        "Cookie": cookie_str,
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36"
        ),
        "Referer": "https://xueqiu.com/7143769715/column",
    })
    with ur.urlopen(req, timeout=15) as resp:
        return resp.read()


# ── main ─────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--discover", action="store_true", help="从专栏页发现所有帖子 ID")
    parser.add_argument("--urls", nargs="*", help="要抓取的帖子 URL 列表")
    parser.add_argument("--max", type=int, default=20, help="最多抓取篇数（默认 20）")
    parser.add_argument("--pages", type=int, default=100, help="discover 最多扫描页数（默认 100）")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_dirs()

    if args.discover:
        print(f"🔍 正在通过 API 发现帖子（最多 {args.pages} 页）…")
        ids = discover_post_ids_via_api(max_pages=args.pages)
        if ids:
            save_json(SCRAPED / "discovered_posts.json", {
                "discovered_at": now_iso(),
                "count": len(ids),
                "post_ids": ids,
            })
            print(f"✅ 发现 {len(ids)} 个帖子")
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

    if not post_ids:
        discovered_file = SCRAPED / "discovered_posts.json"
        if discovered_file.exists():
            discovered = load_json(discovered_file)
            existing = {p.stem.replace("post_", "") for p in SCRAPED.glob("post_*.json")}
            post_ids = [
                pid for pid in discovered.get("post_ids", []) if pid not in existing
            ][:args.max]

    if not post_ids:
        print("没有要抓取的帖子。请提供 --urls 或先运行 --discover")
        return 1

    print(f"📡 准备抓取 {len(post_ids)} 篇帖子…")
    p, b, ctx = launch_context()
    results: list[dict] = []
    try:
        for i, pid in enumerate(post_ids, 1):
            print(f"   [{i}/{len(post_ids)}] {pid}…", end=" ", flush=True)
            result = scrape_post(pid, ctx)
            if result:
                results.append(result)
                save_json(SCRAPED / f"post_{pid}.json", result)
                chars = len(result.get("body_full", ""))
                t = result.get("title", "")[:40]
                print(f"✅ {chars} 字 — {t}")
            else:
                print("⏭️  跳过")
            time.sleep(2)
    finally:
        ctx.close()
        b.close()
        p.stop()

    if results:
        save_json(SCRAPED / "manifest.json", {
            "updated_at": now_iso(),
            "total_scraped": len(results),
            "post_ids": [r["post_id"] for r in results],
        })
    print(f"\n✅ 抓取完成：{len(results)}/{len(post_ids)} 篇成功")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
