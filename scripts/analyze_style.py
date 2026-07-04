#!/usr/bin/env python3
"""Expression DNA analysis — vocabulary, sentence patterns, rhythm fingerprint.

Reads data/dna_corpus.jsonl (C+B tier posts, ~8,400 posts) and extracts:
1. High-frequency vocabulary (top 200 words, excluding stopwords)
2. Sentence pattern features (length distribution, question ratio,转折词 frequency)
3. Rhythm fingerprint (paragraph structure, pacing markers)
4. Signature expression templates (recurring phrase patterns)

Output:
    data/style_profile.json — structured DNA profile
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DNA_FILE = DATA / "dna_corpus.jsonl"
OUTPUT = DATA / "style_profile.json"

# ── stopwords ────────────────────────────────────────────────────────

CN_STOPWORDS = set("""
的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你
会 着 没有 看 好 自己 这 他 她 它 们 那 些 什么 而 为 所以 因为
但是 如果 虽然 可以 觉得 知道 这个 那个 还 已经 被 把 让 给 从
与 对 等 之 中 后 及 或 能 吗 呢 吧 啊 呀 哦 嗯 啦 嘛 哈
""".split())

# ── analysis ────────────────────────────────────────────────────────


def load_dna() -> list[str]:
    texts = []
    for line in DNA_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        obj = json.loads(line)
        t = obj.get("text", "")
        if len(t) > 20:
            texts.append(t)
    return texts


def tokenize(text: str) -> list[str]:
    """Simple Chinese tokenizer — split on punctuation, filter short tokens."""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Split on Chinese/English boundaries
    tokens = re.findall(r"[一-鿿]{2,}|[a-zA-Z]{2,}|\d+", text)
    return [t for t in tokens if t not in CN_STOPWORDS and len(t) >= 2]


def vocab_analysis(texts: list[str]) -> dict:
    """Top 200 words, word frequency distribution."""
    counter = Counter()
    for text in texts:
        counter.update(tokenize(text))
    top200 = counter.most_common(200)
    return {
        "total_unique_words": len(counter),
        "total_word_occurrences": sum(counter.values()),
        "top200": [{"word": w, "count": c} for w, c in top200],
        "top50_words": [w for w, _ in top200[:50]],
    }


def sentence_analysis(texts: list[str]) -> dict:
    """Sentence length distribution, question ratio, key transitions."""
    all_lengths = []
    question_count = 0
    total_sentences = 0
    transition_counter = Counter()

    transition_words = [
        "但是", "然而", "所以", "因此", "不过", "而且", "况且", "虽然",
        "如果", "因为", "于是", "然后", "接着", "最后", "首先", "其次",
        "另外", "同时", "反而", "其实", "当然", "毕竟", "总之",
    ]

    for text in texts:
        # Split into sentences
        sentences = re.split(r"[。！？\n;；!?]+", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 2]
        total_sentences += len(sentences)

        for s in sentences:
            all_lengths.append(len(s))
            if s.endswith("?") or s.endswith("？"):
                question_count += 1
            for tw in transition_words:
                if tw in s:
                    transition_counter[tw] += 1

    if not all_lengths:
        return {}

    all_lengths.sort()
    n = len(all_lengths)

    return {
        "total_sentences": total_sentences,
        "avg_sentence_length": round(sum(all_lengths) / n, 1),
        "median_sentence_length": all_lengths[n // 2],
        "sentence_length_p25": all_lengths[n // 4],
        "sentence_length_p75": all_lengths[3 * n // 4],
        "sentence_length_p90": all_lengths[9 * n // 10],
        "question_ratio": round(question_count / max(total_sentences, 1), 4),
        "top_transitions": transition_counter.most_common(20),
    }


def rhythm_analysis(texts: list[str]) -> dict:
    """Paragraph structure, pacing markers, emoji/empty-line usage."""
    total_paragraphs = 0
    para_lengths = []
    empty_line_count = 0
    br_count = 0
    numbered_list_count = 0

    for text in texts:
        paragraphs = text.split("\n")
        for p in paragraphs:
            cleaned = re.sub(r"<[^>]+>", "", p).strip()
            if not cleaned:
                empty_line_count += 1
                continue
            para_lengths.append(len(cleaned))
            total_paragraphs += 1

        br_count += text.count("<br/>") + text.count("<br>")
        if re.search(r"[\d一二三四五六七八九十]+[、.．）\)]", text):
            numbered_list_count += 1

    if not para_lengths:
        return {}

    para_lengths.sort()
    n = len(para_lengths)
    return {
        "total_paragraphs": total_paragraphs,
        "avg_paragraph_length": round(sum(para_lengths) / n, 1),
        "median_paragraph_length": para_lengths[n // 2],
        "empty_line_rate": round(empty_line_count / max(total_paragraphs + empty_line_count, 1), 4),
        "br_tags_total": br_count,
        "numbered_list_ratio": round(numbered_list_count / max(len(texts), 1), 4),
    }


def signature_phrases(texts: list[str]) -> list[dict]:
    """Find recurring 3-5 character phrase patterns."""
    phrase_counter = Counter()
    for text in texts:
        text = re.sub(r"<[^>]+>", "", text)
        # Extract 3-6 char Chinese phrases
        phrases = re.findall(r"[一-鿿]{3,6}", text)
        for p in phrases:
            if p not in CN_STOPWORDS:
                phrase_counter[p] += 1

    # Filter: phrases that appear >10 times
    signatures = [
        {"phrase": p, "count": c}
        for p, c in phrase_counter.most_common(500)
        if c > 10
    ]
    return signatures


# ── perspective analysis ─────────────────────────────────────────────

def perspective_analysis(texts: list[str]) -> dict:
    """Estimate first-person pronoun density, assertion markers, hedging."""
    total_chars = sum(len(t) for t in texts)
    if not total_chars: return {}

    patterns = {
        "first_person": ["我", "我的", "窝"],
        "assertion": ["一定", "必须", "绝对", "无疑", "显然", "当然"],
        "hedging": ["可能", "也许", "或许", "大概", "应该", "估计"],
        "numbers": re.findall,  # special handling
        "question_words": ["为什么", "怎么", "什么", "如何", "是否"],
    }

    counts = {}
    for key, words in patterns.items():
        if key == "numbers":
            counts[key] = sum(1 for t in texts for _ in re.findall(r"\d+\.?\d*%?", t))
        else:
            counts[key] = sum(t.count(w) for t in texts for w in words)

    return {
        "total_chars": total_chars,
        "density_per_10k": {
            k: round(v * 10000 / total_chars, 1) for k, v in counts.items()
        },
    }


# ── main ─────────────────────────────────────────────────────────────


def main() -> int:
    if not DNA_FILE.exists():
        print("❌ 请先运行 quality_score.py 生成 dna_corpus.jsonl")
        return 1

    print("🧬 加载 DNA 语料…")
    texts = load_dna()
    print(f"   {len(texts)} 帖，{sum(len(t) for t in texts):,} 字")

    print("📊 词汇分析…")
    vocab = vocab_analysis(texts)

    print("📝 句式分析…")
    sent = sentence_analysis(texts)

    print("🎵 节奏分析…")
    rhythm = rhythm_analysis(texts)

    print("🏷️ 签名短语…")
    sigs = signature_phrases(texts)[:100]

    print("👁️ 视角分析…")
    persp = perspective_analysis(texts)

    profile = {
        "corpus_size": len(texts),
        "corpus_chars": sum(len(t) for t in texts),
        "vocabulary": vocab,
        "sentence_patterns": sent,
        "rhythm": rhythm,
        "signature_phrases": sigs,
        "perspective": persp,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n✅ 风格画像已保存到 {OUTPUT}")

    # Quick summary
    print(f"\n{'='*50}")
    print(f"🧬 表达 DNA 速览")
    print(f"{'='*50}")
    print(f"  总帖数:      {len(texts)}")
    print(f"  总字数:      {profile['corpus_chars']:,}")
    print(f"  独特词汇:    {vocab['total_unique_words']:,}")
    print(f"  平均句长:    {sent.get('avg_sentence_length', '?')} 字")
    print(f"  疑问句比:    {sent.get('question_ratio', '?')}")
    print(f"  平均段长:    {rhythm.get('avg_paragraph_length', '?')} 字")
    print(f"  编号列表比:  {rhythm.get('numbered_list_ratio', '?')}")
    print(f"\n  Top 20 高频词:")
    for w, c in [(item["word"], item["count"]) for item in vocab["top200"][:20]]:
        max_count = vocab["top200"][0]["count"]
        bar = "█" * min(20, c // max(1, max_count // 20))
        print(f"    {w:<10} {c:>6}  {bar}")
    print(f"\n  Top 10 签名短语:")
    for s in sigs[:10]:
        print(f"    {s['phrase']:<10} ×{s['count']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
