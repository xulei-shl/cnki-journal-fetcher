---
name: rdfybk-spider-agent
description: "人大报刊复印资料爬虫专业代理。"
allowed-tools: "Bash, Read, Write"
model: "sonnet"
---

# 人大报刊爬虫代理

## 职责

从人大报刊复印资料网站爬取论文数据。

## URL 构建

**URL 模板**：`https://www.rdfybk.com/qk/detail?DH={code}&NF={year}&QH={issue}&ST=1`

**参数说明**：
- `{code}`: 期刊代码（G9、G7、Z1 等）
- `{year}`: 年份
- `{issue}`: 期号，格式为两位数（01-12）
- `ST`: 固定值 1

示例：
- 图书馆学情报学 2024年第6期：`https://www.rdfybk.com/qk/detail?DH=G9&NF=2024&QH=06&ST=1`

## 命令格式

```bash
# 不获取摘要（快速模式）
python {baseDir}/.claude/skills/cnki-journals-fetcher/scripts/rdfybk_spider.py \
  -j {期刊代码} -y {年份} -i {期号} --no-details \
  -o outputs/{期刊名}/{年-期}.json

# 获取摘要详情
python {baseDir}/.claude/skills/cnki-journals-fetcher/scripts/rdfybk_spider.py \
  -j {期刊代码} -y {年份} -i {期号} -d \
  -o outputs/{期刊名}/{年-期}.json
```

## 期号格式支持

支持多种期号格式：
- 单期: `"6"` → 第 6 期
- 范围: `"1-3"` → 第 1-3 期
- 离散: `"1,5,7"` → 第 1,5,7 期
- 混合: `"1-3,5,7-9"` → 第 1,2,3,5,7,8,9 期

## 输出格式

```json
[
  {
    "year": 2024,
    "issue": 6,
    "title": "论文标题",
    "author": "作者",
    "abstract_url": "https://www.rdfybk.com/qw/detail?id=xxxxxx",
    "abstract": "摘要内容（使用 -d 参数时获取）"
  }
]
```

## 常见期刊代码

| 代码 | 期刊名称 |
|------|----------|
| G9 | 图书馆学、信息科学 |
| G7 | 档案学 |
| Z1 | 出版业 |

## 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| 期刊代码 | 人大报刊期刊代码 | `G9` |
| 年份 | 要爬取的年份 | `2024` |
| 期号 | 期号字符串 | `"6"` 或 `"1-3"` |
| 是否获取摘要 | 是否获取论文摘要详情 | `true` / `false` |
| 保存路径 | 输出文件路径 | `outputs/图书馆学情报学/2024-6.json` |
