"""
agent_sender.py — Agent 2: HTML Formatter + MCP Sender.

Takes the CEO's plain-text draft, turns it into a polished HTML email, and
delivers it by *calling the MCP `send_email` tool* (see mcp_email.py). The HTML
is produced exactly once — as the tool's argument — so we never pay output
tokens to both generate and echo it.

`format_and_send` is an async generator: it yields progress phases as they
happen ("formatting" → "sending"), then a final "done" phase carrying the
delivered HTML, success flag, and token usage.
"""

from claude_agent_sdk import query, AssistantMessage, ResultMessage
from claude_agent_sdk.types import ToolUseBlock

from agent_config import agent_options, usage_summary
from mcp_email import build_email_server, EMAIL_TOOL

# The tool-calling contract is identical in both modes — only the visual design
# brief changes — so we share one footer of rules and swap the design section.
_TOOL_RULES = """You have exactly one tool: send_email(to, subject, html).
- Call it immediately, with no text before the call.
- Put your HTML ONLY in the `html` argument — never write the HTML as a message.
- Use the recipient and subject given to you, verbatim.
- After it returns, reply with a single short confirmation sentence.
- If send_email returns an error, do NOT retry it — just reply with the error."""

_CEO_PROMPT = """You are an expert HTML email designer with one job: turn a plain-text
draft into a polished HTML email and send it.

Design requirements for the HTML:
- Inline CSS only (email clients strip <style> blocks)
- Table-based layout for maximum client compatibility
- Dark navy header (#1a1a2e) with the company name centred in white
- White content area, generous padding, ~1.6 line-height
- Preserve paragraph breaks; render bullet lists as <ul> when the draft has them
- Subtle footer (#f4f4f4) with a thin top border and a placeholder contact line
- Max-width 600px, centred with auto margins
- Start from a <div> or <table> wrapper — no <!DOCTYPE>/<html>/<head>/<body>

""" + _TOOL_RULES

_PARTNER_PROMPT = """You are an expert HTML email designer with one job: turn a plain-text
love note into a warm, personal HTML email and send it. This is a private message
to someone's partner — it must NOT look corporate. No company name, no logo, no
business footer.

Design requirements for the HTML:
- Inline CSS only (email clients strip <style> blocks)
- Table-based layout for maximum client compatibility
- A soft, romantic header with a warm blush-to-peach gradient
  (e.g. linear-gradient(135deg,#ff7eb3,#ff9a8b)) and a small heart ♥ or the
  subject centred in white — NEVER a company name
- Cream/white content area (#fffafa), generous padding, ~1.75 line-height,
  an elegant serif body font (Georgia)
- Preserve paragraph breaks; if the draft lists date ideas, render them as a
  styled <ul> (or small cards) so each idea stands out
- A gentle footer with a soft top border and a sweet one-line closer (e.g.
  "Written just for you ♥") — no contact info, no unsubscribe
- Max-width 600px, centred with auto margins
- Start from a <div> or <table> wrapper — no <!DOCTYPE>/<html>/<head>/<body>

""" + _TOOL_RULES


async def format_and_send(subject: str, body: str, to: str, mode: str = "ceo"):
    """Format the draft as HTML and deliver it via the MCP email tool.

    `mode` selects the visual template: "ceo" (corporate) or "partner" (romantic).

    Yields:
        {"phase": "formatting"}
        {"phase": "sending"}                      # emitted when the tool fires
        {"phase": "done", ok, html, subject, error, usage}
    """
    server, outbox = build_email_server()
    system_prompt = _PARTNER_PROMPT if mode == "partner" else _CEO_PROMPT
    options = agent_options(
        system_prompt,
        # Happy path is 2 turns (call send_email, then confirm). The ceiling is
        # generous so an extra internal step never trips it; the "don't retry"
        # rule in the system prompt keeps a failed send from burning the budget.
        max_turns=6,
        allowed_tools=[EMAIL_TOOL],
        mcp_servers={"email": server},
    )
    prompt = f"Recipient: {to}\nSubject: {subject}\n\n{body}"

    yield {"phase": "formatting"}

    usage = None
    announced_send = False
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if (
                    isinstance(block, ToolUseBlock)
                    and block.name == EMAIL_TOOL
                    and not announced_send
                ):
                    announced_send = True
                    yield {"phase": "sending"}
        elif isinstance(message, ResultMessage):
            usage = usage_summary(message)

    yield {
        "phase": "done",
        "ok": outbox.get("ok", False),
        "html": outbox.get("html", ""),
        "subject": outbox.get("subject", subject),
        "error": outbox.get("error"),
        "usage": usage,
    }
