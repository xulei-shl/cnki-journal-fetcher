# 图书情报知识 (lis.ac.cn) 期刊爬虫使用说明

## 概述

`lis_spider.py` 是专门用于爬取图书情报知识期刊 (https://www.lis.ac.cn) 论文数据的爬虫脚本。

## 特点

- **直接获取摘要**：无需跳转到详情页，直接从列表页提取摘要
- **自动过滤非论文记录**：自动跳过 "目录" 和 "专题：" 开头的记录
- **年卷期校验**：自动校验年份与卷号的对应关系
- **数据清理**：使用 JSONSanitizer 自动清理特殊字符

## 年卷期对应关系

卷号计算公式：**卷号 = 年份 - 1956**

| 年份 | 卷号 | 期号范围 |
|------|------|----------|
| 2024 | 68 | 1-24 |
| 2025 | 69 | 1-24 |
| 2026 | 70 | 1-24 |

注：
- 该期刊为半月刊，每年出版 24 期
- 支持爬取任意历史年份的数据（如 2010、2020 等）
- 年份上限为当前年份（2026）

## 基本用法

### 爬取单期

```bash
# 爬取 2025 年第 24 期
python .claude/skills/cnki-journals-fetcher/scripts/lis_spider.py -y 2025 -i 24
```

### 爬取多期（范围格式）

```bash
# 爬取 2025 年第 1-3 期
python .claude/skills/cnki-journals-fetcher/scripts/lis_spider.py -y 2025 -i "1-3"
```

### 爬取多期（离散格式）

```bash
# 爬取 2025 年第 1,5,7 期
python .claude/skills/cnki-journals-fetcher/scripts/lis_spider.py -y 2025 -i "1,5,7"
```

### 爬取多期（混合格式）

```bash
# 爬取 2025 年第 1-3,5,7-9 期
python .claude/skills/cnki-journals-fetcher/scripts/lis_spider.py -y 2025 -i "1-3,5,7-9"
```

### 保存到指定路径

```bash
# 保存到指定目录
python .claude/skills/cnki-journals-fetcher/scripts/lis_spider.py -y 2025 -i 24 \
  -o outputs/图书情报知识/2025-24.json
```

## 命令行参数

| 参数 | 说明 | 示例 | 必填 |
|------|------|------|------|
| `-y, --year` | 年份 | `-y 2025` | 是 |
| `-v, --volume` | 卷号（可选，自动校验） | `-v 69` | 否 |
| `-i, --issue` | 期号（支持范围/离散/混合） | `-i "1-3"` | 是 |
| `-o, --output` | 输出文件路径 | `-o results.json` | 否 |
| `-t, --timeout` | 超时时间（毫秒） | `-t 30000` | 否 |
| `--no-headless` | 显示浏览器窗口 | `--no-headless` | 否 |
| `--sync` | 使用同步模式 | `--sync` | 否 |

## 输出数据格式

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
    "doi": "https://doi.org/...",
    "abstract": "摘要内容"
  }
]
```

## URL 构建规则

```
https://www.lis.ac.cn/CN/Y{year}/V{volume}/I{issue}
```

示例：
- 2025年第24期：`https://www.lis.ac.cn/CN/Y2025/V69/I24`
- 2026年第1期：`https://www.lis.ac.cn/CN/Y2026/V70/I1`

## 常见问题

### Q: 为什么不需要指定 URL？

A: lis.ac.cn 的 URL 遵循固定规则，脚本会根据年卷期自动构建。

### Q: 如何验证年卷期参数是否正确？

A: 脚本会自动校验：
- 年份不能超过当前年份（2026）
- 卷号会根据年份自动计算（卷号 = 年份 - 1956）
- 期号必须在 1-24 范围内

### Q: 可以爬取历史年份的数据吗？

A: 可以！支持爬取任意历史年份的数据，例如：
```bash
# 爬取 2020 年第 1 期
python lis_spider.py -y 2020 -i 1

# 爬取 2010 年第 1-6 期
python lis_spider.py -y 2010 -i "1-6"
```

### Q: 被跳过的记录有哪些？

A: 以下类型的记录会被自动跳过：
- 标题为 "目录" 的记录
- 标题以 "专题：" 开头的记录（如 "专题：新质生产力视域下的科研创新与知识转化"）