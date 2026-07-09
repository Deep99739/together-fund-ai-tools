"""HTTP API for the architecture diligence workflow."""

import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))

from diligence_agent import analyze_startup
from anti_patterns import WRAPPER_ANTI_PATTERNS, DEPTH_DIMENSIONS

app = FastAPI(
    title="Architecture Diligence & Wrapper Detection Agent",
    description="AI-powered technical due diligence for AI-native architecture reviews.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:5176", "http://localhost:5177", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    document_text: str
    startup_name: str = "Startup"


@app.get("/")
def root():
    return {
        "tool": "Architecture Diligence & Wrapper Detection Agent",
        "description": "Together Fund's AI-powered technical due diligence engine",
        "version": "1.0.0",
    }


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "anti_patterns": len(WRAPPER_ANTI_PATTERNS), "dimensions": len(DEPTH_DIMENSIONS)}


@app.get("/api/anti-patterns")
def list_anti_patterns():
    """Return the wrapper-risk taxonomy used by the analyzer."""
    return {"anti_patterns": WRAPPER_ANTI_PATTERNS}


@app.get("/api/dimensions")
def list_dimensions():
    """Return the depth-scoring rubric."""
    return {"dimensions": DEPTH_DIMENSIONS}


@app.get("/api/sample-docs")
def get_sample_docs():
    """Return bundled sample documents for local review flows."""
    samples_dir = Path(__file__).parent.parent / "sample_data"
    samples = []
    if samples_dir.exists():
        for f in sorted(samples_dir.glob("*.md")):
            samples.append({
                "filename": f.name,
                "name": f.stem.replace("_", " ").title(),
                "content": f.read_text(),
            })
    return {"samples": samples}


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest):
    """Run the architecture diligence pipeline for submitted documentation."""
    if not request.document_text.strip():
        raise HTTPException(status_code=400, detail="Document text is required")

    if len(request.document_text) > 50000:
        raise HTTPException(status_code=400, detail="Document too large (max 50,000 characters)")

    try:
        result = analyze_startup(request.document_text, request.startup_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("🔬 Architecture Diligence & Wrapper Detection Agent")
    print("   Together Fund Internal Tool")
    print("="*60)
    print(f"\n🎯 {len(WRAPPER_ANTI_PATTERNS)} anti-patterns loaded")
    print(f"📊 {len(DEPTH_DIMENSIONS)} depth dimensions")
    print(f"🔑 Primary LLM: Google Gemini 2.5 Flash")
    print(f"\n🚀 Starting server on http://localhost:8003")
    print("="*60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8003)
