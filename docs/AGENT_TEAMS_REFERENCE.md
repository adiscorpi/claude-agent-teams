# Agent Teams Master Reference Guide

> **Status**: Experimental — enable with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`  
> **Minimum version**: Claude Code v2.1.32+  
> **Last updated**: 2026-05-25

---

## Table of Contents

1. [Core Concepts](#1-core-concepts)
2. [Architecture](#2-architecture)
3. [When to Use What](#3-when-to-use-what)
4. [Setup & Configuration](#4-setup--configuration)
5. [Agent Teams — Full Guide](#5-agent-teams--full-guide)
6. [Subagents — Full Guide](#6-subagents--full-guide)
7. [Communication Patterns](#7-communication-patterns)
8. [Task Management](#8-task-management)
9. [Hooks & Quality Gates](#9-hooks--quality-gates)
10. [Cost Management](#10-cost-management)
11. [Best Practices Cheatsheet](#11-best-practices-cheatsheet)
12. [Prompt Templates](#12-prompt-templates)
13. [Troubleshooting](#13-troubleshooting)
14. [Limitations](#14-limitations)
15. [Quick-Reference Card](#15-quick-reference-card)

---

## 1. Core Concepts

### What is an Agent Team?

An **agent team** is a set of independent Claude Code sessions coordinated by a single **team lead**. Each teammate:
- Has its **own context window** (no shared memory with the lead or other teammates)
- Can **message other teammates directly**
- Claims work from a **shared task list**
- Runs as a **fully independent Claude Code instance**

### What is a Subagent?

A **subagent** is a specialized helper that runs *within* a single session. It has:
- Its own context window
- A custom system prompt
- Restricted tool access
- Returns only a **summary** to the parent session

Subagents **cannot** message each other. They report only back to the parent.

---

## 2. Architecture

```
AGENT TEAMS
────────────────────────────────────────────
  ┌─────────────┐
  │  Team Lead  │ ← you interact here
  └──────┬──────┘
         │  spawns + coordinates
  ┌──────┴──────────────────────────────┐
  │           Shared Task List          │
  └──────┬──────────┬──────────┬────────┘
         │          │          │
   ┌─────▼──┐  ┌────▼───┐  ┌──▼─────┐
   │ Mate 1 │◄─►│ Mate 2 │◄─►│ Mate 3 │  ← message each other directly
   └────────┘  └────────┘  └────────┘
   own ctx      own ctx      own ctx


SUBAGENTS
────────────────────────────────────────────
  ┌─────────────────┐
  │   Main Session  │
  └────────┬────────┘
           │  delegates + gets summary back
    ┌──────┴──────┐
    │   Subagent  │ (own ctx, custom tools, custom prompt)
    └─────────────┘
    (subagents cannot talk to each other)
```

### Key Components

| Component | Role |
|-----------|------|
| **Team Lead** | Creates team, spawns teammates, coordinates work |
| **Teammates** | Independent Claude instances working on tasks |
| **Task List** | Shared list; teammates claim and complete tasks |
| **Mailbox** | Messaging system for inter-agent communication |

### File Locations

| Resource | Path |
|----------|------|
| Team config | `~/.claude/teams/{team-name}/config.json` |
| Task list | `~/.claude/tasks/{team-name}/` |
| User subagents | `~/.claude/agents/` |
| Project subagents | `.claude/agents/` |

> ⚠️ **Never hand-edit** `config.json` — it is overwritten on every state update.

---

## 3. When to Use What

### Decision Tree

```
Is your task parallelizable?
├─ No → Single session
└─ Yes
   ├─ Do workers need to talk to each other?
   │   ├─ Yes → Agent Teams
   │   └─ No → Subagents (or background agents)
   └─ Is the work purely exploratory/review?
       ├─ Yes → Agent Teams (research / competing hypotheses)
       └─ Sequential with dependencies → Single session or Subagents
