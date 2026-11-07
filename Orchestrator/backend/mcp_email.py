"""
mcp_email.py — the MCP integration for sending email.

This is what makes the pipeline an *MCP* pipeline. Instead of the orchestrator
reaching for SMTP directly, we expose a single `send_email` tool through an
in-process MCP server (Claude Agent SDK). Agent 2 then *calls that tool* — so
the email is delivered through MCP, exactly like any other model-invoked tool.

`build_email_server()` returns a fresh server plus an `outbox` dict that the
tool writes its outcome into. One server + outbox is built per request, so
concurrent pipeline runs never clobber each other's results.
"""

import asyncio
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from claude_agent_sdk import tool, create_sdk_mcp_server

# Fully-qualified name the model sees: mcp__<server>__<tool>.
EMAIL_TOOL = "mcp__email__send_email"


def _wrap_document(html_fragment: str) -> str:
    """Wrap the agent's HTML fragment in a minimal email document."""
    return (
        '<!DOCTYPE html>'
        '<html><head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '</head>'
        '<body style="margin:0;padding:0;background:#f4f4f4;">'
        f"{html_fragment}"
        '</body></html>'
    )


def _smtp_send_sync(to: str, subject: str, html_fragment: str) -> None:
    """Blocking SMTP send. Runs in a thread so it never blocks the event loop."""
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    sender = os.getenv("SMTP_FROM") or user

    if not user or not password:
        raise ValueError(
            "SMTP is not configured — set SMTP_USER and SMTP_PASS in "
            "Orchestrator/backend/.env"
        )
    if not to:
        raise ValueError("No recipient was provided to send_email")

    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(_wrap_document(html_fragment), "html", "utf-8"))

    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as srv:
            srv.login(user, password)
            srv.sendmail(sender, to, msg.as_string())
    else:
        with smtplib.SMTP(host, port, timeout=30) as srv:
            srv.starttls(context=context)
            srv.login(user, password)
            srv.sendmail(sender, to, msg.as_string())


def build_email_server():
    """Return (mcp_server, outbox) for a single pipeline run.

    The `outbox` dict is populated by the tool with what it actually sent
    (to/subject/html) and whether delivery succeeded — the orchestrator reads
    it after the agent finishes, rather than asking the model to echo the HTML
    back (which would double the output tokens).
    """
    outbox: dict = {}

    @tool(
        "send_email",
        "Send the finished HTML email to the recipient. Pass the recipient "
        "address, the subject line, and the full HTML body.",
        {"to": str, "subject": str, "html": str},
    )
    async def send_email(args: dict) -> dict:
        to = (args.get("to") or "").strip()
        subject = args.get("subject") or "Message from the CEO"
        html = args.get("html") or ""
        outbox.update(to=to, subject=subject, html=html)
        try:
            await asyncio.to_thread(_smtp_send_sync, to, subject, html)
            outbox["ok"] = True
            return {"content": [{"type": "text", "text": f"Delivered to {to}."}]}
        except Exception as exc:  # keep the agent loop alive; report as data
            outbox["ok"] = False
            outbox["error"] = str(exc)
            return {
                "content": [{"type": "text", "text": f"Delivery failed: {exc}"}],
                "is_error": True,
            }

    server = create_sdk_mcp_server(name="email", version="1.0.0", tools=[send_email])
    return server, outbox
