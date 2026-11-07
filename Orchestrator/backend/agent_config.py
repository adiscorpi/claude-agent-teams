"""
agent_config.py — shared, token-conscious configuration for both agents.

Both agents are deliberately kept on a short leash: cheapest capable model,
no default Claude Code boilerplate, no filesystem settings, no built-in tools
in context, and a hard cap on agentic turns. The result is that each run sends
only the tokens it actually needs.
"""

from claude_agent_sdk import ClaudeAgentOptions

# Haiku 4.5 — cheapest capable model. The agents do narrow, well-scoped work
# (draft an email / format + send one), so a frontier model would just burn
# tokens for no quality gain.
MODEL = "claude-haiku-4-5"

# Every built-in Claude Code tool, listed so it is stripped from each agent's
# context. Two wins: (1) the tool schemas never enter the prompt, so we don't
# pay tokens for capabilities the agents will never use (this is the lever that
# takes base input from ~30k to ~1.3k tokens — see docs/TOKEN_REDUCTION_FEATURES.md);
# (2) the agents physically cannot take any action except the one tool we hand
# them. allowed_tools only governs *permission* — disallowed_tools is what
# removes the definitions from context. Mirrors claude-web-clone's strip list,
# plus WebSearch (this pipeline never browses).
_BUILTIN_TOOLS = [
    "Task", "AskUserQuestion", "Bash", "BashOutput", "KillShell",
    "CronCreate", "CronDelete", "CronList", "Edit", "MultiEdit", "Write",
    "EnterPlanMode", "EnterWorktree", "ExitPlanMode", "ExitWorktree",
    "Glob", "Grep", "Monitor", "NotebookEdit", "PushNotification", "Read",
    "RemoteTrigger", "ScheduleWakeup", "SendMessage", "Skill", "SlashCommand",
    "TaskCreate", "TaskGet", "TaskList", "TaskOutput", "TaskStop", "TaskUpdate",
    "TeamCreate", "TeamDelete", "ToolSearch", "TodoWrite", "WebFetch", "WebSearch",
    "ListMcpResourcesTool", "ReadMcpResourceTool",
]
# NOTE: if a future CLI adds a new built-in, it can leak back into context. The
# init system message lists what's still available — keep this at [] (plus our
# own MCP tools). TodoWrite was the one that slipped through and made the CEO
# agent take an agentic detour mid-draft.


def agent_options(system_prompt, *, max_turns, allowed_tools=None, mcp_servers=None):
    """Build the token-lean ClaudeAgentOptions shared by both agents.

    - system_prompt replaces Claude Code's default (no boilerplate tokens)
    - setting_sources=[] -> no CLAUDE.md / settings loaded into context
    - disallowed_tools strips every built-in tool's schema from the prompt
    - max_turns caps the agentic loop so a run can never spiral

    No permission_mode is set: a tool listed in allowed_tools runs without a
    prompt, and every other tool is stripped from context — so nothing can ever
    trigger an interactive permission prompt (which would hang a headless run).
    """
    return ClaudeAgentOptions(
        system_prompt=system_prompt,
        model=MODEL,
        max_turns=max_turns,
        allowed_tools=list(allowed_tools or []),
        disallowed_tools=_BUILTIN_TOOLS,
        setting_sources=[],
        mcp_servers=mcp_servers or {},
        strict_mcp_config=True,
    )


def usage_summary(result_msg):
    """Flatten a ResultMessage into {input, output, total, cost_usd} for the UI."""
    u = getattr(result_msg, "usage", None) or {}
    inp = (
        (u.get("input_tokens") or 0)
        + (u.get("cache_read_input_tokens") or 0)
        + (u.get("cache_creation_input_tokens") or 0)
    )
    out = u.get("output_tokens") or 0
    return {
        "input": inp,
        "output": out,
        "total": inp + out,
        "cost_usd": getattr(result_msg, "total_cost_usd", None),
    }
