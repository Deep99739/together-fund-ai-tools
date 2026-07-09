# Architecture Diligence

Local AI tool for reviewing startup architecture notes and identifying technical depth, defensibility signals, and wrapper-risk patterns.

## Features

- Architecture document ingestion
- Component extraction for models, data pipelines, infrastructure, APIs, custom logic, and agentic patterns
- Technical-depth scoring across five diligence dimensions
- Wrapper anti-pattern detection
- Source-grounded reliability checks
- Risk register and follow-up diligence questions
- Copyable markdown diligence brief
- Visible execution trace in the UI and backend logs

## Stack

- Backend: Python, FastAPI, Uvicorn
- Frontend: React, TypeScript, Vite
- LLM providers: Gemini, NVIDIA NIM, Groq through shared provider fallback

## Structure

```text
tool1_architecture_diligence/
  backend/
    server.py
    diligence_agent.py
    anti_patterns.py
    requirements.txt
  frontend/
    src/
    package.json
  sample_data/
    deeptech_startup.md
    grayzone_startup.md
    wrapper_startup.md
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
cd code/tool1_architecture_diligence/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python server.py
```

Backend URL:

```text
http://localhost:8003
```

Frontend:

```bash
cd code/tool1_architecture_diligence/frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Frontend URL:

```text
http://localhost:5173
```

## API

```text
GET  /api/health
GET  /api/sample-docs
GET  /api/anti-patterns
GET  /api/dimensions
POST /api/analyze
```

Example request:

```json
{
  "startup_name": "Example Startup",
  "document_text": "Architecture notes..."
}
```

## Verification

Backend health check:

```bash
curl http://localhost:8003/api/health
```

Frontend production build:

```bash
cd code/tool1_architecture_diligence/frontend
npm run build
```

## Trace output

The backend emits ordered trace steps through the shared reasoning logger. The frontend renders the same trace in the result view.

Primary pipeline stages:

- component extraction
- wrapper anti-pattern detection
- technical-depth scoring
- diligence question generation
- risk-register calibration
- final report assembly
