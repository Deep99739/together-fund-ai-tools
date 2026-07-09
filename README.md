# together-fund-ai-tools

Three local AI tools built with FastAPI, React, TypeScript, and Vite.

## Tools

- `code/tool1_architecture_diligence` — reviews startup architecture notes, scores technical depth, and flags wrapper-risk patterns. [Live demo](https://tool1-architecture-diligence.vercel.app/)
- `code/tool2_expert_router` — routes founder requests to relevant experts from a modeled operator network. [Live demo](https://expert-router.vercel.app/)
- `code/tool3_objection_simulator` — simulates enterprise buyer conversations and scores founder responses. [Live demo](https://objection-simulator-tan.vercel.app/)

Each tool has its own backend, frontend, and README.

## Setup

Create the shared environment file:

```bash
cd code
cp .env.example .env
```

Add one or more provider keys:

```bash
GEMINI_API_KEY=...
GEMINI_API_KEY_2=...
NVIDIA_API_KEY=...
GROQ_API_KEY=...
```

## Run

Open the README for the tool you want to run:

- [Architecture Diligence](code/tool1_architecture_diligence/README.md)
- [The Zone Expert Router](code/tool2_expert_router/README.md)
- [Enterprise Objection Simulator](code/tool3_objection_simulator/README.md)

## Tech stack

- Python
- FastAPI
- React
- TypeScript
- Vite

## Repository layout

```text
code/
  shared/
  tool1_architecture_diligence/
  tool2_expert_router/
  tool3_objection_simulator/
```