```

### Comparison Table

| | Subagents | Agent Teams |
|---|---|---|
| **Context** | Own window; results return to caller | Own window; fully independent |
| **Communication** | Reports back to main only | Teammates message each other directly |
| **Coordination** | Main agent manages all work | Shared task list with self-coordination |
| **Best for** | Focused tasks where only the result matters | Complex work needing discussion & collaboration |
| **Token cost** | Lower — results summarized back | Higher — each teammate is a full Claude instance |
| **Same-file edits** | ✅ Fine | ❌ Avoid (conflict risk) |
| **Sequential deps** | ✅ Fine | ❌ Wasteful |
| **Parallel exploration** | ⚠️ Possible | ✅ Optimal |

### Strongest Agent Team Use Cases

1. **Parallel code review** — security / performance / tests each reviewed by a dedicated teammate
2. **New module/feature development** — teammates own disjoint file sets
3. **Debugging with competing hypotheses** — teammates try to disprove each other's theories
4. **Cross-layer work** — frontend, backend, and tests owned separately
5. **Research synthesis** — multiple angles investigated simultaneously

### When NOT to Use Agent Teams

- Sequential tasks with hard dependencies
- Same-file edits (use a single session)
- Simple, quick, focused tasks (use subagents)
- Routine work (cost overhead is not worth it)

---

## 4. Setup & Configuration

### Enable Agent Teams

**Option A — settings.json:**
```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

**Option B — shell:**
```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

### Display Mode

| Mode | Description | Requirement |
|------|-------------|-------------|
| `auto` (default) | Split panes if in tmux, in-process otherwise | None |
| `in-process` | All teammates in your main terminal | None |
| `tmux` | Each teammate in its own pane | tmux or iTerm2 |

**Set in `~/.claude/settings.json`:**
```json
{
  "teammateMode": "in-process"
}
```

**Override per session:**
```bash
claude --teammate-mode in-process
```

**Install tmux (macOS):**
```bash
brew install tmux
```

**iTerm2 split panes:**
```bash
# Install it2 CLI, then enable Python API in iTerm2 → Settings → General → Magic
```

### Keyboard Shortcuts (In-Process Mode)

| Key | Action |
|-----|--------|
| `Shift+Down` | Cycle to next teammate |
| `Enter` | View teammate's session |
| `Escape` | Interrupt teammate's current turn |
| `Ctrl+T` | Toggle task list |

---

## 5. Agent Teams — Full Guide

### Starting a Team

Tell the lead in natural language. Claude creates the team, spawns teammates, and coordinates:

```text
I'm designing a CLI tool. Create an agent team:
- One teammate on UX
- One on technical architecture  
- One playing devil's advocate
```

### Specifying Team Size & Models

```text
Create a team with 4 teammates to refactor these modules in parallel.
Use Sonnet for each teammate.
```

**Default teammate model**: set in `/config` → "Default teammate model". Choose "Default (leader's model)" to follow the lead's model.

### Requiring Plan Approval

Force teammates to plan before implementing:

```text
Spawn an architect teammate to refactor the authentication module.
Require plan approval before they make any changes.
```

**Flow:**
1. Teammate enters read-only plan mode
2. Submits plan approval request to lead
3. Lead reviews and approves/rejects with feedback
4. If rejected → teammate revises and resubmits
5. If approved → teammate exits plan mode and implements

**Influence approval criteria in your prompt:**
```text
Only approve plans that include test coverage.
Reject plans that modify the database schema.
```

### Talking to Teammates Directly

- **In-process**: `Shift+Down` to cycle, then type to send message
- **Split-pane**: click into pane, interact directly

### Naming Teammates

Give predictable names for later reference:

```text
Spawn three teammates named "security-reviewer", "performance-reviewer", 
and "test-reviewer" to review PR #142.
```

### Reusing Subagent Definitions as Teammates

```text
Spawn a teammate using the security-reviewer agent type to audit the auth module.
```

The teammate honors the definition's `tools` allowlist and `model`. The definition body is **appended** (not replaced) to the teammate's system prompt. Team coordination tools (`SendMessage`, task tools) are always available regardless of `tools` restrictions.

> **Note**: `skills` and `mcpServers` frontmatter fields are **not applied** when a subagent definition runs as a teammate. They load from project/user settings instead.

### Shutting Down a Teammate

```text
Ask the researcher teammate to shut down
```

The lead sends a shutdown request; the teammate can approve (graceful exit) or reject with explanation.

### Cleaning Up the Team

```text
Clean up the team
```

> ⚠️ Always use the **lead** to clean up. Shut down all teammates first, then clean up. Teammates should never run cleanup.

---

## 6. Subagents — Full Guide

### Built-in Subagents

| Agent | Model | Tools | Purpose |
|-------|-------|-------|---------|
| **Explore** | Haiku | Read-only | File discovery, codebase search |
| **Plan** | Inherits | Read-only | Research during plan mode |
| **General-purpose** | Inherits | All | Complex multi-step tasks |
| **statusline-setup** | Sonnet | — | `/statusline` configuration |
| **claude-code-guide** | Haiku | — | Claude Code feature questions |

> Explore and Plan **skip CLAUDE.md and git status** to stay fast and cheap. All others load them.

### Creating a Subagent

**Via `/agents` command** (recommended):
```text
/agents
```
Navigate to Library → Create new agent → Personal/Project → Generate with Claude

**Via file:**
```markdown
---
name: code-reviewer
description: Reviews code for quality and best practices. Use after any code change.
tools: Read, Glob, Grep
model: sonnet
---

