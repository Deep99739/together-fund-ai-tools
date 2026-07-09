"""
Expert-network routing pipeline for The Zone.

Converts a founder support request into structured intent, ranked expert
candidates, near-miss calibration, coverage gaps, and outreach-ready dispatch
copy.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# Shared provider and trace utilities live outside the tool folders.
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))

from llm_config import get_llm
from reasoning_logger import ReasoningLogger


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "before", "by", "for", "from", "how",
    "i", "in", "into", "is", "it", "need", "of", "on", "or", "our", "the",
    "their", "this", "to", "we", "with", "without", "your",
}

ROLE_KEYWORDS: dict[str, list[str]] = {
    "enterprise_gtm": [
        "enterprise sales", "fortune 500", "sales", "gtm", "outbound", "pipeline",
        "pricing", "procurement", "pilot", "buyer", "sales cycle", "us market",
    ],
    "security_compliance": [
        "soc2", "iso", "security", "compliance", "ciso", "vendor risk",
        "penetration", "data residency", "risk assessment", "infosec",
    ],
    "technical_architecture": [
        "architecture", "agentic", "multi-agent", "llm", "inference", "vector",
        "mlops", "model", "platform", "distributed", "scale", "latency",
    ],
    "legal_structuring": [
        "delaware", "entity", "flip", "esop", "safe", "ip", "transfer pricing",
        "c-corp", "incorporation", "legal", "cap table",
    ],
    "finance_ops": [
        "finance", "unit economics", "cfo", "forecast", "audit", "pricing",
        "burn", "runway", "series a", "fundraising",
    ],
    "cloud_infra": [
        "cloud", "gcp", "aws", "azure", "gpu", "tpu", "credits", "kubernetes",
        "serving", "cost optimization", "inference cost",
    ],
    "product_plg": [
        "plg", "product-led", "freemium", "onboarding", "activation", "retention",
        "product", "pmf", "smb", "conversion",
    ],
    "healthcare_regulatory": [
        "hipaa", "ehr", "clinical", "fda", "patient", "healthcare", "medical",
        "hospital", "pharma",
    ],
    "government_procurement": [
        "fedramp", "government", "federal", "defense", "itar", "public sector",
    ],
    "people_org": [
        "hiring", "people", "talent", "compensation", "culture", "remote team",
        "org design", "performance",
    ],
    "design_research": [
        "design", "ux", "dashboard", "research", "visualization", "accessibility",
    ],
    "partnerships": [
        "partnership", "aws marketplace", "cloud marketplace", "channel",
        "ecosystem", "co-sell",
    ],
}

ROLE_LABELS: dict[str, str] = {
    "enterprise_gtm": "Enterprise GTM",
    "security_compliance": "Security / compliance",
    "technical_architecture": "Technical architecture",
    "legal_structuring": "Legal structuring",
    "finance_ops": "Finance / operations",
    "cloud_infra": "Cloud infrastructure",
    "product_plg": "Product / PLG",
    "healthcare_regulatory": "Healthcare regulatory",
    "government_procurement": "Government procurement",
    "people_org": "People / org design",
    "design_research": "Design / research",
    "partnerships": "Partnerships",
}

STAGE_KEYWORDS: dict[str, list[str]] = {
    "idea": ["idea", "solo founder", "co-founder", "cofounder", "prototype"],
    "pre-seed": ["pre-seed", "mvp", "first customers", "first pilot", "pilot"],
    "seed": ["seed", "series a", "first enterprise", "pmf", "product-market"],
    "series-a": ["series a", "scale", "vp sales", "repeatable", "multi-region"],
    "growth": ["series b", "growth", "ipo", "pre-ipo", "global expansion"],
}

URGENCY_KEYWORDS = {
    "high": ["urgent", "blocked", "this week", "next week", "before", "running out", "lost", "security review", "pilot"],
    "medium": ["need help", "trying", "planning", "transitioning", "preparing"],
}


def should_use_llm() -> bool:
    """Gate provider calls for local smoke tests and offline review."""
    return os.getenv("ZONE_ROUTER_USE_LLM", "1").strip().lower() not in {"0", "false", "no", "off"}


def load_expert_profiles() -> list[dict]:
    """Load expert profiles from JSON and enrich them with computed routing metadata."""
    profiles_path = Path(__file__).parent / "expert_profiles.json"
    with open(profiles_path, "r") as f:
        profiles = json.load(f)

    for profile in profiles:
        profile["computed_roles"] = classify_expert_roles(profile)
        profile["stage_fit"] = infer_expert_stage_fit(profile)
        profile["search_text"] = build_expert_search_text(profile)

    return profiles


def network_stats(experts: list[dict] | None = None) -> dict:
    """Return lightweight network metadata for health checks and UI badges."""
    experts = experts or load_expert_profiles()
    roles = Counter(role for expert in experts for role in expert.get("computed_roles", []))
    availability = Counter(expert.get("availability", "unknown") for expert in experts)
    locations = Counter("India" if "India" in expert.get("location", "") else "US" if any(us in expert.get("location", "") for us in ["CA", "NY", "NJ", "DC", "MA", "WA"]) else "Global" for expert in experts)

    return {
        "profiles_loaded": len(experts),
        "demo_slice_note": "Synthetic demo slice of The Zone; production can point this at the live expert CRM.",
        "roles_covered": len(roles),
        "top_roles": [{"role": ROLE_LABELS.get(role, role), "count": count} for role, count in roles.most_common(6)],
        "availability": dict(availability),
        "location_mix": dict(locations),
    }


def extract_json(text: str) -> dict:
    """Extract JSON object from an LLM response, tolerating markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1:
        cleaned = cleaned[start:end + 1]

    return json.loads(cleaned)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def tokenize(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9][a-z0-9+\-.]*", text.lower()) if len(word) > 2 and word not in STOP_WORDS}


