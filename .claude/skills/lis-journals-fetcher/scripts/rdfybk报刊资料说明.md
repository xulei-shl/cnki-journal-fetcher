# 人大报刊资料爬虫使用说明

## 概述

人大报刊资料爬虫用于从人大复印报刊资料网站（https://www.rdfybk.com）获取期刊论文信息。

## 文件说明

| 文件 | 说明 |
|------|------|
| `rdfybk_spider.py` | 主爬虫，负责爬取论文列表 |
| `rdfybk_detail.py` | 详情获取模块，负责获取论文摘要 |

## 网址格式

```
https://www.rdfybk.com/qk/detail?DH=G9&NF=2024&QH=06&ST=1
```

**参数说明：**
- `DH`: 期刊代码（如 G9、GQ 等）
- `NF`: 年份
- `QH`: 期号
- `ST`: 固定值 1

## 使用方法

### 基本命令

```bash
# 从项目根目录执行
python .claude/skills/cnki-journals-fetcher/scripts/rdfybk_spider.py -j G9 -y 2024 -i 6 --no-details

# 或进入 scripts 目录执行
cd .claude/skills/cnki-journals-fetcher/scripts
python rdfybk_spider.py -j G9 -y 2024 -i 6 --no-details

# 爬取并获取论文摘要
python .claude/skills/cnki-journals-fetcher/scripts/rdfybk_spider.py -j G9 -y 2024 -i 6 -d
```

### 期号格式

支持多种期号格式：

```bash
# 单期
python .claude/skills/cnki-journals-fetcher/scripts/rdfybk_spider.py -j G9 -y 2024 -i 6

# 范围格式 (1-3期)
python .claude/skills/cnki-journals-fetcher/scripts/rdfybk_spider.py -j G9 -y 2024 -i "1-3"

# 离散格式 (1,5,7期)
python .claude/skills/cnki-journals-fetcher/scripts/rdfybk_spider.py -j G9 -y 2024 -i "1,5,7"

# 混合格式 (1-3,5,7-9期)
python .claude/skills/cnki-journals-fetcher/scripts/rdfybk_spider.py -j G9 -y 2024 -i "1-3,5,7-9"
```

### 其他参数

```bash
# 非无头模式运行（显示浏览器窗口）
python .claude/skills/cnki-journals-fetcher/scripts/rdfybk_spider.py -j G9 -y 2024 -i 6 --no-headless

# 指定输出文件
python .claude/skills/cnki-journals-fetcher/scripts/rdfybk_spider.py -j G9 -y 2024 -i 6 -o outputs/rdfybk/G9/2024-6.json

# 设置超时时间（毫秒）
python .claude/skills/cnki-journals-fetcher/scripts/rdfybk_spider.py -j G9 -y 2024 -i 6 -t 60000

# 使用同步模式（默认异步）
python .claude/skills/cnki-journals-fetcher/scripts/rdfybk_spider.py -j G9 -y 2024 -i 6 --sync

# 设置异步并发数（仅异步模式）
python .claude/skills/cnki-journals-fetcher/scripts/rdfybk_spider.py -j G9 -y 2024 -i "1-6" -c 5
```

## 输出数据格式

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

## 页面元素结构

### 论文列表页

HTML 结构示例：
```html
<tr class="t1">
  <td class="bt">
    <a href="/qw/detail?id=869380" title="论文标题">论文标题</a>
  </td>
  <td><a href="/qw?s0=2&s1=xxx">作者</a></td>
  <td>2024-11</td>
</tr>
```

**提取逻辑：**
- 选择器：`tr.t1` 或 `tr.t2`
- 标题：`td.bt a` 的 `title` 属性
- 作者：第 2 个 `td` 中的文本
- 日期：第 3 个 `td` 中的文本
- 摘要链接：`td.bt a` 的 `href` 属性（拼接完整 URL）

### 摘要详情页

HTML 结构示例：
```html
<span id="astInfo">
  <strong>内容提要：</strong>
  <span>摘要内容...</span>
  <span style="display:none">英文摘要...</span>
</span>
```

**提取逻辑：**
- 选择器：`span#astInfo span:not([style*="display:none"])`
- 需去除 "内容提要：" 前缀

## 常见期刊代码

| 代码 | 期刊名称 |
|------|----------|
| G9 | 图书馆学、信息科学 |
| GQ | 档案学 |

## 注意事项

1. **摘要获取**：使用 `-d` 参数会获取摘要，但会增加请求时间
2. **异步并发**：默认使用异步模式，性能优于同步模式
3. **数据清理**：结果自动调用 `json_sanitizer.py` 进行特殊字符清理
4. **Windows 控制台**：使用 ASCII 兼容的输出标记，避免编码问题
