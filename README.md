# 冰冰小美框架 · bingbingxiaomei Framework

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.0.0-blue)](changelog.md)
[![Claims](https://img.shields.io/badge/claims-10,764-brightgreen)](data/claims.jsonl)
[![Quality](https://img.shields.io/badge/quality-97%25-success)](corpus/quality_check.py)

**一个证据型人物知识体系 AI Skill。** 基于雪球用户「冰冰小美」（UID 7143769715）的 10,745 篇公开帖子，通过全量采集、质量分级、表达 DNA 分析和 LLM 结构化提取，构建了可查询、可追溯、自带反证与失效条件的知识系统。

**An evidence-graded persona knowledge system.** Distills 10,745 public posts from Xueqiu user 冰冰小美 into a queryable knowledge base with structured claims, source tracing, expression DNA profiling, and counterevidence-aware reasoning — designed as an AI Skill that speaks in her voice while respecting evidential boundaries.

> ⚠️ 本项目不代表「冰冰小美」本人，不声称获得其授权，不构成投资建议。所有分析应回到原始公开来源、发布时间、市场背景和证据等级中理解。

---

## 数据规模

| 数据 | 数量 | 说明 |
|------|------|------|
| 原始帖子 | **10,745** 篇 | API 全量采集，覆盖 ~2022-2026 |
| 结构化观点卡 | **10,764** 条 | 含 20 条 V1 手写精修 + 843 条 LLM 深度提取 |
| 来源登记 | **10,745** 条 | 每条含 URL、发布时间、核验状态 |
| 知识文件 | **23** 篇 | 8 篇手写核心 + 13 篇 LLM 结构化初稿 + 2 篇框架文档 |
| 表达 DNA 分析 | **2,475,463** 字 | 词汇、句式、节奏、视角四维指纹 |

### 证据分级

| 等级 | 数量 | 含义 |
|------|------|------|
| **A** 级 | 844 | 原文已验证，可确认全文语境 |
| **B** 级 | 1,829 | 搜索索引交叉验证，全文未稳定打开 |
| **D** 级 | 6,766 | 第三方整理或用户侧材料复现 |
| **U** 级 | 1,325 | 未归因，待恢复或仅体系线索 |

### 质量分级

| 等级 | 数量 | 用途 |
|------|------|------|
| **S** 级 | 15 | 核心框架文 — 深度知识提取 |
| **A** 级 | 2,076 | 结构化观点 — 反证与失效条件 |
| **B** 级 | 7,730 | 自动归纳 + 语言 DNA |
| **C** 级 | 923 | 语言 DNA 素材 — 零丢弃 |

---

## 知识体系 · Knowledge Map

```
顶层世界观    国运 → AI-美元战略 → 中央加杠杆
    ↓
宏观传导      三层流动性 · 宏观风险清单
    ↓
市场结构      亏钱效应 · 金融三功能 · 信息金融意义
    ↓
产业映射      房地产→科技 · AI与金融 · 猪周期 · 汽车新国标
    ↓
交易执行      三要素联动 · 买入不败 · 防守减仓
    ↓
方法反思      历史危机类比 · 当前市场分析合同
```

完整知识文件见 [`knowledge/INDEX.md`](knowledge/INDEX.md)。

---

## 能做什么

- 🔍 **证据检索**：按关键词、证据等级、系统层检索观点卡，区分作者原话、整理者归纳和 Skill 推断
- 🏗️ **结构化回答**：历史观点 → 出处+时间+等级+推理链+反证；当前市场 → 先联网核验事实 → 再映射框架
- 🧬 **表达 DNA**：基于 247 万字语料统计的词汇、句式、节奏、视角指纹，指导角色扮演风格
- ⚠️ **风险边界**：每条观点附带反证、失效条件和观察指标，不被叙事裹挟
- 🔗 **全文检索**：`query_evidence.py --fulltext "关键词"` 直接搜索原始帖子全文
- 🤖 **自动化管线**：API 发现 → 质量分级 → LLM 提取 → 校验入库，全流程脚本化

---

## 快速开始

```bash
# 检索观点
python3 scripts/query_evidence.py "三要素" --json
python3 scripts/query_evidence.py "流动性" --level A

# 全文检索原始帖子
python3 scripts/query_evidence.py "中央加杠杆" --fulltext --context 300

# 校验数据
python3 scripts/validate_claims.py
python3 scripts/audit_coverage.py --json

# 质量门
python3 corpus/quality_check.py SKILL.md

# 全量测试
python3 -m unittest discover -s tests -p 'test_*.py'
```

## 自动化采集管线

```bash
# 一次性设置
pip3 install playwright browser-cookie3 && python3 -m playwright install chromium
cp .env.example .env   # 编辑 .env 填入 API Key

# 全量发现（556 页，~3分钟）
python3 scripts/bulk_ingest.py --phase 1

# 质量分级 + DNA 分析
python3 scripts/quality_score.py
python3 scripts/analyze_style.py

# 知识文件生成（S+A 级 → knowledge/）
python3 scripts/build_knowledge_files.py
```

---

## 项目结构

```
bingbingxiaomei-framework/
├── SKILL.md                     # AI Skill 核心（5-Surface V2, 315行）
├── README.md                    # 本文件
├── changelog.md                 # 版本日志
├── .env.example                 # 环境变量模板
├── knowledge/                   # 知识文件（23篇）
│   ├── INDEX.md                 #   知识库索引
│   ├── mental-models.md         #   心智模型速查
│   ├── expression-dna.md        #   表达 DNA 指南
│   ├── trading-three-elements.md #  核心概念 × 8
│   ├── loss-effect.md
│   ├── central-leverage.md
│   ├── liquidity-three-layers.md
│   ├── national-fortune.md
│   ├── finance-three-functions.md
│   ├── property-tech-cycle.md
│   ├── pig-cycle.md
│   └── (13篇 LLM 结构化初稿)
├── data/
│   ├── claims.jsonl             # 结构化观点卡（10,764条）
│   ├── sources.jsonl            # 来源登记（10,745条）
│   ├── unresolved-sources.jsonl # 未解来源
│   └── style_profile.json       # 表达 DNA 指纹
├── scripts/                     # 工具链（11个脚本）
│   ├── query_evidence.py        #   证据检索 + 全文搜索
│   ├── validate_claims.py       #   数据校验
│   ├── bulk_ingest.py           #   全量 API 采集
│   ├── build_knowledge.py       #   LLM 深度提取
│   ├── build_knowledge_files.py #   知识文件生成
│   ├── quality_score.py         #   质量分级
│   ├── analyze_style.py         #   表达 DNA 分析
│   └── ...
├── corpus/                      # 语料质控
│   └── quality_check.py         #   SKILL.md 8维度质量门
├── references/                  # 参考文档
│   ├── knowledge-map.md
│   ├── evidence-rules.md
│   ├── contradictions.md
│   ├── coverage-gaps.md
│   ├── concepts/                #   体系概念
│   ├── timelines/               #   观点时间线
│   └── research/                #   蒸馏日志
├── tests/                       # 单元测试（25个）
└── examples/                    # 使用示例
```

---

## 证据等级

| 等级 | 含义 | 回答措辞 |
|------|------|---------|
| **A** | 已直接打开并核验一级来源全文或足够上下文 | "我在某日原帖明确写过…" |
| **B** | 搜索索引可交叉验证，全文未稳定打开 | "搜索索引显示，某日原帖的核心线索是…" |
| **C** | 两个以上独立二手来源一致复现 | "多个整理来源一致指向…" |
| **D** | 单一用户侧整理或第三方知识库复现 | "现有整理材料显示…" |
| **U** | 未归因、可能删除/锁定或仅为体系线索 | "这条先保留为无来源线索" |

> 证据等级描述的是"这句话能否归到作者及其原始语境"，不是观点是否正确。

---

## 版权与侵权处理

本项目结构化数据、证据分级、分析框架、脚本、测试和 Skill 组织方式以 MIT License 发布。**MIT 不覆盖第三方内容**——第三方公开内容归各自权利人所有。详见 [LICENSE-SCOPE.md](LICENSE-SCOPE.md)。

如权利人认为存在侵权，请通过 GitHub Issue 联系维护者，附权利人身份、争议链接、权利依据和处理方式。收到有效通知后优先临时隐藏争议内容，复核后处理。

---

<div align="center">

Copyright (c) 2026 Mon · MIT License

*心中无牛熊，唯有纪律坚。*

</div>
