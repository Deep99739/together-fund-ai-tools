"""HTTP API for the enterprise objection-simulation workflow."""

import os
import sys
import uuid
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

# Load provider credentials from the shared local environment file.
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# Resolve local tool modules and shared runtime utilities.
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))

from simulator_agent import SimulationSession
from coach import generate_coaching_report
from personas import get_all_personas

app = FastAPI(
    title="Enterprise Objection & Procurement Simulator",
    description="AI-powered adversarial sales training for Together Fund portfolio founders.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:5176", "http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session state is process-local for local runs.
sessions: dict[str, SimulationSession] = {}


class StartSessionRequest(BaseModel):
    persona_id: str
    product_context: str
    difficulty: str = "skeptical"
    meeting_objective: Optional[str] = None


class FounderMessageRequest(BaseModel):
    session_id: str
    message: str


class CoachingRequest(BaseModel):
    session_id: str


@app.get("/")
def root():
    return {
        "tool": "Enterprise Objection & Procurement Simulator",
        "description": "Together Fund's AI-powered sales training simulator",
        "version": "1.0.0",
        "endpoints": {
            "GET /api/personas": "List available buyer personas",
            "POST /api/session/start": "Start a new simulation session",
            "POST /api/session/respond": "Send a founder message and get buyer response",
            "POST /api/session/coach": "Generate post-simulation coaching report",
            "GET /api/health": "Health check",
        }
    }


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "active_sessions": len(sessions)}


@app.get("/api/personas")
def list_personas():
    """Return buyer persona options for session setup."""
    return {"personas": get_all_personas()}


@app.post("/api/session/start")
def start_session(request: StartSessionRequest):
    """Create a new simulation and return the opening buyer turn."""
    if not request.product_context.strip():
        raise HTTPException(status_code=400, detail="Product context is required")

    try:
        session = SimulationSession(
            persona_id=request.persona_id,
            product_context=request.product_context,
            difficulty=request.difficulty,
            meeting_objective=request.meeting_objective or "",
        )
        session_id = str(uuid.uuid4())[:8]
        sessions[session_id] = session

        opening = session.get_opening_message()

        return {
            "session_id": session_id,
            "opening": opening,
            "session": session.to_dict(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")


@app.post("/api/session/respond")
def respond_to_founder(request: FounderMessageRequest):
    """Score a founder response and return the next buyer turn."""
    session = sessions.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.is_complete:
        raise HTTPException(status_code=400, detail="This simulation has already ended")

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        response = session.respond_to_founder(request.message)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Response generation failed: {str(e)}")


@app.post("/api/session/coach")
def generate_coaching(request: CoachingRequest):
    """Generate a coaching report for an active session."""
    session = sessions.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if len(session.conversation_history) < 4:
        raise HTTPException(status_code=400, detail="Need at least 2 full exchanges before coaching analysis")

    try:
        session_data = session.to_dict()
        report = generate_coaching_report(session_data)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Coaching analysis failed: {str(e)}")


@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    """Return the latest state for a simulation session."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_dict()


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("Enterprise Objection & Procurement Simulator")
    print("   Together Fund Internal Tool")
    print("="*60)
    print(f"\n{len(get_all_personas())} buyer personas loaded")
    print("Primary LLM: configured provider chain")
    print("\nStarting server on http://localhost:8002")
    print("="*60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8002)
