"""
Sovereign AI Scientist — API Server
Serves the dashboard and exposes the research pipeline + verification endpoints.

Auth: Uses deTERMinal grant-based wallet signature (free 1M tokens).
Env vars needed: WALLET_ADDRESS, WALLET_PRIVATE_KEY
"""

import os
from dotenv import load_dotenv
load_dotenv()  # Load .env file

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent.scientist import SovereignScientist


# ── State ────────────────────────────────────────────
agent: SovereignScientist | None = None
current_run: dict | None = None
run_status: str = "idle"  # idle | running | complete | error
run_error: str = ""
current_milestone: str = ""
completed_milestones: list = []


# ── App ──────────────────────────────────────────────
app = FastAPI(
    title="Sovereign AI Scientist",
    description="Verifiable research discovery agent on EigenCloud",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ───────────────────────────────────────────
class StartRequest(BaseModel):
    topic: str
    seed: int = 42
    num_hypotheses: int = 3


# ── Pipeline Runner ──────────────────────────────────
def run_pipeline_sync(topic: str):
    global current_run, run_status, run_error, current_milestone, completed_milestones
    try:
        def on_milestone(ms: str):
            global current_milestone, completed_milestones
            if current_milestone and current_milestone not in ("STARTING", "DONE", "ERROR"):
                if current_milestone not in completed_milestones:
                    completed_milestones.append(current_milestone)
            current_milestone = ms
            if ms == "DONE":
                for m in ["M1_IDEATION", "M2_DESIGN", "M3_ANALYSIS", "M4_WRITING"]:
                    if m not in completed_milestones:
                        completed_milestones.append(m)

        result = agent.run_pipeline(topic, on_milestone=on_milestone)
        current_run = result
        run_status = "complete"
    except Exception as e:
        run_status = "error"
        run_error = str(e)
        current_milestone = "ERROR"


# ── API Endpoints ────────────────────────────────────

@app.post("/api/start")
async def start_research(req: StartRequest, background_tasks: BackgroundTasks):
    global agent, run_status, run_error, current_run, current_milestone, completed_milestones

    wallet_address = os.environ.get("WALLET_ADDRESS", "")
    private_key = os.environ.get("WALLET_PRIVATE_KEY", "")

    if not wallet_address or not private_key:
        raise HTTPException(
            400,
            "WALLET_ADDRESS and WALLET_PRIVATE_KEY env vars required. "
            "Get free tokens at https://determinal.eigenarcade.com"
        )

    agent = SovereignScientist(
        wallet_address=wallet_address,
        private_key=private_key,
        seed=req.seed,
    )
    run_status = "running"
    run_error = ""
    current_run = None
    current_milestone = "STARTING"
    completed_milestones = []

    background_tasks.add_task(run_pipeline_sync, req.topic)

    return {
        "status": "started",
        "topic": req.topic,
        "seed": req.seed,
        "model": agent.model,
    }


@app.get("/api/status")
async def get_status():
    log_entries = []
    if agent:
        for e in agent.audit_log:
            log_entries.append({
                "step_id": e.step_id,
                "milestone": e.milestone,
                "action": e.action,
                "prompt_hash": e.prompt_hash[:16] + "...",
                "output_hash": e.output_hash[:16] + "...",
                "output_preview": e.output_preview[:200],
                "timestamp": e.timestamp,
                "verified": e.verified,
                "verification_match": e.verification_match,
            })

    return {
        "status": run_status,
        "current_milestone": current_milestone,
        "completed_milestones": completed_milestones,
        "error": run_error if run_status == "error" else None,
        "steps_completed": len(log_entries),
        "audit_log": log_entries,
    }


@app.get("/api/results")
async def get_results():
    if not current_run:
        raise HTTPException(404, "No results yet")
    return current_run


@app.post("/api/verify/{step_id}")
async def verify_step(step_id: str):
    """
    THE MONEY SHOT: Re-execute a step on EigenAI.
    Determinism guarantee: same input + seed = same output hash.
    """
    if not agent:
        raise HTTPException(400, "No agent initialized")

    result = agent.verify_step(step_id)

    if "error" in result:
        raise HTTPException(404, result["error"])

    return result


@app.get("/api/audit")
async def get_full_audit():
    if not agent:
        return {"audit_log": []}
    return {"audit_log": agent.get_audit_log()}


@app.get("/api/health")
async def health():
    return {"status": "ok", "agent_ready": agent is not None}


# ── Serve Frontend ───────────────────────────────────
from fastapi.responses import FileResponse

@app.get("/app")
async def serve_app():
    return FileResponse("frontend/app.html")

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
