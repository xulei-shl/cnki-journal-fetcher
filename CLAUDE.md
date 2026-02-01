# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 概述

面向图书馆学研究者的学术期刊论文自动化管理系统，主要用于从 CNKI（中国知网）定期获取、筛选、总结和管理期刊论文数据。

## 核心架构

### 工作流程

```
cnki-journals-fetcher (Skill) 触发
  ↓
cnki_spider.py 爬取论文 → 输出 JSON 文件
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
| Skill | cnki-journals-fetcher | `.claude/skills/cnki-journals-fetcher/` | 主流程控制：获取期刊论文 |
| Skill | memory-updater | `.claude/skills/memory-updater/` | 更新 MEMORY.md 研究关键词 |
| Agent | paper-filter | `.claude/agents/paper-filter.md` | 根据 MEMORY.md 筛选标注论文 |
| Agent | paper-summarizer | `.claude/agents/paper-summarizer.md` | 生成论文总结报告 |
| Agent | memory-updater-agent | `.claude/agents/memory-updater-agent.md` | 执行 MEMORY.md 更新 |

## 常用命令

### 爬取期刊论文

```bash
# 爬取单期论文（快速模式，不获取摘要）
python .claude/skills/cnki-journals-fetcher/scripts/cnki_spider.py \
  -u "https://navi.cnki.net/knavi/journals/ZGTS/detail" \
  -y 2026 -i 6 --no-details \
  -o outputs/中国图书馆学报/2026-6.json

# 爬取论文并获取摘要详情（较慢）
python .claude/skills/cnki-journals-fetcher/scripts/cnki_spider.py \
  -u "https://navi.cnki.net/knavi/journals/ZGTS/detail" \
  -y 2026 -i 6 -d \
  -o outputs/中国图书馆学报/2026-6.json
```

### 筛选论文

```bash
# 从标注文件中筛选相关论文
python .claude/skills/cnki-journals-fetcher/scripts/filter_papers.py \
  -i outputs/中国图书馆学报/2026-6.json
```

### 安装依赖

```bash
# 安装 Python 依赖
pip install -r .claude/skills/cnki-journals-fetcher/scripts/requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

## 关键文件

| 文件 | 用途 |
|------|------|
| `MEMORY.md` | 用户研究兴趣配置，paper-filter 使用此文件判断论文相关性 |
| `.claude/skills/cnki-journals-fetcher/reference/期刊信息.md` | 期刊列表和爬取状态记录 |
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

## 技术栈

- **Python 3.8+**
- **Playwright** - 浏览器自动化爬虫
- **Claude Agent SDK** - Skills 和 Agents 框架

## 开发注意事项

1. **未找到 AGENTS.md** - 本项目未定义通用流程规划文档，各组件工作流程详见各自的 SKILL.md 或 agent 定义文件

2. **默认使用异步模式** - cnki_spider.py 默认使用异步并发爬取，性能提升约 2.5x

3. **交互限制** - 某些交互场景（如步骤 9.2 人工修改确认）严禁使用 AskUserQuestion 工具，需使用文本循环等待

4. **目录检查** - 执行爬虫前必须先检查并创建输出目录，避免失败后重复执行

5. **无摘要情况** - abstract 字段可能为空，paper-summarizer 需优雅处理此情况

6. **paper-filter 必跳过确认** - 当被 cnki-journals-fetcher 自动调用时需跳过确认步骤
