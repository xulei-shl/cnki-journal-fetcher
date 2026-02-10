# CLAUDE.md

## 概述

面向图书馆学研究者的学术期刊论文自动化管理系统，支持多源期刊获取（CNKI、人大报刊复印资料、独立网站），定期获取、筛选、总结和管理期刊论文数据。

## 核心架构

### 工作流程

```
lis-journals-fetcher (Skill) 触发
  ↓
调用对应类型爬虫（cnki/rdfybk/lis_spider.py）爬取论文 → 输出 JSON 文件
  ↓
paper-filter (Agent) 智能标注相关论文
  ↓
用户可手动调整标注结果
  ↓
filter_papers.py 生成筛选文件 (filtered.json)
  ↓
paper-summarizer (Agent) 生成总结报告 (summary.md)
  ↓
memory-updater-agent (可选) 更新研究兴趣关键词
```

### 组件关系

| 类型 | 名称 | 路径 | 职责 |
|------|------|------|------|
| Skill | lis-journals-fetcher | `.claude/skills/lis-journals-fetcher/` | 主流程控制：获取期刊论文 |
| Skill | memory-updater | `.claude/skills/memory-updater/` | 更新 MEMORY.md 研究关键词 |
| Agent | cnki-spider-agent | `.claude/agents/cnki-spider-agent.md` | CNKI期刊论文爬取 |
| Agent | rdfybk-spider-agent | `.claude/agents/rdfybk-spider-agent.md` | 人大报刊复印资料爬取 |
| Agent | lis-spider-agent | `.claude/agents/lis-spider-agent.md` | 独立网站期刊爬取 |
| Agent | paper-filter | `.claude/agents/paper-filter.md` | 根据 MEMORY.md 筛选标注论文 |
| Agent | paper-summarizer | `.claude/agents/paper-summarizer.md` | 生成论文总结报告 |
| Agent | memory-updater-agent | `.claude/agents/memory-updater-agent.md` | 执行 MEMORY.md 更新 |

## 常用命令

### 爬取期刊论文

**CNKI 期刊**（以中国图书馆学报为例）：
```bash
# 爬取单期论文（快速模式，不获取摘要）
python .claude/skills/lis-journals-fetcher/scripts/cnki_spider.py \
  -u "https://navi.cnki.net/knavi/journals/ZGTS/detail" \
  -y 2026 -i 6 --no-details \
  -o outputs/中国图书馆学报/2026-6.json

# 爬取论文并获取摘要详情（较慢）
python .claude/skills/lis-journals-fetcher/scripts/cnki_spider.py \
  -u "https://navi.cnki.net/knavi/journals/ZGTS/detail" \
  -y 2026 -i 6 -d \
  -o outputs/中国图书馆学报/2026-6.json
```

**其他类型期刊**（人大报刊、独立网站）：用法类似，使用对应的 `rdfybk_spider.py` 或 `lis_spider.py`

### 筛选论文

```bash
# 从标注文件中筛选相关论文
python .claude/skills/lis-journals-fetcher/scripts/filter_papers.py \
  -i outputs/中国图书馆学报/2026-6.json
```

### 安装依赖

```bash
# 安装 Python 依赖
pip install -r .claude/skills/lis-journals-fetcher/scripts/requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

## 关键文件

| 文件 | 用途 |
|------|------|
| `MEMORY.md` | 用户研究兴趣配置，paper-filter 使用此文件判断论文相关性 |
| `.claude/skills/lis-journals-fetcher/reference/journals-list/{类型}-期刊信息.md` | 各类型期刊列表和爬取状态记录 |
| `outputs/{期刊名}/{年-期}.json` | 原始论文数据（含 interest_match 标注） |
| `outputs/{期刊名}/{年-期}-filtered.json` | 筛选后的相关论文 |
| `outputs/{期刊名}/{年-期}-summary.md` | 论文总结报告 |

## 数据格式

### 论文 JSON 格式

```json
[
  {
    "year": 2025,
    "issue": 6,
    "title": "论文标题",
    "author": "作者1; 作者2",
    "pages": "1-12",
    "abstract_url": "https://...",
    "abstract": "摘要内容（可选）",
    "interest_match": true,
    "match_reasons": ["知识组织", "元数据"],
    "relevance_score": 0.85
  }
]
```

### paper-filter 添加的字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `interest_match` | boolean | 论文是否与用户兴趣相关 |
| `match_reasons` | string[] | 匹配的关键词列表 |
| `relevance_score` | float | 相关度分数 (0-1) |

## 开发注意事项

1. **默认使用异步模式** - 各爬虫脚本（cnki/rdfybk/lis_spider.py）默认使用异步并发爬取，性能提升约 2.5x

2. **交互限制** - 在人工修改确认步骤（步骤 9）中需特别注意交互方式，确保正确处理用户输入

3. **目录检查** - 执行爬虫前必须先检查并创建输出目录，避免失败后重复执行

4. **无摘要情况** - abstract 字段可能为空，paper-summarizer 需优雅处理此情况

5. **paper-filter 必跳过确认** - 当被 lis-journals-fetcher 自动调用时需跳过确认步骤

6. **错误处理机制** - SKILL 中包含完善的回退机制，当爬取失败时提供多种处理选项（尝试上一期、手动输入、跳过等）

7. **MEMORY.md 更新条件** - 仅在用户实际修改了论文相关性标签时才触发更新，避免不必要的修改

8. **期刊状态管理** - 期刊信息文件中的"上次获取年间"是核心状态标识，影响智能推荐算法