def phrase_hits(text: str, phrases: list[str]) -> list[str]:
    normalized = normalize(text)
    return [phrase for phrase in phrases if phrase in normalized]


def build_expert_search_text(expert: dict) -> str:
    parts = [
        expert.get("name", ""),
        expert.get("title", ""),
        expert.get("location", ""),
        expert.get("bio", ""),
        expert.get("corridor_expertise", ""),
        " ".join(expert.get("domains", [])),
        " ".join(expert.get("expertise_tags", [])),
        " ".join(expert.get("past_advisory", [])),
    ]
    return normalize(" ".join(parts))


def classify_expert_roles(expert: dict) -> list[str]:
    text = build_expert_search_text(expert)
    roles = []
    for role, keywords in ROLE_KEYWORDS.items():
        if phrase_hits(text, keywords):
            roles.append(role)
    return roles or ["general_operator"]


def infer_expert_stage_fit(expert: dict) -> list[str]:
    text = build_expert_search_text(expert)
    stage_fit = []
    if any(word in text for word in ["co-founder", "solo founder", "mentor", "swarmspace", "seed"]):
        stage_fit.extend(["idea", "pre-seed", "seed"])
    if any(word in text for word in ["series a", "enterprise", "pilot", "vp", "scaled", "sales", "procurement"]):
        stage_fit.extend(["seed", "series-a"])
    if any(word in text for word in ["ipo", "billion", "$1b", "$500m", "fortune 500", "global"]):
        stage_fit.extend(["series-a", "growth"])
    return sorted(set(stage_fit)) or ["pre-seed", "seed"]


def deterministic_intent(query: str) -> dict:
    """Build a keyword-backed intent baseline for provider fallback paths."""
    text = normalize(query)
    roles = [role for role, keywords in ROLE_KEYWORDS.items() if phrase_hits(text, keywords)]
    stage = "seed"
    for candidate_stage, keywords in STAGE_KEYWORDS.items():
        if phrase_hits(text, keywords):
            stage = candidate_stage
            break

    urgency = "low"
    for level, keywords in URGENCY_KEYWORDS.items():
        if phrase_hits(text, keywords):
            urgency = level
            break

    corridor_relevance = "yes" if any(term in text for term in ["india", "indian", "delaware", "us market", "us enterprise", "fortune 500", "cross-border"]) else "no"
    domain_terms = [ROLE_LABELS.get(role, role).lower() for role in roles[:4]] or ["general operator support"]
    skills = []
    for role in roles:
        skills.extend(ROLE_KEYWORDS[role][:3])

    hidden_risks = []
    if "enterprise_gtm" in roles:
        hidden_risks.append("The issue may be buyer trust and procurement readiness, not only sales messaging.")
    if "security_compliance" in roles:
        hidden_risks.append("Security review can block the pilot if SOC2, data residency, and vendor-risk artifacts are not ready.")
    if "cloud_infra" in roles:
        hidden_risks.append("Compute burn may become a runway problem before product-market fit is proven.")
    if "legal_structuring" in roles:
        hidden_risks.append("Corporate structure decisions may affect fundraising, IP ownership, taxes, and employee incentives.")

    return {
        "primary_domains": domain_terms,
        "specific_skills": sorted(set(skills))[:8] or ["operator diagnosis", "startup guidance"],
        "context_summary": query[:260],
        "urgency": urgency,
        "corridor_relevance": corridor_relevance,
        "company_stage": stage,
        "inferred_need_type": ROLE_LABELS.get(roles[0], "General operator support") if roles else "General operator support",
        "hidden_risks": hidden_risks[:4],
        "desired_outcome": "Route the founder to the fastest useful expert conversation and prepare the context needed for that call.",
        "suggested_expert_roles": roles[:4] or ["general_operator"],
        "clarifying_question": "" if roles else "Which function is the blocker: sales, product, technical architecture, legal, finance, or hiring?",
        "confidence": 72 if roles else 44,
    }


