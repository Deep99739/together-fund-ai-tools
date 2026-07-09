"""HTTP API for The Zone expert-routing workflow."""

import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load provider credentials from the shared local environment file.
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# Resolve local tool modules and shared runtime utilities.
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))

from router_agent import route_query, load_expert_profiles, network_stats


SAMPLE_QUERIES = [
    {
        "label": "Security pilot blocked",
        "query": "We are an Indian AI security startup trying to land our first Fortune 500 pilot. The buyer is asking for SOC2, data residency, and a formal security review. We don't know if this is a sales problem, compliance problem, or product architecture problem.",
    },
    {
        "label": "US enterprise GTM",
        "query": "Our PLG motion is working for technical SMB users, but enterprise shadow IT adoption is creating pull from larger accounts. We need to build an outbound US enterprise sales motion without hiring the wrong VP Sales too early.",
    },
    {
        "label": "Entity flip before Series A",
        "query": "We need to flip our Indian entity to a Delaware C-Corp before our Series A. We are worried about IP assignment, ESOP pool sizing, transfer pricing, and how this affects the next financing round.",
    },
    {
        "label": "AI infra cost burn",
        "query": "We are burning through cloud credits faster than expected while serving LLM inference on GCP. We need help reducing cost per request before credits run out and before usage scales 10x.",
    },
    {
        "label": "Healthcare AI procurement",
        "query": "We are building a clinical AI workflow product and a US hospital wants a pilot. They are asking about HIPAA, EHR integration, patient safety, and procurement steps. We need to know who can prepare us.",
    },
]

app = FastAPI(
    title="The Zone — Expert Network Router",
    description="AI-powered routing engine for Together Fund's expert network. Matches founder queries to the best experts from The Zone.",
    version="1.0.0",
)

# Local development origins for the Vite clients.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str


class ExpertResponse(BaseModel):
    pass  # Response shape is assembled by the routing pipeline.


@app.get("/")
def root():
    return {
        "tool": "The Zone — Expert Network Router",
        "description": "Together Fund's AI-powered expert matching engine",
        "version": "1.0.0",
        "endpoints": {
            "POST /api/route": "Submit a founder query to find matching experts",
            "GET /api/experts": "List all experts in The Zone network",
            "GET /api/network-stats": "Summarize demo network coverage",
            "GET /api/sample-queries": "Return polished demo scenarios",
            "GET /api/health": "Health check",
        }
    }


@app.get("/api/health")
def health_check():
    experts = load_expert_profiles()
    return {"status": "healthy", "experts_loaded": len(experts), "network_stats": network_stats(experts)}


@app.get("/api/network-stats")
def get_network_stats():
    """Return high-level stats for the modeled expert network slice."""
    return network_stats(load_expert_profiles())


@app.get("/api/sample-queries")
def get_sample_queries():
    """Return seeded scenarios for local evaluation."""
    return {"samples": SAMPLE_QUERIES}


@app.get("/api/experts")
def list_experts():
    """List all experts in The Zone network."""
    experts = load_expert_profiles()
    return {
        "total_experts": len(experts),
        "experts": [
            {
                "id": e["id"],
                "name": e["name"],
                "title": e["title"],
                "location": e["location"],
                "domains": e["domains"],
                "computed_roles": e.get("computed_roles", []),
                "stage_fit": e.get("stage_fit", []),
                "availability": e.get("availability", "unknown"),
            }
            for e in experts
        ]
    }


@app.post("/api/route")
def route_founder_query(request: QueryRequest):
    """
    Route a founder query through the expert-scoring pipeline.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    if len(request.query) > 2000:
        raise HTTPException(status_code=400, detail="Query too long (max 2000 characters)")

    try:
        result = route_query(request.query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("The Zone — Expert Network Router")
    print("   Expert-network dispatch workflow")
    print("="*60)
    print(f"\nLoaded {len(load_expert_profiles())} expert profiles")
    print("Starting server on http://localhost:8001")
    print("="*60 + "\n")
    uvicorn.run(app, host="127.0.0.1", port=8001)
