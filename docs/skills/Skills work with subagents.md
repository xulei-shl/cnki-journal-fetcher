### Skills and subagents

There are two ways Skills and subagents can work together:

#### Give a subagent access to Skills

[Subagents](/en/sub-agents) do not automatically inherit Skills from the main conversation. To give a custom subagent access to specific Skills, list them in the subagent's `skills` field:

```yaml  theme={null}
# .claude/agents/code-reviewer.md
---
name: code-reviewer
description: Review code for quality and best practices
skills: pr-review, security-check
---
```

The full content of each listed Skill is injected into the subagent's context at startup, not just made available for invocation. If the `skills` field is omitted, no Skills are loaded for that subagent.

<Note>
  Built-in agents (Explore, Plan, general-purpose) do not have access to your Skills. Only custom subagents you define in `.claude/agents/` with an explicit `skills` field can use Skills.
</Note>

#### Run a Skill in a subagent context

Use `context: fork` and `agent` to run a Skill in a forked subagent with its own separate context. See [Run Skills in a forked context](#run-skills-in-a-forked-context) for details.

### Run Skills in a forked context

Use `context: fork` to run a Skill in an isolated sub-agent context with its own conversation history. This is useful for Skills that perform complex multi-step operations without cluttering the main conversation:

```yaml  theme={null}
---
name: code-analysis
description: Analyze code quality and generate detailed reports
context: fork
---
```