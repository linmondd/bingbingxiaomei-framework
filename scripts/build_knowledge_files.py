#!/usr/bin/env python3
"""Build structured knowledge/*.md files from S+A tier posts via LLM extraction.

Reads post_quality.jsonl → extracts S+A tier posts → LLM generates
structured knowledge files → saves to knowledge/ directory.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request as ur
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BULK_FILE = DATA / "bulk_posts.jsonl"
QUALITY_FILE = DATA / "post_quality.jsonl"
KNOWLEDGE = ROOT / "knowledge"

API_KEY = ""
BASE_URL = "https://api.deepseek.com"

# Load .env
_ENV_FILE = ROOT / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _val = _line.split("=", 1)
            os.environ.setdefault(_key.strip(), _val.strip())
API_KEY = os.environ.get("PROMA_API_KEY", "")
BASE_URL = os.environ.get("PROMA_BASE_URL", "https://api.deepseek.com")

SYSTEM_PROMPT = """你是一个知识结构师。请从以下帖子中提取核心观点，生成一个知识文件。

输出格式必须是合法的 Markdown，包含以下结构：

```markdown
# {标题}

**一句话**：{核心判断，≤50字}

## 核心观点

{3-5句话完整表述核心论点}

## 关键论据

- 论据1
- 论据2
- 论据3

## 推理链

{钱→政策→产业→情绪的传导路径，或者事物发展的因果链条}

## 反证与风险

- 反证1：什么情况下这个判断会错
- 风险1：这个观点的边界和盲区

## 观察指标

{可以观察什么来验证或推翻这个观点}

## 适用边界

- 什么时候适用：{场景}
- 什么时候不适用：{场景}
- 框架的局限性：{局限}

## 在体系中的位置

- 系统层：{macro-worldview|market-structure|industry-map|trading-system|method-reflection}
- 关联概念：{相关术语}

## 证据溯源

- 原帖链接：{URL}
- 发布时间：{时间}
- 证据等级：A
- 来源状态：primary_verified
```

只输出 Markdown，不要解释。确保 Markdown 格式正确。"""


def load_s_tier_posts() -> list[dict]:
    """Load S-tier posts from quality scores and bulk data."""
    quality = {}
    for line in QUALITY_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            q = json.loads(line)
            if q["tier"] in ("S", "A"):
                quality[q["post_id"]] = q

    posts = {}
    for line in BULK_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            p = json.loads(line)
            posts[p["post_id"]] = p

    result = []
    for pid, q in sorted(quality.items(), key=lambda x: -x[1]["quality_score"]):
        post = posts.get(pid)
        if post and len(post.get("text", "")) > 100:
            post["_quality"] = q
            result.append(post)

    return result


def llm_extract_knowledge(post: dict) -> str | None:
    """Call LLM to generate a structured knowledge file."""
    text = post.get("text", "")[:8000]
    title = post.get("title", "") or text[:30]

    prompt = f"""帖子链接: https://xueqiu.com/7143769715/{post['post_id']}
发布时间: {post.get('time_before', '')}
帖子标题: {title}

帖子正文:
---
{text}
---

请生成知识文件。"""

    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 3072,
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
            content = re.sub(r"^```\w*\n?", "", content)
            content = re.sub(r"\n```$", "", content)
        return content
    except Exception as exc:
        print(f"      ❌ LLM: {exc}")
        return None


def slugify(title: str) -> str:
    """Convert a title to a clean kebab-case filename."""
    # Remove HTML tags
    slug = re.sub(r"<[^>]+>", "", title)
    # Remove URLs
    slug = re.sub(r"https?://\S+", "", slug)
    # Keep only Chinese chars, letters, digits, spaces
    slug = re.sub(r"[^\w\s一-鿿-]", "", slug.lower())
    # Collapse spaces and hyphens
    slug = re.sub(r"[-\s]+", "-", slug)
    slug = slug.strip("-")
    if len(slug) > 40:
        slug = slug[:40].rstrip("-")
    return slug or f"post-{title[:10]}"


def main() -> int:
    if not API_KEY:
        print("❌ 未设置 API Key")
        return 1

    KNOWLEDGE.mkdir(parents=True, exist_ok=True)

    print("📚 加载 S+A 级帖子…")
    posts = load_s_tier_posts()
    s_count = sum(1 for p in posts if p["_quality"]["tier"] == "S")
    a_count = sum(1 for p in posts if p["_quality"]["tier"] == "A")
    print(f"   S 级: {s_count} | A 级: {a_count}")

    # Phase 1: All S-tier + top A-tier (up to 50 total)
    targets = [p for p in posts if p["_quality"]["tier"] == "S"]
    targets += [p for p in posts if p["_quality"]["tier"] == "A"][:35]
    print(f"   LLM 提取目标: {len(targets)} 篇\n")

    generated = 0
    for i, post in enumerate(targets, 1):
        q = post["_quality"]
        pid = post["post_id"]
        title = (post.get("title") or post.get("text", "")[:30]).strip()[:50]
        print(f"   [{i}/{len(targets)}] S{q['tier']} {pid}: {title[:40]}", end=" ", flush=True)

        md = llm_extract_knowledge(post)
        if not md:
            print("⏭️")
            continue

        filename = slugify(title) or f"post-{pid}"
        filepath = KNOWLEDGE / f"{filename}.md"
        filepath.write_text(md, encoding="utf-8")
        generated += 1
        print(f"✅ → knowledge/{filename}.md")

        if i % 10 == 0:
            print(f"      💾 {generated}/{i} 完成")

        time.sleep(0.5)

    # Build index
    if generated > 0:
        index_lines = ["# 知识库索引\n", f"生成时间: {time.strftime('%Y-%m-%d %H:%M')}\n", f"总文件数: {generated}\n", ""]
        for path in sorted(KNOWLEDGE.glob("*.md")):
            if path.name == "INDEX.md": continue
            first_line = path.read_text(encoding="utf-8").split("\n")[0].replace("# ", "")
            index_lines.append(f"- [{first_line}]({path.name})")
        (KNOWLEDGE / "INDEX.md").write_text("\n".join(index_lines), encoding="utf-8")

    print(f"\n✅ 生成 {generated} 篇知识文件 → knowledge/")
    print(f"   索引: knowledge/INDEX.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
