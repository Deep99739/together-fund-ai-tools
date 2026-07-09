"""
Enterprise objection-simulation session engine.

Maintains buyer persona state, deal-stage transitions, objection tracking,
turn-level scoring, and recovery behavior for malformed provider output.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))

from llm_config import get_llm
from reasoning_logger import ReasoningLogger
from personas import get_persona


CONVERSATION_STAGES = [
    {
        "id": "discovery",
        "label": "Discovery",
        "description": "Buyer tests whether the founder understands the business problem and buying context.",
    },
    {
        "id": "technical_validation",
        "label": "Technical validation",
        "description": "Buyer probes architecture, integration, reliability, and evidence.",
    },
    {
        "id": "security_review",
        "label": "Security review",
        "description": "Buyer evaluates data handling, compliance, risk controls, and vendor trust.",
    },
    {
        "id": "procurement",
        "label": "Procurement",
        "description": "Buyer pressure-tests approval path, stakeholders, legal review, and purchasing process.",
    },
    {
        "id": "pricing_negotiation",
        "label": "Pricing negotiation",
        "description": "Buyer challenges ROI, budget fit, and commercial structure.",
    },
    {
        "id": "next_step_close",
        "label": "Next-step close",
        "description": "Buyer decides whether the founder earned a clear next action.",
    },
]

STAGE_IDS = {stage["id"] for stage in CONVERSATION_STAGES}

OBJECTION_STACK_TEMPLATE = [
    {
        "id": "security",
        "label": "Security proof",
        "description": "SOC2, penetration testing, access controls, vendor risk process.",
        "status": "watch",
        "severity": 58,
    },
    {
        "id": "data_residency",
        "label": "Data residency",
        "description": "Where customer data is processed, retained, logged, and deleted.",
        "status": "unopened",
        "severity": 48,
    },
    {
        "id": "integration",
        "label": "Integration burden",
        "description": "Implementation effort, APIs, SDKs, migration risk, workflow change.",
        "status": "watch",
        "severity": 52,
    },
    {
        "id": "budget",
        "label": "Budget confidence",
        "description": "ROI proof, procurement timing, pricing model, expansion case.",
        "status": "unopened",
        "severity": 45,
    },
    {
        "id": "procurement",
        "label": "Procurement path",
        "description": "Legal, vendor onboarding, security review, contract vehicle, buying committee.",
        "status": "watch",
        "severity": 60,
    },
    {
        "id": "champion",
        "label": "Champion risk",
        "description": "Whether an internal buyer has enough conviction to sponsor the deal.",
        "status": "unopened",
        "severity": 42,
    },
    {
        "id": "vendor_viability",
        "label": "Vendor viability",
        "description": "Startup maturity, references, support quality, and long-term survivability.",
        "status": "unopened",
        "severity": 50,
    },
]

DIFFICULTY_SETTINGS = {
    "friendly": {
        "label": "Friendly",
        "behavior": "Constructive buyer. Ask hard questions, but reward good answers and help the founder find a path.",
        "trust_offset": 8,
        "risk_offset": -6,
    },
    "skeptical": {
        "label": "Skeptical",
        "behavior": "Realistic senior buyer. Fair, specific, and impatient with vague claims.",
        "trust_offset": 0,
        "risk_offset": 0,
    },
    "hostile_procurement": {
        "label": "Hostile procurement",
        "behavior": "Adversarial enterprise gatekeeper. Press on compliance gaps, approval path, budget, and vendor risk.",
        "trust_offset": -8,
        "risk_offset": 10,
    },
}


def clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, value))


def clean_json_response(response: str) -> dict:
    """Parse a JSON payload from provider output."""
    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def extract_json_string_field(response: str, field_name: str) -> str:
    """Recover a string field from malformed provider JSON when possible."""
    marker = f'"{field_name}"'
    start = response.find(marker)
    if start == -1:
        return ""

    colon = response.find(":", start + len(marker))
    if colon == -1:
        return ""

    quote = response.find('"', colon + 1)
    if quote == -1:
        return ""

    value_chars: list[str] = []
    escaped = False
    for char in response[quote + 1:]:
        if escaped:
            escapes = {
                '"': '"',
                "\\": "\\",
                "/": "/",
                "b": "\b",
                "f": "\f",
                "n": "\n",
                "r": "\r",
                "t": "\t",
            }
            value_chars.append(escapes.get(char, char))
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            break
        value_chars.append(char)

    return "".join(value_chars).strip()


class SimulationSession:
    """State container for one founder-versus-buyer simulation."""

    def __init__(
        self,
        persona_id: str,
        product_context: str,
        difficulty: str = "skeptical",
        meeting_objective: str = "",
    ):
        self.persona_id = persona_id
        self.persona = get_persona(persona_id)
        if not self.persona:
            raise ValueError(f"Unknown persona: {persona_id}")

        self.product_context = product_context
        self.difficulty = difficulty if difficulty in DIFFICULTY_SETTINGS else "skeptical"
        self.meeting_objective = meeting_objective.strip() or "Earn a credible next-step commitment from the buyer."
        self.conversation_history: list[dict] = []
        self.reasoning_log: list[dict] = []
        self.logger = ReasoningLogger(task_name=f"Enterprise Objection Simulation — {self.persona['name']}")
        self.turn_count = 0
        self.is_complete = False
        self.llm = get_llm()

        self.current_stage = "discovery"
        self.deal_health = self._initial_deal_health()
        self.objection_stack = [dict(item) for item in OBJECTION_STACK_TEMPLATE]
        self.turn_evaluations: list[dict] = []
        self.battle_replay: list[dict] = []
        self.latest_strategy = ""
        self.latest_evaluation_status = "ready"

    def _initial_deal_health(self) -> dict:
        setting = DIFFICULTY_SETTINGS[self.difficulty]
        compliance = self.persona.get("compliance_sensitivity", "").lower()
        compliance_boost = 12 if "extreme" in compliance else 8 if "very" in compliance else 0
        procurement_power = self.persona.get("procurement_power", "").lower()
        procurement_boost = 8 if "controls" in procurement_power or "veto" in procurement_power else 4

        return {
            "buyer_trust": clamp(48 + setting["trust_offset"]),
            "compliance_risk": clamp(58 + compliance_boost + setting["risk_offset"]),
            "budget_confidence": clamp(46 + setting["trust_offset"]),
            "urgency": 42,
            "procurement_friction": clamp(60 + procurement_boost + setting["risk_offset"]),
        }

    def _stage_label(self, stage_id: Optional[str] = None) -> str:
        target = stage_id or self.current_stage
        for stage in CONVERSATION_STAGES:
            if stage["id"] == target:
                return stage["label"]
        return "Discovery"

    def _apply_health_delta(self, delta: dict) -> None:
        for key in self.deal_health:
            try:
                self.deal_health[key] = clamp(int(self.deal_health[key]) + int(delta.get(key, 0)))
            except (TypeError, ValueError):
                continue

    def _apply_objection_updates(self, objections: list[dict]) -> None:
        by_id = {item["id"]: item for item in self.objection_stack}
        for objection in objections[:5]:
            objection_id = objection.get("id")
            if objection_id not in by_id:
                continue
            target = by_id[objection_id]
            status = objection.get("status")
            if status in {"unopened", "active", "handled", "watch"}:
                target["status"] = status
            try:
                target["severity"] = clamp(int(objection.get("severity", target["severity"])))
            except (TypeError, ValueError):
                pass
            if objection.get("description"):
                target["latest_signal"] = str(objection["description"])[:220]

    def _session_snapshot(self) -> dict:
        return {
            "stage": self.current_stage,
            "stage_label": self._stage_label(),
            "stages": CONVERSATION_STAGES,
            "deal_health": self.deal_health,
            "objection_stack": self.objection_stack,
            "battle_replay": self.battle_replay,
            "turn_evaluations": self.turn_evaluations,
            "latest_strategy": self.latest_strategy,
            "latest_evaluation_status": self.latest_evaluation_status,
            "difficulty": self.difficulty,
            "difficulty_label": DIFFICULTY_SETTINGS[self.difficulty]["label"],
            "meeting_objective": self.meeting_objective,
        }

    def _looks_incomplete_buyer_message(self, text: str, opening: bool = False) -> bool:
        """Detect clipped or invalid buyer utterances before persisting them."""
        normalized = " ".join((text or "").split())
        if not normalized:
            return True
        min_length = 105 if opening else 55
        if len(normalized) < min_length:
            return True
        if normalized[-1] not in ".?!\"'”’":
            return True
        if opening and "?" not in normalized:
            return True
        return False

    def _fallback_opening_message(self) -> str:
        """Return a persona-aware opening when provider output is incomplete."""
        title = self.persona["title"]
        company_type = self.persona["company_type"]
        name = self.persona["name"]
        company_lower = company_type.lower()
        title_lower = title.lower()

        if "federal" in company_lower or "procurement" in title_lower:
            pressure = (
                "what is the smallest compliant pilot you can support, what authorization or security evidence already exists, "
                "and where exactly will customer data be processed and retained?"
            )
        elif "security" in title_lower or "financial" in company_lower:
            pressure = (
                "what controls, audit evidence, and vendor-risk commitments can you show before we put production data anywhere near this?"
            )
        elif "hospital" in company_lower or "health" in company_lower:
            pressure = (
                "how do you prove clinical workflow safety, data handling, and adoption without creating liability for our operators?"
            )
        else:
            pressure = (
                "what measurable problem are you solving, what implementation burden should my team expect, and what evidence proves this is worth prioritizing now?"
            )

        return (
            f"Good morning — I’m {name}, {title}. Before we get excited about the product, I want to pressure-test the buying path: {pressure}"
        )

    def _fallback_follow_up(self) -> str:
        """Return a stage-aware follow-up when provider output is incomplete."""
        stage_prompts = {
            "discovery": "I need a sharper business case: who owns this pain, what happens if they do nothing, and why is this urgent now?",
            "technical_validation": "I need specifics on architecture, integration effort, failure modes, and what evidence shows this already works outside a friendly pilot.",
            "security_review": "I need the actual control surface: data boundary, subprocessors, access model, retention policy, and the evidence your team can send this week.",
            "procurement": "I need to understand the approval path: legal vehicle, security review owner, timeline, blockers, and who has authority to say yes.",
            "pricing_negotiation": "I need to see why this is budget-worthy now: ROI owner, comparable spend, expansion logic, and the risk if we delay.",
            "next_step_close": "I am willing to keep going only if we can agree on a concrete next step, owner, date, and evidence package.",
        }
        return stage_prompts.get(self.current_stage, stage_prompts["discovery"])

    def _repair_buyer_message(self, candidate: str, *, opening: bool = False) -> str:
        """Repair incomplete buyer copy once before using a local fallback."""
        if not self._looks_incomplete_buyer_message(candidate, opening=opening):
            return candidate.strip()

        repair_prompt = f"""
