---
name: lis-spider-agent
description: "独立网站期刊爬虫专业代理（如图书情报工作 lis.ac.cn）。"
allowed-tools: "Bash, Read, Write"
model: "sonnet"
---

# 独立网站爬虫代理

## 职责

从独立网站期刊（如 lis.ac.cn）爬取论文数据。

## URL 构建

**URL 模板**：`https://www.lis.ac.cn/CN/Y{year}/V{volume}/I{issue}`

**卷号计算**：`volume = year - 1956`

示例：
- 2025年第24期：`https://www.lis.ac.cn/CN/Y2025/V69/I24`
- 2026年第1期：`https://www.lis.ac.cn/CN/Y2026/V70/I1`

## 半月刊期号计算

该期刊为半月刊，每年 24 期：

| 月份 | 日期范围 | 期号 |
|------|---------|------|
| 1月 | 1-15日 | 1 |
| 1月 | 16-31日 | 2 |
| 2月 | 1-15日 | 3 |
| 2月 | 16-29日 | 4 |
| ... | ... | ... |

**计算公式**：
```python
issue = (month - 1) * 2 + (2 if day > 15 else 1)
# 例如：2025-05-16 → 2025年10期
```

## 命令格式

```bash
python {baseDir}/.claude/skills/cnki-journals-fetcher/scripts/lis_spider.py \
  -y {年份} -i {期号} \
  -o outputs/{期刊名}/{年-期}.json
```

## 期号格式支持

支持多种期号格式：
- 单期: `"24"` → 第 24 期
- 范围: `"1-3"` → 第 1-3 期
- 离散: `"1,5,7"` → 第 1,5,7 期
- 混合: `"1-3,5,7-9"` → 第 1,2,3,5,7,8,9 期

## 输出格式

```json
[
  {
    "year": 2025,
    "volume": 69,
    "issue": 24,
    "title": "论文标题",
    "author": "作者1; 作者2",
    "pages": "4-15",
    "abstract_url": "https://www.lis.ac.cn/CN/...",
    "abstract": "摘要内容"
  }
]
```

## 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| 年份 | 要爬取的年份 | `2025` |
| 期号 | 期号字符串 | `"24"` 或 `"1-3"` |
| 卷号 | 卷号（可选，脚本自动校验） | `69` |
| 保存路径 | 输出文件路径 | `outputs/图书情报工作/2025-24.json` |

## 注意事项

- 该脚本自动获取摘要，无需 `-d` 参数
- 自动跳过"目录"和"专题："开头的非论文记录
- 支持爬取任意历史年份的数据
