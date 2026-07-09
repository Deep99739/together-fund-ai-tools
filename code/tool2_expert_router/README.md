# The Zone Expert Router

Local AI tool for routing founder requests to the best-fit experts in a modeled operator network.

## Features

- Founder-request intake
- Intent extraction for stage, urgency, domain, geography, and help type
- Expert-profile retrieval from local JSON data
- Ranked expert matching
- Expert graph/map view
- Primary expert, backup expert, and specialist-review routing
- Near-miss and rejection rationale
- Coverage-gap detection
- Generated intro copy and dispatch brief
- Visible execution trace in the UI and backend logs

## Stack

- Backend: Python, FastAPI, Uvicorn
- Frontend: React, TypeScript, Vite
- Data: local JSON expert profile set
- LLM providers: Gemini, NVIDIA NIM, Groq through shared provider fallback

## Structure

```text
tool2_expert_router/
  backend/
    server.py
    router_agent.py
    expert_profiles.json
    requirements.txt
  frontend/
    src/
    package.json
```

Shared provider configuration is in `../shared/llm_config.py`. Environment variables are loaded from `../.env`.

## Environment

Create the shared environment file from the `code/` directory:

```bash
cp .env.example .env
```

Set at least one provider key:

```bash
GEMINI_API_KEY=...
GEMINI_API_KEY_2=...
NVIDIA_API_KEY=...
GROQ_API_KEY=...
```

Provider order:

```text
Gemini 2.5 Flash → NVIDIA NIM DeepSeek V4 Flash → Groq Llama 3.3 70B
```

## Run

Backend:

```bash
cd code/tool2_expert_router/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python server.py
```

Backend URL:

```text
http://localhost:8001
```

Frontend:

```bash
cd code/tool2_expert_router/frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5174
```

Frontend URL:

```text
http://localhost:5174
```

## API

```text
GET  /api/health
GET  /api/network-stats
GET  /api/sample-queries
GET  /api/experts
POST /api/route
```

Example request:

```json
{
  "query": "Founder request or operating blocker..."
}
```

## Verification

Backend health check:

```bash
curl http://localhost:8001/api/health
```

Frontend production build:

```bash
cd code/tool2_expert_router/frontend
npm run build
```

## Trace output

The backend emits ordered trace steps through the shared reasoning logger. The frontend renders the same trace in the routing result.

Primary pipeline stages:

- founder-intent extraction
- expert profile retrieval
- role and evidence scoring
- near-miss calibration
- coverage-gap analysis
- dispatch-plan generation