You are a code reviewer. Analyze code and provide specific, actionable 
feedback on quality, security, and best practices.
```

### Subagent Scope & Priority

| Location | Scope | Priority |
|----------|-------|----------|
| Managed settings | Organization-wide | 1 (highest) |
| `--agents` CLI flag | Current session only | 2 |
| `.claude/agents/` | Current project | 3 |
| `~/.claude/agents/` | All your projects | 4 |
| Plugin `agents/` directory | Where plugin is enabled | 5 (lowest) |

> Same name → higher priority wins. Keep names unique across the whole tree.

### All Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | ✅ | Unique ID: lowercase + hyphens |
| `description` | ✅ | When Claude should delegate here |
| `tools` | No | Allowed tools; inherits all if omitted |
| `disallowedTools` | No | Tools to deny (removes from allowed set) |
| `model` | No | `sonnet`, `opus`, `haiku`, full model ID, or `inherit` |
| `permissionMode` | No | `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, `plan` |
| `maxTurns` | No | Max agentic turns before stopping |
| `skills` | No | Skills to preload into context at startup |
| `mcpServers` | No | MCP servers for this subagent |
| `hooks` | No | Lifecycle hooks scoped to this subagent |
| `memory` | No | Persistent memory: `user`, `project`, or `local` |
| `background` | No | `true` = always run as background task |
| `effort` | No | `low`, `medium`, `high`, `xhigh`, `max` |
| `isolation` | No | `worktree` = isolated git worktree |
| `color` | No | `red`, `blue`, `green`, `yellow`, `purple`, `orange`, `pink`, `cyan` |
| `initialPrompt` | No | Auto-submitted first turn when run as main session agent |

### Model Resolution Order

1. `CLAUDE_CODE_SUBAGENT_MODEL` env var
2. Per-invocation `model` parameter
3. Subagent definition's `model` frontmatter
4. Main conversation's model

### Invoking Subagents Explicitly

Use the agent's name or a scoped identifier:

```text
Use the security-reviewer agent to audit src/auth/
```

For plugin subagents with subdirectories:
```text
# File at plugin agents/review/security.md in plugin "my-plugin"
# Registered as: my-plugin:review:security
```

### CLI-Defined Subagents

For testing or automation — not saved to disk:

```bash
claude --agents '{
  "code-reviewer": {
    "description": "Expert code reviewer. Use proactively after code changes.",
    "prompt": "You are a senior code reviewer...",
    "tools": ["Read", "Grep", "Glob", "Bash"],
    "model": "sonnet"
  }
}'
```

### Persistent Memory

Enable cross-session learning:
```yaml
memory: user    # ~/.claude/agent-memory/
memory: project # .claude/agent-memory/
memory: local   # local path (not synced)
```

---

## 7. Communication Patterns

### Team Lead → Teammate

- Natural language instruction in spawn prompt
- Direct message via `Shift+Down` (in-process) or pane click (split)

### Teammate → Team Lead

- **Automatic**: idle notifications sent when teammate stops
- **Automatic**: plan approval requests
- **Explicit**: `SendMessage` tool with lead as recipient

