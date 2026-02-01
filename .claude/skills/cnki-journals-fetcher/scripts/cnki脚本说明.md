# CNKI 期刊论文爬虫

使用 Playwright 实现的中国知网期刊论文爬取工具。

## 功能特性

- ✅ 爬取指定期刊的某一期论文列表
- ✅ 默认获取论文摘要等详细信息（摘要、关键词、DOI、基金、作者详情）
- ✅ **异步并发爬取** - 默认使用异步模式，性能提升 2-3 倍
- ✅ **智能等待策略** - 动态检测元素加载，替代固定延迟
- ✅ **结构化进度输出** - 实时显示爬取进度和 ETA
- ✅ 支持命令行参数配置
- ✅ 结果保存为 JSON 格式

## 安装

1. 安装 Python 3.8+
2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 安装 Playwright 浏览器：
```bash
playwright install chromium
```

## 使用方法

```bash
python cnki_spider.py -u <期刊导航页URL> -y <年份> -i <期号> [选项]
```

### 参数说明

| 参数 | 必填 | 说明 |
|------|------|------|
| `-u, --url` | ✅ | 期刊导航页 URL |
| `-y, --year` | ✅ | 要爬取的年份 |
| `-i, --issue` | ✅ | 要爬取的期号，支持以下格式：<br/>• 单期：`6` (表示第6期)<br/>• 范围：`1-3` (表示第1-3期)<br/>• 离散：`1,5,7` (表示第1,5,7期)<br/>• 混合：`1-3,5,7-9` (表示第1,2,3,5,7,8,9期) |
| `-c, --concurrency` | ❌ | 异步并发数，默认 3（仅异步模式有效） |
| `--sync` | ❌ | 使用同步模式（默认为异步模式） |
| `-d, --details` | ❌ | 是否获取论文摘要（默认：获取） |
| `--no-details` | ❌ | 不获取论文摘要等详细信息 |
| `--no-headless` | ❌ | 显示浏览器窗口进行调试 |
| `-t, --timeout` | ❌ | 超时时间（毫秒），默认 30000 |
| `-o, --output` | ❌ | 输出文件路径，默认 results.json |

### 使用示例

```bash
# ===== 异步模式（默认，推荐） =====

# 基本用法：爬取 2025 年第 6 期论文列表
python cnki_spider.py -u "https://navi.cnki.net/knavi/journals/ZGTS/detail?uniplatform=NZKPT" -y 2025 -i 6

# 指定并发数（默认为3，保守范围2-5）
python cnki_spider.py -u "https://navi.cnki.net/knavi/journals/ZGTS/detail" -y 2025 -i 6 -c 5

# 爬取 2025 年第 1-3 期论文列表（范围格式）
python cnki_spider.py -u "https://navi.cnki.net/knavi/journals/TSQC/detail" -y 2025 -i "5-6"

# 爬取 2025 年第 1,5,7 期论文列表（离散格式）
python cnki_spider.py -u "https://navi.cnki.net/knavi/journals/ZGTS/detail" -y 2025 -i "1,5,7"

# 爬取 2025 年第 1-3,5,7-9 期论文列表（混合格式）
python cnki_spider.py -u "https://navi.cnki.net/knavi/journals/ZGTS/detail" -y 2025 -i "1-3,5,7-9"

# ===== 同步模式 =====

# 使用同步模式（兼容旧版本）
python cnki_spider.py -u "https://navi.cnki.net/knavi/journals/ZGTS/detail" -y 2025 -i 6 --sync

# ===== 其他选项 =====

# 获取论文摘要详情（默认已开启）
python cnki_spider.py -u "https://navi.cnki.net/knavi/journals/ZGTS/detail" -y 2025 -i 6

# 不获取论文摘要详情
python cnki_spider.py -u "https://navi.cnki.net/knavi/journals/ZGTS/detail" -y 2025 -i 6 --no-details

# 非无头模式（显示浏览器），用于调试
python cnki_spider.py -u "https://navi.cnki.net/knavi/journals/ZGTS/detail" -y 2025 -i 6 --no-headless

# 自定义输出文件名
python cnki_spider.py -u "https://navi.cnki.net/knavi/journals/ZGTS/detail" -y 2025 -i 6 -o my_papers.json
```

### 性能对比

| 论文数量 | 同步模式耗时 | 异步模式耗时 (并发3) | 提升比例 |
|----------|--------------|---------------------|----------|
| 10篇     | ~15秒        | ~6秒                | **2.5x** |
| 20篇     | ~30秒        | ~11秒               | **2.7x** |
| 30篇     | ~45秒        | ~16秒               | **2.8x** |

## 输出示例

```json
[
  {
    "year": 2025,
    "issue": 6,
    "title": "基于深度学习的图书馆知识发现研究",
    "author": "张三; 李四; 王五",
    "pages": "1-12",
    "abstract_url": "https://kns.cnki.net/kcms2/article/abstract?uniplatform=NZKPT&...",
    "abstract": "随着人工智能技术的快速发展...",
    "keywords": "深度学习; 知识发现; 图书馆; 数据挖掘",
    "doi": "10.12345/example.2025.06.001",
    "fund": "国家社会科学基金项目(23BTQ012)",
    "authors_detail": "张三（教授），研究方向：数字图书馆；李四（副教授）..."
  }
]
```

## 进度输出示例

异步模式会显示实时进度：

```
  [5/20] [█████████░░░░░░░░░░░░] 25% | ✅4 ❌1 ⏭️0 | ETA:35s | 基于深度学习的图书馆知识...
```

进度条说明：
- `[5/20]` - 当前进度/总数
- `[█████░░░░░░]` - 可视化进度条
- `25%` - 完成百分比
- `✅4` - 成功数量
- `❌1` - 失败数量
- `⏭️0` - 跳过数量
- `ETA:35s` - 预计剩余时间

## 注意事项

1. **并发设置**：建议并发数为 2-5
   - 保守值（2-3）：稳定性高，不易触发反爬
   - 激进值（5-10）：速度快，但可能被限制
2. **频率限制**：请勿过于频繁爬取，以免对服务器造成压力
3. **反爬措施**：如遇到验证码，可能需要登录 CNKI 账号
4. **合法使用**：请确保爬取行为符合 CNKI 的使用条款
5. **异步 vs 同步**：异步模式为默认选项，如需兼容旧版本可使用 `--sync` 参数

## 技术特点

- **异步 I/O**：使用 Playwright Async API，充分利用等待时间
- **智能等待**：动态检测页面元素就绪，避免不必要的固定延迟
- **页面池复用**：预创建页面循环使用，减少资源开销
- **信号量控制**：精确控制并发数，避免资源耗尽

## License

MIT
