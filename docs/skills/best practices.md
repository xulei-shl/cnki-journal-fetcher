
# Skill 编写最佳实践

> 简洁指南，详细的原理说明和高级模式见引用文档。

---

## 1. Frontmatter（元数据）

```yaml
---
name: skill-name              # 必需：小写字母+连字符，最多64字符
description: "功能描述，使用时机"  # 必需，1024字符内，第三人称
# context: fork               # 可选：fork(独立上下文)/stream(共享上下文)
# allowed-tools: "Task, Read, Edit, Write, Bash, Grep, Glob"  # 可选：最小化权限
# model: "sonnet"             # 可选：覆盖默认模型
---
```

### 字段说明

| 字段 | 要求 | 示例 |
|------|------|------|
| `name` | 小写字母、数字、连字符 | `pdf-processing` |
| `description` | 第三人称，包含触发场景 | `处理 PDF 文件，提取文本和表格` |
| `context` | 复杂任务用 fork | `fork` |
| `allowed-tools` | 最小化权限 | `"Task, Read, Edit"` |

---

## 2. Markdown 内容结构

```markdown
# [Skill 名称]

## 概述
[简短目的陈述：此 skill 的功能、何时使用]

## 快速开始
[核心操作示例]

## 指令/工作流
### 步骤 1：[操作名称]
[命令式指令]
### 步骤 2：[操作名称]
[命令式指令]

## 输出格式
[结果模板或格式要求]

## 错误处理
[失败时如何处理]
```

### 结构要点

- **命令式语言**：使用"提取文本"而非"你应该提取文本"
- **路径规范**：使用 `{baseDir}` 和正斜杠，如 `Read {baseDir}/config.json`
- **渐进披露**：详细文档通过引用加载，保持 SKILL.md 简洁

---

## 3. 核心原则

### 3.1 简洁性是关键

上下文窗口有限。审视每个部分：
- "Claude 真的需要这个解释吗？"
- "这段话值得它的 token 成本吗？"

**好的示例**（约50 token）：
```markdown
## 提取 PDF 文本

使用 pdfplumber：
```python
import pdfplumber
with pdfplumber.open("file.pdf") as pdf:
    text = pdf.pages[0].extract_text()
```
```

**避免**（约150 token，冗余）：
```markdown
## 提取 PDF 文本

PDF 是一种常见文件格式，包含文本和图像。要提取文本，需要使用库...
```

### 3.2 设置适当的自由度

| 自由度 | 适用场景 | 示例 |
|--------|----------|------|
| **高** | 多种方法有效、上下文决定 | 代码审查、分析任务 |
| **中** | 有首选模式、允许变化 | 生成报告模板 |
| **低** | 操作脆弱、必须精确 | 数据库迁移、验证脚本 |

**类比**：狭窄的桥（低自由度）vs 开阔的田野（高自由度）

### 3.3 渐进披露模式

保持 SKILL.md 在 500 行以内，详细内容引用外部文件：

```markdown
## 高级功能

**表单填写**：参见 [FORMS.md](FORMS.md)
**API 参考**：参见 [REFERENCE.md](REFERENCE.md)
**示例**：参见 [EXAMPLES.md](EXAMPLES.md)
```

---

## 4. 命名规范

### 4.1 Skill 名称

| 类型 | 示例 |
|------|------|
| **推荐（动名词）** | `pdf-processing`、`code-review`、`data-analysis` |
| **可接受** | `process-pdfs`、`analyze-data` |
| **避免** | `helper`、`utils`、`documents` |

### 4.2 描述（description）

**第三人称**，包含功能和使用时机：

```yaml
description: "从 PDF 提取文本和表格，处理表单。处理 PDF 文件或用户提到 PDF 时使用。"
```

**避免**：
```yaml
description: "我可以帮你处理 PDF"
description: "帮助处理文档"
```

---

## 5. 常见模式

### 5.1 工作流模式

复杂任务分解为清晰步骤：

```markdown
## 任务进度

- [ ] 步骤 1：分析文件
- [ ] 步骤 2：提取数据
- [ ] 步骤 3：验证结果
- [ ] 步骤 4：生成报告

**步骤 1：分析文件**
使用 analyze.py 脚本...
```

### 5.2 反馈循环

```markdown
## 审查过程

1. 按照指南起草内容
2. 根据清单审查
3. 如果发现问题：记录问题 → 修改 → 再次审查
4. 只有满足所有要求后才继续
```

### 5.3 输出模板

**严格格式**（API响应、数据格式）：
```markdown
## 报告结构

始终使用此模板：

```markdown
# [标题]