The previous buyer utterance was incomplete or too thin:
{candidate}

Rewrite it as {self.persona['name']}, {self.persona['title']}.
Requirements:
- Stay in character.
- 2-3 concise sentences.
- End with a concrete enterprise-buyer question.
- Do not reveal hidden internal concerns verbatim.
- No markdown.

Product context:
{self.product_context}

Meeting objective:
{self.meeting_objective}
"""

        try:
            repaired = self.llm.chat(
                messages=[
                    {"role": "system", "content": self.persona["system_prompt"]},
                    {"role": "user", "content": repair_prompt},
                ],
                temperature=0.38,
                max_tokens=260,
            ).strip()
            if not self._looks_incomplete_buyer_message(repaired, opening=opening):
                return repaired
        except Exception:
            pass

        if opening:
            return self._fallback_opening_message()
        return self._fallback_follow_up()

    def get_opening_message(self) -> dict:
        """Create the opening buyer turn and initial session snapshot."""
        self.logger.start_step(
            title="Simulation Initialization",
            description=f"Setting up buyer persona: {self.persona['name']}, {self.persona['title']} at {self.persona['company_type']}",
            step_type="processing",
            input_data=f"Product context: {self.product_context[:200]}",
        )
        self.logger.end_step(output_data=f"Persona loaded. Priorities: {', '.join(self.persona['priorities'][:3])}")

        self.logger.start_step(
            title="Opening Buyer Question",
            description="The buyer persona generates a realistic first question based on the deal room context.",
            step_type="generation",
            input_data=f"Persona: {self.persona['name']} ({self.persona['title']})",
        )

        difficulty_behavior = DIFFICULTY_SETTINGS[self.difficulty]["behavior"]
        system_msg = self.persona["system_prompt"] + f"""