### Teammate → Teammate

- **Direct**: `SendMessage` tool by teammate name
- To reach everyone: send one message per recipient (no broadcast)
- Messages are delivered automatically — no polling required

### Shared State

- **Task list**: all agents can see task status; teammates self-claim
- **CLAUDE.md**: loaded by all teammates from working directory

### What Teammates DON'T Inherit

- Lead's conversation history
- Lead's in-progress context

### What Teammates DO Load at Startup

- Same project context as a regular session (CLAUDE.md, MCP servers, skills)
- The spawn prompt from the lead

---

## 8. Task Management

### Task States

```
pending → in progress → completed
```

Dependencies: a pending task with unresolved dependencies **cannot be claimed** until they complete. Unblocking is automatic when blocking tasks complete.

### Task Assignment

| Mode | How |
|------|-----|
| **Lead assigns** | Tell the lead which task → which teammate |
| **Self-claim** | Teammate finishes and picks the next unassigned, unblocked task |

File locking prevents race conditions when multiple teammates try to claim simultaneously.

### Task Sizing

| Size | Problem |
|------|---------|
| Too small | Coordination overhead > benefit |
| Too large | Long runs without check-ins; wasted effort risk |
| **Just right** | Self-contained; clear deliverable (a function, test file, or review) |

**Rule of thumb**: 5–6 tasks per teammate keeps everyone productive without excessive context switching.

### Nudging Stuck Tasks

If a task appears stuck (work done but not marked complete):
```text
Teammate hasn't marked task #3 as complete — please update it.
```

Or tell the lead:
```text
Check whether task #3 is actually done and update its status.
```

---

## 9. Hooks & Quality Gates

### Agent Team Hooks

| Hook | Trigger | Exit 2 Effect |
|------|---------|---------------|
| `TeammateIdle` | Teammate about to go idle | Send feedback, keep teammate working |
| `TaskCreated` | Task being created | Prevent creation, send feedback |
| `TaskCompleted` | Task being marked complete | Prevent completion, send feedback |

### Subagent Hooks

Scoped to individual subagents via frontmatter:

```yaml
hooks:
  SubagentStart:
    - type: command
      command: echo "Subagent starting"
  SubagentStop:
    - type: command
      command: ~/.claude/hooks/subagent-cleanup.sh
```

`SubagentStart` hook receives `agent_type` = the subagent's `name` field.

### Global Hooks for Teams