## 执行摘要
[概述]

## 关键发现
- 发现 1 及数据
```
```

---

---

## 6. 增强模式（可选）

### 6.1 状态报告看板

**适用场景：** 多步骤任务、需要向用户展示进度

```markdown
| Status | Task | Progress |
|--------|------|----------|
| ✅ | 分析需求 | 100% |
| 🔄 | 生成方案 | 50% |
| ⏳ | 用户确认 | 0% |

图标：✅ 完成 | 🔄 进行中 | ⏳ 等待 | ❌ 错误 | ⚠️ 警告
```

### 6.2 选项权衡表格

**适用场景：** 需要用户做决策时

```markdown
**方案：**
| 方案 | 优点 | 缺点 | 适合场景 |
|------|------|------|----------|
| A | ... | ... | ... |

**未指定时：** 默认方案 + 理由
```

**原则：**
- 展示选项时同时说明 trade-off
- 明确默认选择，避免无限等待

### 6.3 渐进式需求澄清

**适用场景：** 复杂/模糊需求

**核心思路：** 不急于编码，通过问题揭示实现路径

| 策略 | 说明 |
|------|------|
| 目的优先 | 解决什么问题？谁用？ |
| 范围界定 | 必须有 vs 最好有 |
| 约束识别 | 时间/成本/技术限制 |

**使用建议：** 根据复杂度选择是否启用，简单需求可直接处理。

---

## 7. 避免反模式

| 反模式 | 正确做法 |
|--------|----------|
| 提供多个库选择 | 指定默认库，提供特殊场景逃逸 |
| 假设工具已安装 | 明确列出依赖并验证 |
| Windows 路径 | 使用正斜杠：`scripts/helper.py` |
| 深层嵌套引用 | 引用深度最多一级 |
| 时间敏感信息 | 使用"旧模式"部分隔离 |

---

## 8. MCP 工具引用

使用 MCP 工具时，必须使用完全限定的工具名称：

```markdown
使用 BigQuery:bigquery_schema 工具检索表模式。
使用 GitHub:create_issue 工具创建问题。
使用 Notion:notion-search 搜索页面。
```

**格式**：`ServerName:tool_name`

| 组成部分 | 示例 |
|----------|------|
| MCP 服务器名 | `BigQuery`、`GitHub`、`Notion` |
| 工具名 | `bigquery_schema`、`create_issue`、`notion-search` |

**要点：**
- 明确列出使用的 MCP 服务器
- 提供工具使用示例
- 不带服务器前缀可能导致工具找不到

---

## 9. Skill 与 Subagent 协作

> 详细规则见 [SKILL_SUBAGENT_BEST_PRACTICE.md](SKILL_SUBAGENT_BEST_PRACTICE.md)

### 9.1 Skill 调用 Subagent

```markdown
# 主代理

## 步骤 1：并行部署子代理

Task(
    subagent_type="research-agent",
    description="研究主题 A",
    prompt="研究 AI 发展趋势..."
)

Task(
    subagent_type="research-agent",
    description="研究主题 B",
    prompt="研究机器学习最新进展..."
)
```

### 9.2 Subagent 加载 Skill

`.claude/agents/research-agent.md`：
```yaml
---
name: research-agent
description: "研究代理"
skills: research-subagent     # 加载指定 skill
model: sonnet
---

# 研究子代理

你是一个专业研究助手。
```

---

---

---

## 10. 文件组织

```
skill-name/
├── SKILL.md              # 主指令（必需）
├── README.md             # 中文说明（可选）
├── examples/             # 使用示例
│   └── usage-examples.md
├── reference/            # 详细文档
│   ├── api-reference.md
│   └── advanced.md
└── scripts/              # 实用脚本
    └── helper.py
```

---

## 引用文档

| 主题 | 文档 |
|------|------|
| 详细编写指南（官方） | [best practices-claude code.md](best practices-claude code.md) |
| Skill/Subagent 使用规则 | [SKILL_SUBAGENT_BEST_PRACTICE.md](SKILL_SUBAGENT_BEST_PRACTICE.md) |
| Subagent 创建 | [docs/subagents/Create custom subagents.md](../subagents/Create custom subagents.md) |
| Skill 与 Subagent 协作 | [Skills work with subagents.md](Skills work with subagents.md) |
| Subagent 示例 | [docs/subagents/subagent example-code simplifier.md](../subagents/subagent example-code simplifier.md) |
| 动态提问实践 | [brainstorming 示例](../../examples/brainstorming/) |

---

> 文档版本：2.1
> 最后更新：2026-01-18