def merge_intent(llm_intent: dict, fallback: dict) -> dict:
    """Normalize provider output and fill required routing fields."""
    merged = {**fallback, **{k: v for k, v in llm_intent.items() if v not in (None, "", [], {})}}
    for key in ["primary_domains", "specific_skills", "hidden_risks", "suggested_expert_roles"]:
        value = merged.get(key, [])
        if isinstance(value, str):
            merged[key] = [value]
    merged["urgency"] = str(merged.get("urgency", "medium")).lower()
    if merged["urgency"] not in {"high", "medium", "low"}:
        merged["urgency"] = fallback["urgency"]
    merged["corridor_relevance"] = "yes" if str(merged.get("corridor_relevance", "no")).lower() in {"yes", "true", "high"} else "no"
    merged["company_stage"] = str(merged.get("company_stage", fallback["company_stage"])).lower()
    merged["confidence"] = int(float(merged.get("confidence", fallback["confidence"])))
    return merged


def extract_query_intent(query: str, logger: ReasoningLogger) -> dict:
    """
    Extract routing intent from natural-language founder context.

    The result captures operating need, company stage, urgency, hidden risks,
    and the expert roles likely to unblock the request.
    """
    logger.start_step(
        title="Founder Need Extraction",
        description="Converting the raw founder request into a structured operating need, stage, urgency, and expert-role profile.",
        step_type="processing",
        input_data=query,
    )

    fallback = deterministic_intent(query)

    try:
        if not should_use_llm():
            raise RuntimeError("LLM disabled by ZONE_ROUTER_USE_LLM=0")
        llm = get_llm()
        response = llm.chat(
            messages=[
                {
                    "role": "system",
                    "content": """You are an operator-network triage agent for Together Fund's expert network, The Zone.
Extract the founder's real operating need. Be practical and specific.

Return valid JSON only with:
{
  "primary_domains": ["2-4 domain labels"],
  "specific_skills": ["4-8 precise skills needed"],
  "context_summary": "1-2 sentence summary of what the founder actually needs",
  "urgency": "high | medium | low",
  "corridor_relevance": "yes | no",
  "company_stage": "idea | pre-seed | seed | series-a | growth",
  "inferred_need_type": "short label",
  "hidden_risks": ["risks the founder may not have named"],
  "desired_outcome": "what a good expert conversation should produce",
  "suggested_expert_roles": ["enterprise_gtm | security_compliance | technical_architecture | legal_structuring | finance_ops | cloud_infra | product_plg | healthcare_regulatory | government_procurement | people_org | design_research | partnerships"],
  "clarifying_question": "only if the query is too ambiguous; otherwise empty string",
  "confidence": 0-100
}""",
                },
                {"role": "user", "content": f"Founder request:\n{query}"},
            ],
            temperature=0.2,
            max_tokens=900,
        )
        intent = merge_intent(extract_json(response), fallback)
    except Exception as exc:
        intent = fallback
        intent["llm_fallback_used"] = True
        intent["fallback_reason"] = str(exc)[:180]

    logger.end_step(output_data=json.dumps(intent, indent=2))
    return intent


def score_phrase_overlap(query_items: list[str], expert_items: list[str], max_score: float, partial_weight: float = 0.45) -> tuple[float, list[str]]:
    """Score phrase and token overlap with inspectable match evidence."""
    if not query_items:
        return 0.0, []

    expert_text = normalize(" ".join(expert_items))
    matches: list[str] = []
    score = 0.0
    per_item = max_score / max(len(query_items), 1)

    for item in query_items:
        normalized_item = normalize(str(item))
        item_tokens = tokenize(normalized_item)
        if normalized_item and normalized_item in expert_text:
            score += per_item
            matches.append(normalized_item)
            continue

        expert_tokens = tokenize(expert_text)
        overlap = item_tokens & expert_tokens
        if item_tokens and len(overlap) / max(len(item_tokens), 1) >= partial_weight:
            score += per_item * min(0.75, len(overlap) / max(len(item_tokens), 1))
            matches.append(f"{normalized_item} ↔ {'/'.join(sorted(overlap)[:3])}")

    return min(score, max_score), matches[:8]