Add to `settings.json` to pre-filter data before agents see it:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/filter-test-output.sh"
          }
        ]
      }
    ]
  }
}
```

---

## 10. Cost Management

### Cost Benchmarks

| Scenario | Approx. multiplier vs. single session |
|----------|---------------------------------------|
| Standard single session | 1× |
| Agent team (teammates working) | ~3–5× |
| Agent team with plan mode | ~7× |

### Enterprise Averages

- Average: ~$13/developer/active day
- 90th percentile: <$30/active day
- Monthly: ~$150–250/developer

### Rate Limit Recommendations (API)

| Team size | TPM per user | RPM per user |
|-----------|-------------|-------------|
| 1–5 | 200k–300k | 5–7 |
| 5–20 | 100k–150k | 2.5–3.5 |
| 20–50 | 50k–75k | 1.25–1.75 |
| 50–100 | 25k–35k | 0.62–0.87 |
| 100–500 | 15k–20k | 0.37–0.47 |
| 500+ | 10k–15k | 0.25–0.35 |

### Cost Reduction Strategies

**For agent teams:**
- Use **Sonnet** for teammates (not Opus)
- Keep teams **3–5 teammates** max
- Keep spawn prompts **focused** (everything in it adds to context from start)
- **Clean up teams** when done — idle teammates still consume tokens
- Use plan mode judiciously (7× cost multiplier)

**For subagents:**
- Route simple tasks to **Haiku** subagents
- Use subagents to **isolate high-volume operations** (log processing, test runs)
- Set `maxTurns` to cap runaway subagents

**General:**
- Run `/usage` to track token spend per session
- Use `/clear` between unrelated tasks
- Use `/compact Focus on X` to guide summarization
- Keep CLAUDE.md under 200 lines — move workflow-specific instructions to skills
- Defer MCP tool schemas (enabled by default)

### Tracking

```text
/usage          → token stats for current session
```

For API users: authoritative billing at [platform.claude.com/usage](https://platform.claude.com/usage)

---

## 11. Best Practices Cheatsheet

### Team Design

- ✅ **Give teammates enough context in the spawn prompt** — they don't inherit the lead's history
- ✅ **Assign disjoint file sets** — two teammates editing the same file causes overwrites
- ✅ **Start with 3–5 teammates** for most workflows
- ✅ **Name teammates explicitly** if you'll reference them later
- ✅ **Break work into 5–6 tasks per teammate**
- ✅ **Start with research/review tasks** when new to agent teams
- ❌ **Don't assign the same file to multiple teammates**
- ❌ **Don't let teams run unattended** — check in, redirect, synthesize

### Lead Behavior

- If the lead starts implementing instead of delegating:
  ```text
  Wait for your teammates to complete their tasks before proceeding.
  ```
- If the lead shuts down before work is done:
  ```text
  Keep going — teammates haven't finished yet.
  ```

### Subagent Design

- Write **clear, specific descriptions** — Claude uses these to decide when to delegate
- Restrict tools to **minimum needed** for the task
- Use **Haiku for fast, cheap, read-only tasks**
- Use **Sonnet for complex analysis**
- Use **Opus sparingly** — only for architectural decisions
- Set `isolation: worktree` for subagents that need an isolated repo copy
- Enable `memory` for subagents you want to accumulate domain knowledge over time

### Context Hygiene

- Subagent receives: system prompt + basic env (working dir) — **not** the full Claude Code system prompt
- `cd` in a subagent does not persist between tool calls or affect main conversation
- CLAUDE.md is loaded by all teammates and custom subagents (but NOT by Explore/Plan built-ins)

---

## 12. Prompt Templates

### Parallel Code Review

```text
Create an agent team to review PR #142. Spawn three reviewers:
- "security-reviewer": focused on security implications
- "perf-reviewer": checking performance impact
- "test-reviewer": validating test coverage and quality
Have them each review independently and report findings to you.
Synthesize after all three are done.
```

### Competing Hypotheses Debug

```text
Users report [DESCRIBE BUG]. Spawn 5 agent teammates to investigate 
different hypotheses. Have them communicate with each other to try to 
disprove each other's theories, like a scientific debate. Update 
docs/findings.md with whatever consensus emerges.
```

### Parallel Feature Development

```text
Create a team with 3 teammates to build [FEATURE]:
- "backend-dev": owns src/api/ and src/models/
- "frontend-dev": owns src/ui/ and src/components/
- "test-writer": owns tests/ and writes coverage for both
Assign tasks with clear file ownership to avoid conflicts.
```

### Research Synthesis

```text
Create an agent team to research [TOPIC] from multiple angles:
- One teammate on [ANGLE 1]
- One teammate on [ANGLE 2]
- One teammate playing devil's advocate
Have them share findings and synthesize a recommendation.
```

### Spawn with Plan Approval

```text
Spawn an architect teammate named "db-architect" to redesign the 
database schema in src/db/. Require plan approval before they make 
any changes. Only approve plans that include migration scripts and 
don't break existing API contracts.
```

### Reuse a Subagent Definition as Teammate

```text
Spawn a teammate using the security-reviewer agent type to audit 
the authentication module at src/auth/. Focus on token handling, 
session management, and input validation.
```

### Simple Subagent (File)

```markdown
---
name: test-runner
description: Runs tests and summarizes failures. Use after any code change.
tools: Bash, Read
model: haiku
maxTurns: 10
---

Run the test suite and return a concise summary of:
1. Total tests passed/failed
2. Each failing test name and error message
3. Any patterns in the failures

Do not suggest fixes — only report results.
```

### Research Subagent with Memory

```markdown
---
name: library-researcher
description: Researches external libraries and APIs. Use when evaluating dependencies.
tools: WebFetch, WebSearch, Read
model: sonnet
memory: user
---

