"""
main.py — Pure Python Orchestrator

Coordinates the agent email pipeline:
  Agent 1 (agent_ceo)     -> drafts a CEO-voice email from instructions
  Agent 3 (agent_partner) -> drafts a warm, personal email to a partner,
                             with date ideas (used when "Date Mode" is on)
  Agent 2 (agent_sender)  -> formats the draft as HTML and delivers it via the
                             MCP send_email tool (see mcp_email.py)

A per-request `mode` ("ceo" | "partner") picks which drafter runs and which
HTML template the sender uses. The orchestrator itself contains zero AI and
never touches SMTP directly — it just runs each agent in sequence and streams
progress (and token usage) back to the frontend over Server-Sent Events (SSE).
"""

import json
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent_ceo import draft_email as draft_ceo_email
from agent_partner import draft_email as draft_partner_email
from agent_sender import format_and_send

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="CEO Email Pipeline", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class PipelineRequest(BaseModel):
    instructions: str
    email_to: str
    mode: str = "ceo"  # "ceo" (default) or "partner" (Date Mode toggle)


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _run_pipeline(instructions: str, email_to: str, mode: str = "ceo"):
    """Run the agent pipeline, yielding SSE events for the frontend.

    `mode` selects the drafter (CEO vs. partner) and the sender's HTML template.
    """
    partner = mode == "partner"
    draft_email = draft_partner_email if partner else draft_ceo_email
    drafter_name = "Partner Agent" if partner else "CEO Agent"

    totals = {"input": 0, "output": 0, "total": 0, "cost_usd": 0.0}

    def _accumulate(usage):
        if not usage:
            return
        totals["input"] += usage.get("input", 0)
        totals["output"] += usage.get("output", 0)
        totals["total"] += usage.get("total", 0)
        if usage.get("cost_usd"):
            totals["cost_usd"] += usage["cost_usd"]

    # ── Agent 1 / Agent 3: draft the email in the selected voice ─────────────
    yield _sse({"step": 1, "status": "working", "msg": f"{drafter_name} is drafting your email…"})

    try:
        draft = await draft_email(instructions)
    except Exception as exc:
        yield _sse({"step": 1, "status": "error", "msg": f"{drafter_name} failed: {exc}"})
        return

    _accumulate(draft.get("usage"))
    subject = draft.get("subject", "A little something for you" if partner else "Message from the CEO")
    body = draft.get("body", "")

    yield _sse({
        "step": 1,
        "status": "done",
        "msg": "Draft complete",
        "subject": subject,
        "body": body,
        "usage": draft.get("usage"),
    })

    # ── Agent 2: format to HTML and deliver via the MCP email tool ────────────
    yield _sse({"step": 2, "status": "working", "msg": "HTML Agent is formatting your email…"})

    result = None
    try:
        async for ev in format_and_send(subject, body, email_to, mode):
            if ev["phase"] == "sending":
                yield _sse({"step": 2, "status": "sending", "msg": "Calling the MCP email tool…"})
            elif ev["phase"] == "done":
                result = ev
    except Exception as exc:
        yield _sse({"step": 2, "status": "error", "msg": f"HTML Agent failed: {exc}"})
        return

    _accumulate(result.get("usage") if result else None)

    if not result or not result.get("ok"):
        # An explicit error means the send_email tool ran and SMTP rejected it.
        # No error means the formatter agent finished without ever calling the
        # tool — a different failure that needs a different fix, so say which.
        err = (result or {}).get("error")
        if not err:
            err = (
                "the formatter agent never called the send_email tool "
                "(no SMTP attempt was made) — check the backend console"
            )
        yield _sse({"step": 2, "status": "error", "msg": f"Send failed: {err}"})
        return

    yield _sse({
        "step": 2,
        "status": "done",
        "msg": f"Email delivered to {email_to} via MCP",
        "html_preview": result.get("html", ""),
        "usage": result.get("usage"),
    })

    yield _sse({"step": "complete", "status": "done", "msg": "Pipeline complete ✓", "totals": totals})


@app.post("/pipeline")
async def pipeline(req: PipelineRequest):
    return StreamingResponse(
        _run_pipeline(req.instructions, req.email_to, req.mode),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/health")
async def health():
    return {"ok": True}


# Serve the frontend from /
_frontend = Path(__file__).parent.parent / "frontend"
if _frontend.exists():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="static")