def infer_query_words(intent: dict) -> set[str]:
    words = tokenize(" ".join([
        " ".join(intent.get("primary_domains", [])),
        " ".join(intent.get("specific_skills", [])),
        intent.get("context_summary", ""),
        intent.get("inferred_need_type", ""),
    ]))
    return words - STOP_WORDS


def score_expert(intent: dict, expert: dict) -> dict:
    query_roles = [str(role).lower() for role in intent.get("suggested_expert_roles", [])]
    expert_roles = expert.get("computed_roles", [])
    query_domains = [str(item).lower() for item in intent.get("primary_domains", [])]
    query_skills = [str(item).lower() for item in intent.get("specific_skills", [])]
    query_words = infer_query_words(intent)

    domain_score, domain_matches = score_phrase_overlap(query_domains, expert.get("domains", []), 24)
    skill_score, skill_matches = score_phrase_overlap(query_skills, expert.get("expertise_tags", []), 26)

    role_overlap = sorted(set(query_roles) & set(expert_roles))
    role_score = min(len(role_overlap) * 8, 16)

    search_text = expert.get("search_text", "")
    bio_terms = sorted([word for word in query_words if len(word) > 3 and word in search_text])[:8]
    bio_score = min(len(bio_terms) * 2, 14)

    advisory_text = normalize(" ".join(expert.get("past_advisory", [])))
    advisory_terms = sorted([word for word in query_words if len(word) > 3 and word in advisory_text])[:6]
    advisory_score = min(len(advisory_terms) * 2, 10)

    corridor_text = normalize(expert.get("corridor_expertise", ""))
    corridor_score = 0
    if intent.get("corridor_relevance") == "yes":
        corridor_score = 10 if any(term in corridor_text for term in ["india", "us", "corridor", "global"]) else 2
    elif any(term in corridor_text for term in ["us", "enterprise", "global"]):
        corridor_score = 4

    stage = intent.get("company_stage", "seed")
    stage_score = 10 if stage in expert.get("stage_fit", []) else 5 if stage in {"seed", "series-a"} else 3

    availability_scores = {"high": 8, "medium": 5, "low": 2}
    availability_score = availability_scores.get(expert.get("availability", "medium"), 5)

    urgency_score = 5
    if intent.get("urgency") == "high" and expert.get("availability") == "low":
        urgency_score = 1
    elif intent.get("urgency") == "high" and expert.get("availability") == "high":
        urgency_score = 7

    conflict_penalty = 0
    if "investment" in normalize(expert.get("title", "")) and any(role in query_roles for role in ["legal_structuring", "finance_ops"]):
        conflict_penalty = 4

    raw_score = (
        domain_score + skill_score + role_score + bio_score + advisory_score +
        corridor_score + stage_score + availability_score + urgency_score - conflict_penalty
    )
    match_score = round(max(0, min(100, raw_score)), 1)

    match_reasons = []
    if role_overlap:
        match_reasons.append(f"Role fit: {', '.join(ROLE_LABELS.get(role, role) for role in role_overlap[:2])}")
    if domain_matches:
        match_reasons.append(f"Domain evidence: {', '.join(domain_matches[:2])}")
    if skill_matches:
        match_reasons.append(f"Skill evidence: {', '.join(skill_matches[:2])}")
    if advisory_terms:
        match_reasons.append("Past advisory context overlaps with the request")
    if corridor_score >= 8:
        match_reasons.append(f"Corridor fit: {expert.get('corridor_expertise', '')}")
    if expert.get("availability") == "high":
        match_reasons.append("High availability for fast routing")

    fit_label = "Primary route" if match_score >= 72 else "Strong fit" if match_score >= 58 else "Useful specialist" if match_score >= 44 else "Weak fit"
    confidence = round(min(96, max(35, match_score + len(match_reasons) * 2)))
    role_key = role_overlap[0] if role_overlap else expert_roles[0] if expert_roles else ""
    routing_role = ROLE_LABELS.get(role_key, "Operator")

    return {
        **expert,
        "match_score": match_score,
        "confidence": confidence,
        "fit_label": fit_label,
        "routing_role": routing_role,
        "match_reasons": match_reasons[:6] or ["Broad operator relevance; no precise evidence match."],
        "score_breakdown": {
            "domain_match": round(domain_score, 1),
            "skill_match": round(skill_score, 1),
            "role_fit": round(role_score, 1),
            "bio_relevance": round(bio_score, 1),
            "advisory_relevance": round(advisory_score, 1),
            "corridor_fit": round(corridor_score, 1),
            "stage_fit": round(stage_score, 1),
            "availability": round(availability_score, 1),
            "urgency_fit": round(urgency_score, 1),
            "conflict_penalty": round(conflict_penalty, 1),
        },
        "evidence": {
            "domain_matches": domain_matches,
            "skill_matches": skill_matches,
            "bio_terms": bio_terms,
            "advisory_terms": advisory_terms,
            "roles": [ROLE_LABELS.get(role, role) for role in expert_roles],
            "stage_fit": expert.get("stage_fit", []),
        },
    }


