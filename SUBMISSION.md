# Submission Notes

## Tools

- `code/tool1_architecture_diligence` — local architecture diligence tool for scoring technical depth and wrapper-risk signals from startup architecture notes.
- `code/tool2_expert_router` — local expert-routing tool for matching founder requests to a modeled operator network and generating a dispatch brief.
- `code/tool3_objection_simulator` — local enterprise-buyer simulation tool for practicing objections and generating coaching feedback.

## Environment variables

Create `code/.env` from `code/.env.example` and provide at least one LLM provider key.

```bash
GEMINI_API_KEY=...
GEMINI_API_KEY_2=...
NVIDIA_API_KEY=...
GROQ_API_KEY=...
```

The shared provider chain is:

```text
Gemini 2.5 Flash → NVIDIA NIM DeepSeek V4 Flash → Groq Llama 3.3 70B
```

## Local ports

```text
Tool 1 backend:  http://localhost:8003
Tool 1 frontend: http://localhost:5173

Tool 2 backend:  http://localhost:8001
Tool 2 frontend: http://localhost:5174

Tool 3 backend:  http://localhost:8002
Tool 3 frontend: http://localhost:5175
```

## Hosted frontends

```text
Tool 1: https://tool1-architecture-diligence.vercel.app/
Tool 2: https://expert-router.vercel.app/
Tool 3: https://objection-simulator-tan.vercel.app/
```

## Written artifacts

- `ideation.md` — Part 1 ideation document with six tool ideas, prioritized shortlist, and risks.
- `writeup.md` — combined technical writeup for the three implemented tools.
- `writeup.pdf` — PDF export of the technical writeup.
- `README.md` — repository overview.
- `code/*/README.md` — install and run instructions for each tool.

## Notes

- All three tools run locally.
- Sample data is synthetic and included in the repository.
- Visible reasoning is shown in the frontend and emitted in backend logs.
- Each tool is independently runnable, while sharing provider configuration from `code/shared`.