Product being discussed:
{self.product_context}

Meeting objective:
{self.meeting_objective}

Difficulty profile:
{difficulty_behavior}

Buyer hidden concern:
{self.persona.get('hidden_objection', '')}

Generate your opening message for this meeting. Introduce yourself briefly and ask your first probing question.
Keep it to 2-3 sentences. This is the start of the meeting."""

        response = self.llm.chat(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": "Begin the meeting. Introduce yourself briefly and ask your first question."},
            ],
            temperature=0.75,
            max_tokens=320,
        )
        response = self._repair_buyer_message(response, opening=True)

        self.conversation_history.append({"role": "buyer", "content": response})
        self.turn_count = 1

        self.logger.end_step(output_data=response[:220])
        self.reasoning_log = self.logger.get_all_steps()

        return {
            "role": "buyer",
            "persona_name": self.persona["name"],
            "persona_title": self.persona["title"],
            "content": response,
            "turn": self.turn_count,
            "reasoning_steps": self.reasoning_log,
            **self._session_snapshot(),
        }

    def _build_conversation_messages(self, founder_message: str) -> list[dict]:
        difficulty_behavior = DIFFICULTY_SETTINGS[self.difficulty]["behavior"]
        stage_summary = json.dumps(CONVERSATION_STAGES, indent=2)
        health_summary = json.dumps(self.deal_health, indent=2)
        objection_summary = json.dumps(self.objection_stack, indent=2)

        system_content = self.persona["system_prompt"] + f"""

