# Skill 与 Subagent 互相调用最佳实践

> 清晰指南：如何正确编写和调用 Skills 与 Subagents

---

## 1. 核心概念

| 概念 | 说明 | 用途 |
|------|------|------|
| **Skill** | 可被调用的功能模块 | 封装特定能力（如代码审查、格式化） |
| **Subagent** | 独立上下文的专业代理 | 复杂任务、并行执行、工具隔离 |
| **Task 工具** | 启动 Subagent 的机制 | `Task(subagent_type="xxx", prompt="...")` |

---

## 2. Skill 文件格式

### 2.1 标准结构

```yaml
---
name: my-skill              # 必需：小写字母+连字符
description: "简短描述何时使用此 skill"
---

# Skill 名称

你的角色和指令...
```

### 2.2 完整 Frontmatter

```yaml
---
name: research-subagent     # 必需
description: "内部研究子代理，执行网络研究任务"
# skills: skill1, skill2   # 可选：加载其他 skills
# context: fork            # 可选：fork/stream，默认 fork
---
```

---

## 3. Subagent 文件格式

### 3.1 自定义 Subagent

文件位置：`.claude/agents/<name>.md`

```yaml
---
name: research-agent        # 必需：Subagent 唯一标识
description: "专门的研究代理"
skills: research-subagent   # 可选：加载的 skills
model: sonnet               # 可选：sonnet/opus/haiku/inherit
tools: Read, Grep           # 可选：限制工具
disallowedTools: Write      # 可选：禁用工具
permissionMode: default     # 可选：权限模式
---

# 研究子代理

你是一个专业研究助手，使用 Web 工具执行研究任务。
```

### 3.2 内置 Subagent

| 类型 | 调用方式 | 能否加载 Skills |
|------|----------|-----------------|
| `general-purpose` | `Task(subagent_type="general-purpose")` | **不能** |
| `Explore` | `Task(subagent_type="Explore")` | **不能** |
| `Plan` | `Task(subagent_type="Plan")` | **不能** |

---

## 4. Skill 中调用 Subagent

### 4.1 并行调用多个 Subagent

**关键**：在单条消息中发起所有 Task 调用

```markdown
# 主代理

## Step 1: 部署子代理

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

Task(
    subagent_type="research-agent",
    description="研究主题 C",
    prompt="研究自然语言处理..."
)
```

### 4.2 单个 Subagent 调用

```markdown
Task(
    subagent_type="code-reviewer",
    description="审查认证模块",
    prompt="审查用户认证模块的安全性..."
)
```

### 4.3 Task 参数说明

```python
Task(
    subagent_type="research-agent",  # 必需：与子代理 name 一致
    description="简短描述（3-5词）",   # 必需
    prompt="详细任务描述",             # 必需
    model="sonnet",                   # 可选：覆盖默认模型
    run_in_background=False           # 可选：后台运行
)
```

---

## 5. Subagent 中使用 Skill

### 5.1 加载 Skills（通过自定义 Subagent）

**.claude/agents/research-agent.md**:
```yaml
---
name: research-agent
description: "研究代理"
skills: research-subagent     # 加载指定 skill
model: sonnet
---

# 研究子代理

你是一个专业研究助手。执行任务时使用加载的 skill。
```

### 5.2 完整调用链示例

```
用户查询
    ↓
deep-research Skill（主代理）
    ↓ 并行 Task 调用
    ├─→ Subagent 1 (research-agent)
    │       ↓
    │       使用 research-subagent skill
    │       ↓
    │       返回发现
    │
    ├─→ Subagent 2 (research-agent)
    │       ↓
    │       使用 research-subagent skill
    │       ↓
    │       返回发现
    │
    └─→ Subagent N (research-agent)
            ↓
            使用 research-subagent skill
            ↓
            返回发现
    ↓
主代理汇总，写最终报告
```

---

## 6. 架构决策矩阵

| 场景 | 使用方式 |
|------|----------|
| 简单任务，直接使用工具 | `Task(general-purpose)` |
| 需要并行执行 | 自定义 Subagent + 并行 Task |
| 需要复用 Skill 能力 | 自定义 Subagent + frontmatter `skills` |
| 主代理协调多子任务 | Skill 中并行调用多个 Task |
| 子代理需要多层协调 | 主代理串联（不能嵌套） |

---

## 7. 注意事项

### 7.1 内置 Subagent 限制

```
general-purpose / Explore / Plan:
├── 不能加载 skills（frontmatter 中 skills 无效）
└── 不能嵌套调用其他 subagents
```

### 7.2 自定义 Subagent 要求

```
自定义 Subagent 文件：
├── 位置：.claude/agents/<name>.md
├── name 字段：小写字母+连字符
├── subagent_type：必须与 name 一致
├── skills：可在 frontmatter 中加载
└── 可继承或限制工具
```

### 7.3 Subagent 不能做什么

- **不能**启动其他 Subagent（嵌套）
- **不能**访问内置 Subagent 的 skills
- **不能**与主代理共享上下文

---

## 8. 常见模式

### 模式一：扇出-汇总

```
主代理 Skill
├── 并行启动 N 个 Subagent（扇出）
│   ├── Subagent 1 → 结果 1
│   ├── Subagent 2 → 结果 2
│   └── Subagent N → 结果 N
└── 汇总所有结果 → 最终报告
```

### 模式二：管道模式

```
Subagent A（收集）→ 结果
    ↓
Subagent B（分析）→ 结果
    ↓
Subagent C（生成）→ 结果
```

### 模式三：Skill 代理链

```
用户 → Skill A → Task(Subagent) → Skill B → 最终输出
```

---

## 9. 文件命名规范

| 类型 | 文件位置 | 命名格式 |
|------|----------|----------|
| Skill | `.claude/skills/` | `skill-name/SKILL.md` |
| Subagent | `.claude/agents/` | `subagent-name.md` |

---

## 10. Skill 中调用外部脚本

### 10.1 脚本文档标准格式

```markdown
## Tools

### script_name.py

**Usage:**

`python3 scripts/script_name.py --arg1 value1 --arg2 value2`


**Scenarios:**

#### 场景 1：快速浏览

python3 scripts/fetch_news.py --source hackernews --limit 5


#### 场景 2：深度分析
`python3 scripts/fetch_news.py --keyword "AI" --limit 20 --deep`

**Arguments:**

- `--source`: 数据源 (default: "all")
- `--limit`: 最大条目数 (default: 10)
- `--keyword`: 关键词过滤 (逗号分隔)
- `--deep`: **[NEW]** 启用深度获取

**Output:**
JSON 数组，包含 `title`, `url`, `source`, `content` 字段（`--deep` 时）

```


### 10.2 关键原则

✅ **按场景组织**：而非按参数罗列
✅ **提供完整可执行命令**：复制即用
✅ **标注关键标记**：`[NEW]`, `[CRITICAL]`, `[DEPRECATED]`
✅ **明确路径**：使用 `scripts/` 目录统一管理

❌ 不要硬编码路径
❌ 不要省略默认值
❌ 不要使用过时示例

### 10.3 完整示例参考

见 `examples/news-aggregator-skill/SKILL.md` - 展示了场景化使用、智能扩展说明、参数列表、输出格式的完整实践。

---

> 文档版本：1.1
> 最后更新：2026-01-20
