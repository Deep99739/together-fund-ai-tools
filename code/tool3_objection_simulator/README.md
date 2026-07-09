# Enterprise Objection Simulator

Local AI role-play tool for practicing enterprise buyer conversations and scoring founder responses against deal-stage and objection-handling criteria.

Live demo: https://objection-simulator-tan.vercel.app/

## Features

- Buyer persona selection
- Product and deal-context intake
- Difficulty selection
- Stateful buyer simulation
- Deal-stage progression
- Live deal-health metrics
- Objection-stack tracking
- Turn-level founder-response scoring
- Post-call coaching report
- Copyable markdown report
- Visible execution trace in the UI and backend logs

## Stack

- Backend: Python, FastAPI, Uvicorn
- Frontend: React, TypeScript, Vite
- Session state: process-local in-memory store
- LLM providers: Gemini, NVIDIA NIM, Groq through shared provider fallback

## Structure

```text
tool3_objection_simulator/
  backend/
    server.py
    simulator_agent.py
    personas.py
    coach.py
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
cd code/tool3_objection_simulator/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python server.py
```

Backend URL:

```text
http://localhost:8002
```

Frontend:

```bash
cd code/tool3_objection_simulator/frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5175
```

Frontend URL:

```text
http://localhost:5175
```

## API

```text
GET  /api/health
GET  /api/personas
POST /api/session/start
POST /api/session/respond
POST /api/session/coach
GET  /api/session/{session_id}
```

Example session request:

```json
{
  "persona_id": "fortune500_ciso",
  "product_context": "Product and deal context...",
  "difficulty": "skeptical",
  "meeting_objective": "Earn a credible next-step commitment from the buyer."
}
```

Example response request:

```json
{
  "session_id": "returned-session-id",
  "message": "Founder response..."
}
```

## Verification

Backend health check:

```bash
curl http://localhost:8002/api/health
```

Frontend production build:

```bash
cd code/tool3_objection_simulator/frontend
npm run build
```

## Trace output

The backend emits ordered trace steps through the shared reasoning logger. The frontend renders the same trace during the simulation.

Primary pipeline stages:

- persona initialization
- opening buyer question generation
- founder answer scoring
- deal-health update
- objection-stack update
- buyer follow-up generation
- coaching-report compilation