You are running a realistic enterprise sales simulation for a founder.

Product being discussed:
{self.product_context}

Meeting objective:
{self.meeting_objective}

Difficulty profile:
{difficulty_behavior}

Current deal stage:
{self.current_stage} — {self._stage_label()}

Current deal health:
{health_summary}

Objection stack:
{objection_summary}

Available stages:
{stage_summary}

Hidden buyer concern:
{self.persona.get('hidden_objection', '')}

Rules:
- Stay in character as {self.persona['name']}.
- Be tough, specific, and commercially realistic.
- Reward clear enterprise-grade answers with slightly more trust or urgency.
- Penalize vague answers, unsupported claims, and attempts to dodge procurement/security reality.
- Keep your buyer response to 2-4 sentences.
- If turn 7 or later, begin moving toward next-step close or a clear no.
- Do not reveal the hidden concern verbatim to the founder.
- Return only valid JSON. No markdown."""

        messages = [{"role": "system", "content": system_content}]

        for msg in self.conversation_history:
            if msg["role"] == "buyer":
                messages.append({"role": "assistant", "content": msg["content"]})
            else:
                messages.append({"role": "user", "content": msg["content"]})

        messages.append(
            {
                "role": "user",
                "content": f"""Founder just said:
{founder_message}

Return JSON with this exact shape:
{{
  "internal_strategy": "1-2 sentence private analysis of what the founder did and what the buyer will test next.",
  "buyer_response": "The buyer's next spoken response.",
  "stage": "one of: discovery, technical_validation, security_review, procurement, pricing_negotiation, next_step_close",
  "stage_reason": "Why the conversation is now in this stage.",
  "deal_health_delta": {{
    "buyer_trust": -15 to 15,
    "compliance_risk": -15 to 15,
    "budget_confidence": -15 to 15,
    "urgency": -15 to 15,
    "procurement_friction": -15 to 15
  }},
  "turn_evaluation": {{
    "score": 1 to 10,
    "label": "Poor/Fair/Good/Strong/Excellent",
    "what_worked": "Most useful part of the founder answer.",
    "missed_moment": "What the founder failed to address.",
    "evidence_quote": "Short quote or paraphrase from the founder answer.",
    "better_response": "A sharper founder answer in 1-2 sentences."
  }},
  "objections_detected": [
    {{
      "id": "security/data_residency/integration/budget/procurement/champion/vendor_viability",
      "status": "active/handled/watch/unopened",
      "severity": 0 to 100,
      "description": "Short current signal"
    }}
  ],
  "next_best_move": "What the founder should do next."
}}""",
            }
        )

        return messages

    def respond_to_founder(self, founder_message: str) -> dict:
        """Evaluate the founder turn and generate the next buyer response."""
        self.turn_count += 1

        self.logger.start_step(
            title=f"Founder Answer Evaluation (Turn {self.turn_count})",
            description="Scoring the founder response against enterprise buying criteria and updating deal state.",
            step_type="decision",
            input_data=founder_message[:320],
        )

        self.conversation_history.append({"role": "founder", "content": founder_message})

        response = self.llm.chat(
            messages=self._build_conversation_messages(founder_message),
            temperature=0.68,
            max_tokens=1300,
        )

        parsed: dict[str, Any] = {}
        buyer_response = response.strip()
        analysis = ""
        evaluation = {
            "score": None,
            "label": "Unscored",
            "what_worked": "The model returned a buyer response but did not return a complete scorecard.",
            "missed_moment": "Review the transcript manually.",
            "evidence_quote": founder_message[:160],
            "better_response": "Re-run the turn if a complete scorecard is required.",
        }
        next_best_move = ""

        try:
            parsed = clean_json_response(response)
            buyer_response = str(parsed.get("buyer_response", buyer_response)).strip()
            analysis = str(parsed.get("internal_strategy", "")).strip()
            next_stage = str(parsed.get("stage", self.current_stage)).strip()
            if next_stage in STAGE_IDS:
                self.current_stage = next_stage

            if isinstance(parsed.get("deal_health_delta"), dict):
                self._apply_health_delta(parsed["deal_health_delta"])

            if isinstance(parsed.get("turn_evaluation"), dict):
                evaluation = parsed["turn_evaluation"]

            if isinstance(parsed.get("objections_detected"), list):
                self._apply_objection_updates(parsed["objections_detected"])

            next_best_move = str(parsed.get("next_best_move", "")).strip()
            self.latest_evaluation_status = "scored"
        except Exception as e:
            salvaged_buyer_response = extract_json_string_field(response, "buyer_response")
            salvaged_strategy = extract_json_string_field(response, "internal_strategy")
            salvaged_stage = extract_json_string_field(response, "stage")
            if salvaged_buyer_response:
                buyer_response = salvaged_buyer_response
                analysis = salvaged_strategy
                if salvaged_stage in STAGE_IDS:
                    self.current_stage = salvaged_stage
                self.latest_evaluation_status = "spoken_response_recovered"
            else:
                buyer_response = self._fallback_follow_up()
                self.latest_evaluation_status = f"scorecard_unparsed_safe_fallback: {str(e)[:120]}"

        self.latest_strategy = analysis
        buyer_response = self._repair_buyer_message(buyer_response, opening=False)

        replay_item = {
            "turn": self.turn_count,
            "stage": self.current_stage,
            "stage_label": self._stage_label(),
            "founder_message": founder_message[:420],
            "buyer_response": buyer_response[:420],
            "score": evaluation.get("score"),
            "label": evaluation.get("label", "Unscored"),
            "what_worked": evaluation.get("what_worked", ""),
            "missed_moment": evaluation.get("missed_moment", ""),
            "better_response": evaluation.get("better_response", ""),
            "next_best_move": next_best_move,
            "internal_strategy": analysis,
        }
        self.turn_evaluations.append(evaluation)
        self.battle_replay.append(replay_item)

        self.logger.end_step(
            output_data=f"Stage: {self._stage_label()} | Score: {evaluation.get('score', 'N/A')} | {evaluation.get('label', 'Unscored')}"
        )

        self.logger.start_step(
            title=f"Buyer Response Generation (Turn {self.turn_count})",
            description="Generating the buyer's next objection or next-step pressure based on updated state.",
            step_type="generation",
        )

        self.conversation_history.append({"role": "buyer", "content": buyer_response})

        if self.turn_count >= 8 or self.current_stage == "next_step_close":
            self.is_complete = True

        self.logger.end_step(output_data=buyer_response[:220])
        self.reasoning_log = self.logger.get_all_steps()

        return {
            "role": "buyer",
            "persona_name": self.persona["name"],
            "content": buyer_response,
            "turn": self.turn_count,
            "is_complete": self.is_complete,
            "internal_strategy": analysis,
            "turn_evaluation": evaluation,
            "reasoning_steps": self.reasoning_log,
            **self._session_snapshot(),
        }

    def get_conversation_transcript(self) -> list[dict]:
        """Return the persisted conversation turns."""
        return self.conversation_history

    def to_dict(self) -> dict:
        """Serialize the current session state for API responses."""
        return {
            "persona_id": self.persona_id,
            "persona_name": self.persona["name"],
            "persona_title": self.persona["title"],
            "company_type": self.persona["company_type"],
            "persona": {
                "name": self.persona["name"],
                "title": self.persona["title"],
                "company_type": self.persona["company_type"],
                "personality": self.persona["personality"],
                "priorities": self.persona["priorities"],
                "deal_stage": self.persona.get("deal_stage", ""),
                "risk_tolerance": self.persona.get("risk_tolerance", ""),
                "procurement_power": self.persona.get("procurement_power", ""),
                "compliance_sensitivity": self.persona.get("compliance_sensitivity", ""),
                "budget_authority": self.persona.get("budget_authority", ""),
                "hidden_objection": self.persona.get("hidden_objection", ""),
                "success_condition": self.persona.get("success_condition", ""),
            },
            "product_context": self.product_context,
            "conversation": self.conversation_history,
            "turn_count": self.turn_count,
            "is_complete": self.is_complete,
            **self._session_snapshot(),
        }