def compute_expert_scores(intent: dict, experts: list[dict], logger: ReasoningLogger) -> list[dict]:
    """
    Rank the expert pool with auditable, multi-factor feature scores.

    The scoring path is deterministic and can be replaced with embeddings
    without changing the downstream route contract.
    """
    logger.start_step(
        title="Network Retrieval and Scoring",
        description=f"Scoring {len(experts)} profiles across role fit, skills, domain evidence, past advisory context, stage fit, corridor relevance, urgency, and availability.",
        step_type="retrieval",
        input_data=f"Roles: {intent.get('suggested_expert_roles', [])}; Skills: {intent.get('specific_skills', [])}",
    )

    scored_experts = [score_expert(intent, expert) for expert in experts]
    scored_experts.sort(key=lambda x: x["match_score"], reverse=True)

    top_summary = "\n".join([
        f"{i + 1}. {expert['name']} — {expert['match_score']}/100 ({expert['routing_role']}); {expert['match_reasons'][0]}"
        for i, expert in enumerate(scored_experts[:6])
    ])
    logger.end_step(output_data=f"Candidate pool ranked:\n{top_summary}")
    return scored_experts


def build_near_misses(scored_experts: list[dict], selected_ids: set[str]) -> list[dict]:
    """Return strong non-selected candidates with rejection rationale."""
    near_misses = []
    for expert in scored_experts:
        if expert["id"] in selected_ids:
            continue
        missing = []
        breakdown = expert["score_breakdown"]
        if breakdown["availability"] <= 2:
            missing.append("availability is low")
        if breakdown["skill_match"] < 8:
            missing.append("specific skill evidence is weaker than the selected route")
        if breakdown["role_fit"] == 0:
            missing.append("role is adjacent rather than central")
        if not missing:
            missing.append("strong specialist, but the selected experts cover the immediate route better")
        near_misses.append({
            "name": expert["name"],
            "title": expert["title"],
            "match_score": expert["match_score"],
            "why_not_selected": "; ".join(missing[:2]),
            "use_if": f"Use if the primary route needs deeper {expert['routing_role'].lower()} support.",
        })
        if len(near_misses) >= 3:
            break
    return near_misses


def build_coverage_gaps(intent: dict, scored_experts: list[dict]) -> list[dict]:
    """
    Identify requested expertise where the current network slice is weak.

    These gaps become recruiting or metadata-enrichment signals in a live CRM.
    """
    gaps = []
    requested_roles = [role for role in intent.get("suggested_expert_roles", []) if role != "general_operator"]

    for role in requested_roles:
        candidates = [expert for expert in scored_experts if role in expert.get("computed_roles", [])]
        best = candidates[0] if candidates else None
        if not best:
            gaps.append({
                "role": ROLE_LABELS.get(role, role),
                "severity": "high",
                "reason": "No modeled expert has this role coverage.",
                "recruiting_signal": f"Recruit one more operator with strong {ROLE_LABELS.get(role, role).lower()} experience.",
            })
        elif best["match_score"] < 48:
            gaps.append({
                "role": ROLE_LABELS.get(role, role),
                "severity": "medium",
                "reason": f"Best available match is {best['name']} at {best['match_score']}/100, which is useful but not decisive.",
                "recruiting_signal": f"Add a deeper {ROLE_LABELS.get(role, role).lower()} specialist or strengthen profile metadata.",
            })

    if intent.get("confidence", 100) < 55:
        gaps.append({
            "role": "Request clarity",
            "severity": "medium",
            "reason": "The founder request is broad enough that premature routing may waste expert time.",
            "recruiting_signal": "Capture one clarifying answer before dispatching.",
        })

    return gaps[:4]


