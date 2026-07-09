"""Post-call coaching report generator for completed simulations."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))

from llm_config import get_llm
from reasoning_logger import ReasoningLogger


def generate_coaching_report(session_data: dict) -> dict:
    """Generate a structured coaching report from a completed session snapshot."""
    logger = ReasoningLogger(task_name="Post-Simulation Coaching Analysis")
    llm = get_llm()

    conversation = session_data.get("conversation", [])
    persona_name = session_data.get("persona_name", "Unknown Buyer")
    persona_title = session_data.get("persona_title", "Unknown")
    company_type = session_data.get("company_type", "Unknown")
    product_context = session_data.get("product_context", "")
    deal_health = session_data.get("deal_health", {})
    battle_replay = session_data.get("battle_replay", [])
    objection_stack = session_data.get("objection_stack", [])

    # Prepare the transcript payload used by the coaching model.
    logger.start_step(
        title="Transcript Analysis Preparation",
        description="Formatting the simulation transcript for analysis.",
        step_type="processing",
        input_data=f"{len(conversation)} messages in transcript"
    )

    transcript_text = ""
    for msg in conversation:
        role_label = persona_name if msg["role"] == "buyer" else "FOUNDER"
        transcript_text += f"\n{role_label}: {msg['content']}\n"

    logger.end_step(output_data=f"Transcript: {len(transcript_text)} characters, {len(conversation)} turns")

    # Open the trace step for the main coaching evaluation.
    logger.start_step(
        title="Strengths Analysis",
        description="Identifying what the founder did well during the simulation.",
        step_type="decision",
    )

    # Request a board-ready coaching payload from the provider.
    coaching_prompt = f"""You are a world-class enterprise sales coach. You've been observing a practice negotiation between a founder (who is building an AI product from India and trying to sell to the US enterprise market) and a buyer persona.

BUYER PERSONA:
- Name: {persona_name}
- Title: {persona_title}  
- Company: {company_type}

PRODUCT CONTEXT:
{product_context}

FULL TRANSCRIPT:
{transcript_text}

DEAL HEALTH AT END:
{json.dumps(deal_health, indent=2)}

BATTLE REPLAY:
{json.dumps(battle_replay, indent=2)}

OBJECTION STACK:
{json.dumps(objection_stack, indent=2)}

Analyze this simulation and produce a board-ready coaching report. Respond in JSON with these keys:

{{
  "overall_score": <number from 1-10>,
  "score_label": "<label like 'Needs Work', 'Promising', 'Strong', 'Excellent'>",
  "summary": "<2-3 sentence executive summary of the founder's performance>",
  "board_summary": "<one paragraph a partner could read before coaching the founder>",
  "deal_health_summary": "<what happened to trust, risk, budget confidence, urgency, and procurement friction>",
  "strongest_moment": {{
    "quote": "<short transcript evidence>",
    "why_it_worked": "<why this improved the deal>"
  }},
  "weakest_moment": {{
    "quote": "<short transcript evidence>",
    "why_it_hurt": "<why this damaged the deal>"
  }},
  "strengths": [
    {{
      "title": "<strength title>",
      "detail": "<specific example from the transcript>",
      "impact": "<why this matters in a real enterprise deal>"
    }}
  ],
  "weaknesses": [
    {{
      "title": "<weakness title>",
      "detail": "<specific example from the transcript>",
      "missed_opportunity": "<what they should have said or done instead>"
    }}
  ],
  "coaching_tips": [
    {{
      "tip": "<actionable advice>",
      "practice": "<a specific exercise to improve this skill>"
    }}
  ],
  "objection_handling_breakdown": [
    {{
      "objection": "<the buyer's objection>",
      "founder_response": "<summary of how the founder responded>",
      "rating": "<Excellent/Good/Fair/Poor>",
      "better_response": "<what a top seller would have said>"
    }}
  ],
  "next_call_plan": [
    "<specific preparation item for the next call>"
  ],
  "recommended_founder_script": "<a concise rewritten answer the founder should practice>",
  "readiness_assessment": "<1-2 sentences on whether this founder is ready for a real call with this buyer type>"
}}

Be specific and reference actual quotes from the transcript. Be constructive but honest.
Provide 2-4 strengths, 2-4 weaknesses, 3-5 coaching tips, and break down each major objection.
Respond ONLY with valid JSON."""

    response = llm.chat(
        messages=[
            {"role": "system", "content": "You are an expert enterprise sales coach. Respond only in valid JSON."},
            {"role": "user", "content": coaching_prompt}
        ],
        temperature=0.5,
        max_tokens=3000,
    )

    logger.end_step(output_data="Strengths identified from transcript analysis")

    logger.start_step(
        title="Coaching Report Compilation",
        description="Compiling the final coaching report with scores, strengths, weaknesses, and actionable tips.",
        step_type="generation",
    )

    try:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
        report = json.loads(cleaned)
    except json.JSONDecodeError:
        report = {
            "overall_score": 5,
            "score_label": "Needs Review",
            "summary": "The coaching analysis could not be fully parsed. Please review the transcript manually.",
            "board_summary": "The report parser could not recover a full coaching payload. The transcript remains available for manual review.",
            "deal_health_summary": "Deal-health analysis unavailable because the coaching response was not valid JSON.",
            "strongest_moment": {"quote": "", "why_it_worked": "Unavailable."},
            "weakest_moment": {"quote": "", "why_it_hurt": "Unavailable."},
            "strengths": [{"title": "Engaged in the simulation", "detail": "The founder participated in the full simulation.", "impact": "Practice is essential for improvement."}],
            "weaknesses": [{"title": "Analysis incomplete", "detail": "The AI coaching analysis encountered a parsing issue.", "missed_opportunity": "Try running the simulation again for a complete analysis."}],
            "coaching_tips": [{"tip": "Practice regularly with different buyer personas.", "practice": "Run at least 3 simulations per week."}],
            "objection_handling_breakdown": [],
            "next_call_plan": ["Review the transcript manually and rerun coaching."],
            "recommended_founder_script": "Use a concise answer that names proof, risk controls, buyer-specific relevance, and a clear next step.",
            "readiness_assessment": "Additional practice recommended."
        }

    logger.end_step(output_data=f"Report complete. Score: {report.get('overall_score', 'N/A')}/10 — {report.get('score_label', '')}")

    report["reasoning_log"] = logger.get_all_steps()
    return report
