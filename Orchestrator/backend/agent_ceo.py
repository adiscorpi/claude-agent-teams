"""
agent_ceo.py — Agent 1: CEO Email Drafter.

Takes high-level instructions and returns a professional CEO-voiced email
(subject + body) as plain text, plus token usage for the run.
"""

import json

from claude_agent_sdk import query, AssistantMessage, ResultMessage
from claude_agent_sdk.types import TextBlock

from agent_config import agent_options, usage_summary

_SYSTEM_PROMPT = """You are a seasoned CEO drafting company communications. Your voice is:
- Confident and direct — no corporate filler
- Warm and human — employees are people, not resources
- Concise — say it once, say it well

Output ONLY a JSON object with exactly two keys:
{"subject": "...", "body": "..."}

The body is plain text (no HTML), written in the first person. End it with a
signature block: a blank line, then "Best regards," then a blank line, then "[CEO]".
Output nothing but the JSON — no markdown fences, no commentary."""


async def draft_email(instructions: str) -> dict:
    """Draft a CEO-style email. Returns {"subject", "body", "usage"}."""
    # The draft is a single model response, but max_turns is only a safety
    # ceiling — the model stops on its own at end_turn, so a little headroom
    # costs no extra tokens and avoids tripping the cap on an extra internal step.
    options = agent_options(_SYSTEM_PROMPT, max_turns=4)

    raw = ""
    usage = None
    async for message in query(prompt=instructions, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock) and block.text:
                    raw += block.text
        elif isinstance(message, ResultMessage):
            usage = usage_summary(message)

    raw = raw.strip()
    try:
        # Strip accidental ```json fences if the model added them.
        if raw.startswith("```"):
            raw = raw[raw.index("{") : raw.rindex("}") + 1]
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        data = {"subject": "Message from the CEO", "body": raw}

    data["usage"] = usage
    return data