Research libraries, APIs, and documentation. Accumulate knowledge about 
libraries you've researched before. When asked about a library, check 
your memory first before searching the web.
```

---

## 13. Troubleshooting

### Teammates Not Appearing

1. Press `Shift+Down` — they may already be running but not visible
2. Verify task was complex enough (Claude decides whether to spawn)
3. Check tmux is installed: `which tmux`
4. For iTerm2: verify `it2` CLI is installed and Python API is enabled

### Too Many Permission Prompts

Pre-approve common operations **before** spawning teammates:
```json
{
  "permissions": {
    "allow": ["Bash(npm test:*)", "Bash(git:*)", "Read(*)", "Write(src/**)"]
  }
}
```

### Teammates Stopping on Errors

- Check their output: `Shift+Down` in in-process mode, or click pane in split mode
- Give additional instructions directly to the stuck teammate
- Or: spawn a replacement teammate to continue the work

### Lead Shuts Down Early

```text
Keep going — not all tasks are complete yet.
```

Or proactively add to spawn prompt:
```text
Wait for all teammates to finish before shutting down.
```

### Orphaned tmux Sessions

```bash
tmux ls
tmux kill-session -t <session-name>
```

### Task Status Lagging

If a task appears stuck (work done, not marked complete):
```text
Tell [teammate-name] to mark task #3 as completed.
```

### Lead Messaging Dead Teammates (After /resume)

`/resume` and `/rewind` do NOT restore in-process teammates. Tell the lead:
```text
Those teammates no longer exist. Spawn new ones to continue.
```

---

## 14. Limitations

| Limitation | Detail |
|------------|--------|
| **No session resumption** | `/resume` and `/rewind` don't restore in-process teammates |
| **Task status lag** | Teammates may not mark tasks complete; blocked tasks can stall |
| **Slow shutdown** | Teammates finish current request/tool call before shutting down |
| **One team at a time** | Lead can only manage one team; clean up before creating another |
| **No nested teams** | Teammates cannot spawn their own teams or teammates |
| **Fixed lead** | Session that creates the team is lead for life; no promotion/transfer |
| **Permissions at spawn** | Per-teammate modes can be changed after spawning, but not set at spawn time |
| **Split panes** | Requires tmux or iTerm2; not supported in VS Code terminal, Windows Terminal, or Ghostty |
| **Subagent nesting** | Subagents cannot spawn other subagents (prevents infinite nesting) |

---

## 15. Quick-Reference Card

### Agent Team Lifecycle

```
Enable → Describe task → Lead creates team → Teammates spawn 
→ Claim tasks → Communicate → Report idle → Lead synthesizes 
→ Shut down teammates → Clean up team
```

### Subagent Lifecycle

```
Define (file or /agents) → Claude auto-delegates matching tasks 
→ Subagent works in own context → Returns summary to main session
```

### Key Commands

| Command | What it does |
|---------|-------------|
| `/agents` | Manage subagents (create, edit, view running) |
| `/usage` | Check token usage |
| `/clear` | Fresh context (save tokens) |
| `/compact [focus]` | Summarize conversation |
| `/model` | Switch model |
| `Shift+Down` | Cycle teammates (in-process mode) |
| `Ctrl+T` | Toggle task list |

### Model Selection Guide

| Task | Model |
|------|-------|
| Fast read-only search/explore | Haiku |
| Code analysis, review, most coding | Sonnet |
| Complex architecture, multi-step reasoning | Opus |
| Agent team teammates (default) | Sonnet |

### Settings Reference

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "teammateMode": "in-process",
  "permissions": {
    "allow": ["Bash(git:*)", "Read(**)"]
  }
}
```

### Subagent File Template

```markdown
---
name: <lowercase-hyphenated>
description: <when Claude should use this agent — be specific>
tools: Read, Grep, Glob, Bash
model: sonnet
maxTurns: 20
color: blue
---

<System prompt here. Be specific about format of output 
and what the agent should/shouldn't do.>
```

---

*Source: [Claude Code Agent Teams Docs](https://code.claude.com/docs/en/agent-teams) | [Subagents Docs](https://code.claude.com/docs/en/sub-agents) | [Cost Docs](https://code.claude.com/docs/en/costs)*