def safe_sentence(text: str, max_len: int = 260) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned if len(cleaned) <= max_len else cleaned[:max_len].rstrip() + "…"


def humanize_label(value: str | None, fallback: str = "operator support") -> str:
    """Convert route identifiers into human-readable labels."""
    if not value:
        return fallback
    label = ROLE_LABELS.get(str(value), str(value))
    label = label.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", label).strip()


def first_name(full_name: str) -> str:
    return full_name.split()[0] if full_name else "there"


def strongest_advisory_line(expert: dict) -> str:
    advisory = expert.get("past_advisory", [])
    if advisory:
        return safe_sentence(advisory[0], 220)
    return safe_sentence(expert.get("bio", ""), 220)


def route_objective(role: str, intent: dict, step: int) -> str:
    role_lower = role.lower()
    outcome = safe_sentence(intent.get("desired_outcome", "leave with a concrete operating artifact"), 180)

    if "security" in role_lower or "compliance" in role_lower:
        return "Separate the trust blocker from the product blocker, identify the exact security artifact needed, and define what the company can credibly promise now."
    if "enterprise" in role_lower or "gtm" in role_lower:
        return "Map the buyer process, decide whether this is sales motion or readiness work, and define the next enterprise-facing artifact."
    if "cloud" in role_lower or "infrastructure" in role_lower:
        return "Find the main cost or reliability driver, pressure-test the current serving architecture, and choose the fastest remediation path."
    if "legal" in role_lower:
        return "Clarify entity, IP, ESOP, and financing implications before the company makes an irreversible structuring move."
    if "healthcare" in role_lower:
        return "Turn the hospital request into a concrete compliance, integration, safety, and procurement checklist."
    if "product" in role_lower:
        return "Translate the founder's blocker into product motion, activation, buyer proof, and the next experiment."
    if step == 1:
        return f"Diagnose the real operating blocker and define the first artifact needed to {outcome.lower()}."
    if step == 2:
        return "Convert the first-call diagnosis into a tactical sequence, backup path, and owner for the next week."
    return "Pressure-test the specialist risk before the founder spends more time on the wrong motion."


def route_label(role: str, step: int) -> str:
    if step == 1:
        return f"First call: {role}"
    if step == 2:
        return f"Backup lane: {role}"
    return f"Specialist check: {role}"


def fallback_rationale(intent: dict, top_experts: list[dict]) -> dict:
    recommendations = []
    for expert in top_experts[:3]:
        role = humanize_label(expert.get("routing_role"), "operator")
        advisory_line = strongest_advisory_line(expert)
        recommendations.append({
            "name": expert["name"],
            "rationale": (
                f"{expert['name']} is the strongest {role.lower()} fit because "
                f"{'; '.join(expert['match_reasons'][:2]).lower()}. A useful precedent: {advisory_line}."
            ),
            "conversation_starter": route_objective(role, intent, 1),
            "complementary_value": f"{role} judgment plus {expert.get('corridor_expertise', 'operator-network context')}.",
        })
    primary = top_experts[0]
    backup = top_experts[1] if len(top_experts) > 1 else None
    specialist = top_experts[2] if len(top_experts) > 2 else None
    return {
        "recommendations": recommendations,
        "routing_strategy": " ".join([
            f"Start with {primary['name']} because the first conversation needs {humanize_label(primary.get('routing_role')).lower()} judgment.",
            f"Keep {backup['name']} as the backup lane if the blocker moves toward {humanize_label(backup.get('routing_role')).lower()}." if backup else "",
            f"Bring in {specialist['name']} only if the first two calls expose a specialist {humanize_label(specialist.get('routing_role')).lower()} risk." if specialist else "",
        ]).strip(),
    }


