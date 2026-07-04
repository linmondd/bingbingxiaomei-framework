#!/usr/bin/env python3
"""SKILL.md quality gate — 8-dimension auto-check.

Usage:
    python corpus/quality_check.py SKILL.md           # Default report
    python corpus/quality_check.py SKILL.md --json    # JSON output
    python corpus/quality_check.py SKILL.md --strict  # Exit 1 on any warning

Dimensions:
    1. Architecture: 5-Surface structure completeness
    2. Safety: Red lines + yellow lines + disclaimer
    3. Evidence: A/B/C/D/U grading present and rules defined
    4. Knowledge: Cross-references valid (no broken links)
    5. Expression: DNA rules present + backed by data
    6. Workflow: Agentic protocol defined
    7. Data: Claims/sources/knowledge file counts reasonable
    8. Boundaries: Coverage gaps + limitations documented
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_skill(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def check_architecture(text: str) -> dict:
    """Check 5-Surface structure."""
    surfaces = {
        "routing": "路由声明" in text or "Routing Surface" in text,
        "contract": "契约" in text or "Contract Surface" in text,
        "runtime": "运行时资源" in text or "Runtime Boundary" in text,
        "safety": "安全边界" in text or "Safety Surface" in text,
        "expression": "表达 DNA" in text or "Expression",
    }
    score = sum(surfaces.values()) * 20
    return {
        "name": "Architecture (5-Surface)",
        "score": score,
        "max": 100,
        "details": surfaces,
        "pass": score >= 80,
    }


def check_safety(text: str) -> dict:
    """Check red lines, yellow lines, disclaimer."""
    checks = {
        "has_red_lines": "红线" in text or "绝对禁止" in text,
        "has_yellow_lines": "黄线" in text or "条件限制" in text,
        "has_disclaimer": "不构成投资建议" in text,
        "has_no_predict": "不得预测" in text or "不得给出确定性" in text,
        "has_no_impersonate": "不得冒充" in text or "不是冰冰小美本人" in text,
    }
    score = sum(checks.values()) * 20
    return {
        "name": "Safety (Red/Yellow/Disclaimer)",
        "score": score,
        "max": 100,
        "details": checks,
        "pass": score >= 80,
    }


def check_evidence(text: str) -> dict:
    """Check evidence grading."""
    levels = ["A", "B", "C", "D", "U"]
    checks = {
        "levels_defined": all(l in text for l in ["证据等级", "A", "B", "U"]),
        "rules_linked": "evidence-rules" in text,
        "source_tracing": "来源追溯" in text or "原帖链接" in text,
        "u_level_handling": "无来源" in text or "U 级" in text or "未归因" in text,
    }
    score = sum(checks.values()) * 25
    return {
        "name": "Evidence (A/B/C/D/U)",
        "score": score,
        "max": 100,
        "details": checks,
        "pass": score >= 75,
    }


def check_knowledge_links(text: str) -> dict:
    """Check knowledge file references."""
    # Extract all knowledge/*.md references
    refs = set(re.findall(r"knowledge/[\w\-一-鿿]+\.md", text))
    broken = []
    valid = []
    for ref in refs:
        path = ROOT / ref
        if path.exists():
            valid.append(ref)
        else:
            broken.append(ref)

    score = 100 if not broken else max(0, 100 - len(broken) * 15)
    return {
        "name": f"Knowledge Links ({len(valid)} ok / {len(broken)} broken)",
        "score": score,
        "max": 100,
        "details": {"valid": valid, "broken": broken},
        "pass": len(broken) == 0,
    }


def check_expression(text: str) -> dict:
    """Check expression DNA rules."""
    checks = {
        "has_dna_section": "表达 DNA" in text,
        "has_style_profile": "style_profile" in text or "2,475,463" in text or "2475463" in text,
        "has_sentence_rules": "句长" in text or "句式" in text,
        "has_vocab_rules": "高频词" in text or "词汇" in text,
        "has_anti_ai": "说白了" in text or "意味着" in text or "AI 味" in text or "禁止" in text,
    }
    score = sum(checks.values()) * 20
    return {
        "name": "Expression DNA",
        "score": score,
        "max": 100,
        "details": checks,
        "pass": score >= 60,
    }


def check_workflow(text: str) -> dict:
    """Check agentic protocol / workflow."""
    checks = {
        "has_classify": "问题分类" in text or "Step 1" in text or "识别类型" in text,
        "has_history_flow": "历史观点" in text,
        "has_market_flow": "当前市场" in text,
        "has_output_skeleton": "回答骨架" in text or "推理链" in text or "Step 3" in text,
    }
    score = sum(checks.values()) * 25
    return {
        "name": "Workflow (Agentic Protocol)",
        "score": score,
        "max": 100,
        "details": checks,
        "pass": score >= 75,
    }


def check_data_health() -> dict:
    """Check data file sizes / counts."""
    claims = ROOT / "data" / "claims.jsonl"
    sources = ROOT / "data" / "sources.jsonl"
    knowledge = ROOT / "knowledge"

    n_claims = sum(1 for _ in open(claims, encoding="utf-8")) if claims.exists() else 0
    n_sources = sum(1 for _ in open(sources, encoding="utf-8")) if sources.exists() else 0
    n_knowledge = len(list(knowledge.glob("*.md"))) if knowledge.exists() else 0

    checks = {
        "claims_exist": n_claims > 0,
        "claims_reasonable": n_claims >= 100,
        "sources_exist": n_sources > 0,
        "knowledge_exist": n_knowledge >= 5,
    }
    score = sum(checks.values()) * 25
    return {
        "name": f"Data Health (claims:{n_claims} src:{n_sources} k:{n_knowledge})",
        "score": score,
        "max": 100,
        "details": {"n_claims": n_claims, "n_sources": n_sources, "n_knowledge": n_knowledge},
        "pass": score >= 50,
    }


def check_boundaries(text: str) -> dict:
    """Check coverage gaps + limitations."""
    checks = {
        "has_gaps": "缺口" in text or "coverage-gaps" in text,
        "has_limitations": "局限" in text or "失效条件" in text or "边界" in text,
        "has_incomplete_notice": "已经收齐" not in text,
        "has_takedown": "下架" in text or "takedown" in text or "删除" in text,
    }
    score = sum(checks.values()) * 25
    return {
        "name": "Boundaries & Limitations",
        "score": score,
        "max": 100,
        "details": checks,
        "pass": score >= 50,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_path", nargs="?", default="SKILL.md")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    text = load_skill(args.skill_path)
    checks = [
        check_architecture(text),
        check_safety(text),
        check_evidence(text),
        check_knowledge_links(text),
        check_expression(text),
        check_workflow(text),
        check_data_health(),
        check_boundaries(text),
    ]

    total = sum(c["score"] for c in checks)
    max_score = sum(c["max"] for c in checks)
    passed = sum(1 for c in checks if c["pass"])
    pct = round(total / max_score * 100)

    if args.json:
        print(json.dumps({
            "total_score": total,
            "max_score": max_score,
            "percentage": pct,
            "passed": passed,
            "total_checks": len(checks),
            "checks": checks,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"{'='*55}")
        print(f"  SKILL.md 质量检查 — {pct}% ({passed}/{len(checks)} 项通过)")
        print(f"{'='*55}")
        for c in checks:
            icon = "✅" if c["pass"] else "⚠️"
            print(f"  {icon} {c['name']}: {c['score']}/{c['max']}")
        print(f"{'='*55}")

    if args.strict:
        return 0 if passed == len(checks) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
