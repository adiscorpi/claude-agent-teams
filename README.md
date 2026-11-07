# Claude Agent Teams

Experiments in multi-agent orchestration with the Claude Agent SDK and Claude Code Agent Teams, with a focus on keeping token usage low.

## What's inside

| Path | What it is |
|---|---|
| `Orchestrator/` | A plain-Python FastAPI orchestrator that chains agents into an email pipeline. A drafting agent (CEO voice, or a personal "Date Mode" partner email) writes the message, and a sender agent formats it as HTML and delivers it through a custom MCP `send_email` tool over SMTP. Progress and token usage stream to a small frontend over Server-Sent Events. |
| `claude-web-clone/` (submodule) | A Claude-style chat app: FastAPI backend and React frontend built on the Agent SDK. See [adiscorpi/claude-web-clone](https://github.com/adiscorpi/claude-web-clone). |
| `docs/AGENT_TEAMS_REFERENCE.md` | Reference guide to Claude Code Agent Teams vs. subagents: architecture, communication patterns, task management, hooks, cost control and prompt templates. |
| `docs/TOKEN_REDUCTION_FEATURES.md` | Notes on cutting base input tokens from about 30k to about 1.3k (around 95%) by stripping unused built-in tool schemas, and what each removed capability would have offered. |

## Token-conscious design

- Each agent runs on the cheapest capable model (Haiku) with a hard cap on agentic turns.
- Every built-in Claude Code tool is listed in `disallowed_tools`, so its schema never enters the prompt. Agents can only call the one MCP tool they are given.
- The orchestrator contains no model calls itself. It runs the agents in order and streams their results.

## Running the Orchestrator

```bash
cd Orchestrator/backend
pip install -r requirements.txt
cp .env.example .env   # add your Claude token and SMTP credentials
uvicorn main:app --reload --port 8000
```

Then open `Orchestrator/frontend/index.html`.

## Tech

Python, FastAPI, Claude Agent SDK, MCP, SSE, SMTP, React (web clone).