def generate_routing_rationale(intent: dict, top_experts: list[dict], logger: ReasoningLogger) -> dict:
    """
    Build practical rationale for the dispatch plan.

    If provider output is unavailable, the fallback keeps the route usable and
    preserves the same response contract.
    """
    logger.start_step(
        title="Dispatch Rationale Generation",
        description="Turning the ranked candidates into a practical explanation, first-call strategy, and conversation starters.",
        step_type="generation",
        input_data=f"Selected route: {', '.join(e['name'] for e in top_experts[:3])}",
    )

    experts_context = json.dumps([
        {
            "name": e["name"],
            "title": e["title"],
            "location": e["location"],
            "bio": e["bio"],
            "domains": e["domains"],
            "past_advisory": e.get("past_advisory", []),
            "match_score": e["match_score"],
            "match_reasons": e["match_reasons"],
            "score_breakdown": e["score_breakdown"],
            "availability": e.get("availability", "unknown"),
            "corridor_expertise": e.get("corridor_expertise", ""),
            "routing_role": e.get("routing_role", ""),
        }
        for e in top_experts[:3]
    ], indent=2)

    try:
        if not should_use_llm():
            raise RuntimeError("LLM disabled by ZONE_ROUTER_USE_LLM=0")
        llm = get_llm()
        response = llm.chat(
            messages=[
                {
                    "role": "system",
                    "content": """You are the dispatch rationale engine for Together Fund's operator network, The Zone.
Generate concise, practical routing rationale. Do not sound like a generic recommendation engine.

Return valid JSON:
{
  "recommendations": [
    {
      "name": "expert name",
      "rationale": "2-3 sentences connecting this exact expert to the founder's need",
      "conversation_starter": "the first high-leverage question to ask",
      "complementary_value": "what this expert adds that the other route members do not"
    }
  ],
  "routing_strategy": "who to start with, who to add second, and why"
}""",
                },
                {
                    "role": "user",
                    "content": f"""Founder need:
{json.dumps(intent, indent=2)}

Selected experts:
{experts_context}""",
                },
            ],
            temperature=0.35,
            max_tokens=1500,
        )
        rationale = extract_json(response)
    except Exception:
        rationale = fallback_rationale(intent, top_experts)

    logger.end_step(output_data=json.dumps(rationale, indent=2)[:900])
    return rationale


def build_dispatch_plan(intent: dict, top_experts: list[dict], rationale: dict) -> dict:
    """Create the route plan consumed by the frontend."""
    primary = top_experts[0]
    backup = top_experts[1] if len(top_experts) > 1 else None
    specialist = top_experts[2] if len(top_experts) > 2 else None
    clarifying_question = intent.get("clarifying_question", "")

    recommended_sequence = [
        {
            "step": 1,
            "label": route_label(primary["routing_role"], 1),
            "expert": primary["name"],
            "role": primary["routing_role"],
            "objective": route_objective(primary["routing_role"], intent, 1),
            "timebox": "25 minutes",
        }
    ]
    if backup:
        recommended_sequence.append({
            "step": 2,
            "label": route_label(backup["routing_role"], 2),
            "expert": backup["name"],
            "role": backup["routing_role"],
            "objective": route_objective(backup["routing_role"], intent, 2),
            "timebox": "30 minutes",
        })
    if specialist:
        recommended_sequence.append({
            "step": 3,
            "label": route_label(specialist["routing_role"], 3),
            "expert": specialist["name"],
            "role": specialist["routing_role"],
            "objective": route_objective(specialist["routing_role"], intent, 3),
            "timebox": "20 minutes",
        })

    confidence = round(sum(e["confidence"] for e in top_experts[:3]) / max(len(top_experts[:3]), 1))
    if clarifying_question and confidence < 55:
        decision = "Ask one clarifying question before routing"
    else:
        decision = f"Start with {primary['name']}"

    return {
        "decision": decision,
        "primary_expert": primary["name"],
        "primary_role": primary["routing_role"],
        "confidence": confidence,
        "urgency": intent.get("urgency", "medium"),
        "stage": intent.get("company_stage", "seed"),
        "why_now": intent.get("desired_outcome", "Fast expert diagnosis is likely to unblock the next operating decision."),
        "sequence": recommended_sequence,
        "routing_strategy": rationale.get("routing_strategy", ""),
        "clarifying_question": clarifying_question,
    }


