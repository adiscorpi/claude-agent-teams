# Token Reduction: Features Lost at 95% Cut

> **Context**: `claude-web-clone/backend/agent.py` strips all built-in tools except `WebSearch`
> and disables MCP servers, cutting base input tokens from ~30k to ~1.3k (~95% reduction).
> This doc captures what was traded away and what each capability could do.

---

## Stripped Built-in Tools

| Category | Tools Removed | What You Lost | Example Use Case |
|---|---|---|---|
| **File Reading** | `Read`, `Glob`, `Grep` | Can't read local files, search codebases, or find patterns | "Read my `config.py` and explain the database settings" |
| **File Writing** | `Edit`, `MultiEdit`, `Write` | Can't create or modify files | "Refactor this function and save it back to the file" |
| **Shell Execution** | `Bash`, `BashOutput`, `KillShell` | Can't run commands, scripts, tests, or CLI tools | "Run the test suite and tell me what's failing" |
| **Web Fetching** | `WebFetch` | Can search but can't read specific URLs/pages | "Fetch the OpenAI pricing page and compare it to Anthropic's" |
| **Task Management** | `Task`, `TaskCreate`, `TaskGet`, `TaskList`, `TaskOutput`, `TaskStop`, `TaskUpdate` | Can't break work into subtasks or track multi-step jobs | "Do this 5-step refactor and track your progress" |
| **Agent Teams** | `TeamCreate`, `TeamDelete`, `SendMessage` | Can't spawn parallel teammates or coordinate multi-agent work | "Spawn 3 reviewers to audit this PR in parallel" |
| **Planning Mode** | `EnterPlanMode`, `ExitPlanMode` | Can't propose a plan before implementing | "Plan how you'd restructure this module before touching any files" |
| **Scheduling** | `CronCreate`, `CronDelete`, `CronList`, `ScheduleWakeup` | Can't schedule recurring or delayed tasks | "Check the deploy status every 5 minutes until it's green" |
| **Worktrees** | `EnterWorktree`, `ExitWorktree` | Can't isolate risky changes in a git branch | "Try this refactor in an isolated worktree so main stays clean" |
| **Monitoring** | `Monitor` | Can't watch a long-running background process | "Run the server and alert me if it crashes" |
| **Notifications** | `PushNotification` | Can't push OS notifications when async work finishes | "Notify me when the long build completes" |
| **Remote Triggers** | `RemoteTrigger` | Can't trigger external automations or webhooks | "Trigger the CI pipeline after patching this file" |
| **Skills / Commands** | `Skill`, `SlashCommand` | Can't invoke Claude Code skills (`/code-review`, `/verify`, etc.) | "Run `/code-review` on these changes before committing" |
| **Tool Discovery** | `ToolSearch` | Can't look up deferred tool schemas at runtime | Dynamic tool loading in complex agentic workflows |
| **Notebooks** | `NotebookEdit` | Can't read or edit Jupyter notebooks | "Update cell 3 in my analysis notebook with the new formula" |
| **MCP Resources** | `ListMcpResourcesTool`, `ReadMcpResourceTool` | Can't browse MCP server resource trees | Reading a file tree exposed by a custom MCP server |

---

## Stripped MCP Servers (`strict_mcp_config=True`)

| MCP Server | What You Lost | Example Use Case |
|---|---|---|
| **Google Drive** | Can't read/write/search Drive files | "Find the Q2 report in my Drive and summarize it" |
| **Gmail** | Can't read, send, or search email | "Draft a reply to the last email from my manager" |
| **Google Calendar** | Can't read or create calendar events | "What meetings do I have tomorrow?" |
| **Canva** | Can't create, edit, or export designs | "Generate a slide deck for this feature launch" |

---

## The Two Levers (both required)

```python
# 1. disallowed_tools — strips tool *definitions* from the context window.
#    allowed_tools only governs permissions, NOT what's loaded into context.
disallowed_tools=_UNWANTED_BUILTIN_TOOLS,

# 2. setting_sources=[] — don't inherit filesystem settings, CLAUDE.md,
#    slash commands, or MCP servers from the user's Claude Code install.
setting_sources=[],

# 3. strict_mcp_config + empty mcp_servers — block account-level MCP
#    connectors (Canva/Drive/Gmail/Calendar) which load regardless of
#    setting_sources and inflate context nondeterministically.
strict_mcp_config=True,
mcp_servers={},
```

---

## Token Budget Summary

| Config | Base Input Tokens | Notes |
|---|---|---|
| Default SDK (no restrictions) | ~27k–53k | Full toolset + MCP servers + settings loaded every turn |
| This app (stripped) | ~1.3k | WebSearch only, no MCP, no settings inheritance |
| Savings | **~95%** | Pure chat + web-search assistant |

---

## What the Stripped Agent CAN Do

- Multi-turn conversation (session resumption via `resume=session_id`)
- Web search (`WebSearch` is the one allowed tool)
- Markdown-formatted responses
- Streaming output via SSE

Everything else requires re-enabling the relevant tools and accepting the token cost.

---

*Source: `claude-web-clone/backend/agent.py` — see `_UNWANTED_BUILTIN_TOOLS` and `ClaudeAgentOptions` config*
