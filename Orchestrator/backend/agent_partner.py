"""
agent_partner.py — Agent 3: Personal / Partner Email Drafter (toggle-gated).

The CEO drafter (agent_ceo) is the default voice. When the user flips the
"Date Mode" toggle in the UI, the orchestrator routes drafting here instead:
a warm, genuine message to a partner — never corporate — and, when the brief
calls for it, a few concrete, thoughtful date ideas.

Same contract as agent_ceo.draft_email: returns {"subject", "body", "usage"}.
"""

import json

from claude_agent_sdk import query, AssistantMessage, ResultMessage
from claude_agent_sdk.types import TextBlock

from agent_config import agent_options, usage_summary

_SYSTEM_PROMPT = """You are writing a heartfelt email from someone to the person they love.
Your voice is:
- Warm, affectionate, and personal — like a real partner, never a CEO or a brand
- Genuine and specific — small, true-feeling details over generic flattery
- Playful and a little tender — sweet, not stiff; confident, not cheesy or over-the-top
- Plain-spoken — no corporate words, no buzzwords, no formal sign-offs

If the brief involves planning time together, an anniversary, a surprise, or
explicitly asks for date ideas, include 2-3 concrete, thoughtful date ideas.
Make each one specific and easy to picture (a vibe, a place type, a small touch
that shows you paid attention) — not a generic list. Weave them in naturally or
present them as a short list, whichever reads more warmly.

Output ONLY a JSON object with exactly two keys:
{"subject": "...", "body": "..."}

The body is plain text (no HTML), written in the first person to her directly.
End it with a warm, loving sign-off (e.g. a blank line, then something like
"All my love," or "Yours always," then a blank line, then "[Me]"). Keep the
[Me] placeholder so the sender can drop in their name.
Output nothing but the JSON — no markdown fences, no commentary."""


async def draft_email(instructions: str) -> dict:
    """Draft a warm, personal email to a partner. Returns {"subject", "body", "usage"}."""
    # Single model response; max_turns is just a safety ceiling (the model stops
    # itself at end_turn), mirroring agent_ceo so both drafters behave the same.
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
        data = {"subject": "A little something for you 💕", "body": raw}

    data["usage"] = usage
    return data
