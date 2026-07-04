# 蒸馏日志：从语料到知识

> 记录从原始帖子中提炼知识文件的过程——哪些帖子被深度提取、哪些概念被建立、哪些缺口待补。

## 语料来源

| 来源 | 数量 | 时间 | 采集方式 |
|------|------|------|---------|
| 雪球用户时间线 API | 10,745 帖 | ~2022-2026 | `bulk_ingest.py --phase 1` (556 页) |
| 用户侧整理材料 | 部分 | 2026-06 | 脱敏笔记 |
| 第三方知识库 bbxmkb.cn | 概念图谱 | 2026 | Daniel 整理 |

## 蒸馏批次

### Batch 1: V1 手写 claims（2026-06-24）

从已有材料中手工提取 20 条结构化 claims：

- `claim-identity-homepage` — 身份入口
- `claim-ai-dollar-strategy` (A级) — 384549129
- `claim-ai-finance-bound` (D级) — 387912729
- `claim-macro-risk-checklist` (D级) — 380445909
- `claim-finance-three-functions` (B级) — 384601355
- `claim-property-tech-cycle` (B级) — 384601355
- `claim-three-elements` (U级) — 未恢复
- `claim-loss-effect` (D级) — bbxmkb.cn
- `claim-liquidity-three-layers` (D级) — bbxmkb.cn
- `claim-central-leverage` (U级) — 待恢复
- `claim-buying-never-loses` (U级) — 待恢复
- `claim-pig-cycle-framework` (D级) — 332245550
- `claim-information-financial-meaning` (D级) — bbxmkb.cn
- `claim-national-fortune` (D级) — bbxmkb.cn
- `claim-crisis-history` (D级) — 387996955
- `claim-current-analysis-contract` (U级) — Skill 自身约束
- `claim-2026-june-margin-crowding` (B级) — 397149143
- `claim-2026-defensive-deleveraging` (B级) — 397804869
- `claim-2026-us10y-risk-line` (B级) — 397936419
- `claim-2026-auto-standard-rotation` (B级) — 398236720

### Batch 2: LLM 深度提取（2026-07-04）

对 844 篇 Tier 1+2 帖做结构化提取：

- 843 篇生成更新 claims（A 级，author_statement，含反证/失效条件）
- 来源：DeepSeek API (`deepseek-chat`)
- 输出：更新 `data/claims.jsonl` 对应条目

### Batch 3: knowledge/ 手写核心文件（2026-07-04）

基于 V1 claims 手写 5 篇核心知识文件：

| 文件 | 对应 claim | 证据等级 | 来源 |
|------|-----------|---------|------|
| `knowledge/trading-three-elements.md` | claim-three-elements | U | 第三方整理 |
| `knowledge/loss-effect.md` | claim-loss-effect | D | bbxmkb.cn |
| `knowledge/central-leverage.md` | claim-central-leverage | U | 体系线索 |
| `knowledge/liquidity-three-layers.md` | claim-liquidity-three-layers | D | bbxmkb.cn |
| `knowledge/national-fortune.md` | claim-national-fortune | D | bbxmkb.cn |

### Batch 4: knowledge/ LLM 初稿（2026-07-04）

对 42 篇 S+A 级帖生成结构化知识文件：

- 13 篇成功生成（`scripts/build_knowledge_files.py`）
- 29 篇因 LLM 超时/错误放弃
- 来源：DeepSeek API (`deepseek-chat`)
- 状态：AI 辅助初稿，核心观点来自原文，反证/指标/边界含 AI 推演，待人工审核

## 已知缺口

- ~~三要素最早成形帖的原始雪球状态 ID~~ → 2026-07-04 通过全文检索恢复：`272355561` (2023-12-26) + `266484468` (2023-11-11) + `286345052` (2024-04-16)。可升级 claim-three-elements 为 B 级。
- 中央加杠杆系列帖的完整时间链
- 2023 年牛市起点原始预测帖
- 专栏目录 2023-2025 的逐条恢复
- 评论、图片、直播、播客、转发附言和已删除内容

## 下次蒸馏计划

- [ ] 对 S 级 15 篇做人工逐篇审核（标注原文 vs LLM 推演边界）
- [ ] 补充"金融三功能""产业映射""猪周期"的 knowledge/ 文件
- [ ] 对 S+A 级语料单独跑 `analyze_style.py`（当前 DNA 来自 B+C 级）