def build_intro_pack(query: str, intent: dict, top_experts: list[dict], rationale: dict) -> dict:
    """Generate intro copy, prep questions, and success criteria."""
    primary = top_experts[0]
    recommendation = next((rec for rec in rationale.get("recommendations", []) if rec.get("name") == primary["name"]), {})
    context_summary = safe_sentence(intent.get("context_summary", query), 360)
    hidden_risks = intent.get("hidden_risks", [])[:3]
    need_type = humanize_label(intent.get("inferred_need_type"), "operating blocker")
    primary_role = humanize_label(primary.get("routing_role"), "operator")
    advisory_line = strongest_advisory_line(primary)
    first_question = recommendation.get("conversation_starter") or route_objective(primary_role, intent, 1)

    prep_questions = [
        first_question,
        "What evidence would make this company look enterprise-ready within two weeks?",
        "What should the founder avoid doing before the next external conversation?",
    ]
    if hidden_risks:
        prep_questions.append(f"Which hidden risk is most likely to block progress: {hidden_risks[0]}")

    subject = f"Intro request: {need_type} for a {intent.get('company_stage', 'seed')} founder"
    email = (
        f"Hi {first_name(primary['name'])},\n\n"
        f"We are working with a founder who is blocked on {need_type.lower()}, and your {primary_role.lower()} experience feels like the right first call.\n\n"
        f"Context: {context_summary}\n\n"
        f"Why you: {primary['match_reasons'][0]}. You have handled adjacent work before — {advisory_line}. "
        f"Your {primary.get('corridor_expertise', 'operator context')} perspective should help us avoid sending them to the wrong specialist too early.\n\n"
        f"Could you do a focused 25-minute call to diagnose the blocker and name the artifact they should prepare next?\n\n"
        f"Suggested opening question: {first_question}\n\n"
        f"Thank you — this should be a tight, practical call rather than a broad advisory session."
    )

    return {
        "subject": subject,
        "intro_email": email,
        "context_to_send": [
            context_summary,
            f"Stage: {intent.get('company_stage', 'unknown')}; urgency: {intent.get('urgency', 'medium')}.",
            f"Desired outcome: {intent.get('desired_outcome', 'clear next step')}",
        ],
        "prep_questions": prep_questions[:5],
        "success_criteria": [
            "Founder leaves with a concrete operating artifact to prepare.",
            "Expert identifies the real blocker, not just the surface request.",
            "Together can decide whether a second specialist call is needed.",
        ],
    }


def serialize_expert(expert: dict, rank: int) -> dict:
    return {
        "rank": rank,
        "id": expert["id"],
        "name": expert["name"],
        "title": expert["title"],
        "location": expert["location"],
        "bio": expert["bio"],
        "domains": expert.get("domains", []),
        "expertise_tags": expert.get("expertise_tags", []),
        "past_advisory": expert.get("past_advisory", []),
        "match_score": expert["match_score"],
        "confidence": expert["confidence"],
        "fit_label": expert["fit_label"],
        "routing_role": expert["routing_role"],
        "match_reasons": expert["match_reasons"],
        "score_breakdown": expert["score_breakdown"],
        "evidence": expert["evidence"],
        "availability": expert.get("availability", "unknown"),
        "corridor_expertise": expert.get("corridor_expertise", ""),
    }


def route_query(query: str) -> dict:
    """
    Route a founder request and return an auditable dispatch plan.
    """
    logger = ReasoningLogger(task_name="The Zone Dispatch")

    experts = load_expert_profiles()
    stats = network_stats(experts)
    logger.start_step(
        title="Load Expert Network",
        description="Loading the expert network slice and computing role, availability, and location coverage.",
        step_type="retrieval",
    )
    logger.end_step(output_data=f"Loaded {stats['profiles_loaded']} profiles across {stats['roles_covered']} role categories. Availability mix: {stats['availability']}")

    intent = extract_query_intent(query, logger)
    scored_experts = compute_expert_scores(intent, experts, logger)

    top_experts = scored_experts[:3]
    selected_ids = {expert["id"] for expert in top_experts}
    near_misses = build_near_misses(scored_experts, selected_ids)
    coverage_gaps = build_coverage_gaps(intent, scored_experts)

    logger.start_step(
        title="Near-Miss Calibration",
        description="Checking strong but unselected candidates so reviewers can see why the route is not arbitrary.",
        step_type="decision",
    )
    logger.end_step(output_data=json.dumps(near_misses, indent=2))

    rationale = generate_routing_rationale(intent, top_experts, logger)

    dispatch_plan = build_dispatch_plan(intent, top_experts, rationale)
    intro_pack = build_intro_pack(query, intent, top_experts, rationale)

    logger.start_step(
        title="Compile Dispatch Brief",
        description="Assembling routing decision, expert sequence, near misses, intro copy, prep questions, and audit trail.",
        step_type="decision",
    )

    result = {
        "query": query,
        "intent": intent,
        "network_stats": stats,
        "dispatch_plan": dispatch_plan,
        "top_experts": [serialize_expert(expert, i + 1) for i, expert in enumerate(top_experts)],
        "candidate_pool": [serialize_expert(expert, i + 1) for i, expert in enumerate(scored_experts[:8])],
        "near_misses": near_misses,
        "coverage_gaps": coverage_gaps,
        "rationale": rationale,
        "intro_pack": intro_pack,
        "reasoning_log": logger.get_all_steps(),
    }

    logger.end_step(output_data=f"Dispatch ready. Decision: {dispatch_plan['decision']} | Confidence: {dispatch_plan['confidence']}% | Primary: {dispatch_plan['primary_expert']}")

    return result
