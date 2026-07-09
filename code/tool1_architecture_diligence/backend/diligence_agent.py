"""
Architecture diligence pipeline for AI-native startup documentation.

Combines structured extraction, wrapper-risk checks, technical-depth scoring,
and source-evidence calibration into a review-ready response.
"""

import json
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))

from llm_config import get_llm
from reasoning_logger import ReasoningLogger
from anti_patterns import WRAPPER_ANTI_PATTERNS, DEPTH_DIMENSIONS


import re

RISK_TAXONOMY = [
    {
        "id": "architecture_defensibility",
        "name": "Architecture defensibility",
        "framework": "Together 10x / Building for Keeps",
        "why_it_matters": "Reviewers need to know whether the company has a durable technical wedge or a weekend-replicable wrapper.",
        "positive_terms": ["custom model", "trained from scratch", "fine-tuned", "proprietary architecture", "multi-agent", "reinforcement", "custom transformer", "custom inference"],
        "negative_terms": ["openai api", "gpt-4", "gpt-4o", "claude api", "prompt template", "prompts are our moat", "wrapper", "api call"],
        "validation_question": "Which parts of the system would remain hard to replicate if model API prices dropped to zero?",
    },
    {
        "id": "data_moat",
        "name": "Data moat and learning loop",
        "framework": "NIST AI RMF — Map / Measure",
        "why_it_matters": "A defensible AI startup should improve with proprietary data, feedback loops, labeling, or deployment-specific telemetry.",
        "positive_terms": ["proprietary data", "customer telemetry", "labeled data", "active learning", "data flywheel", "expert annotations", "synthetic data", "federated"],
        "negative_terms": ["public data", "no proprietary data", "no training data", "doesn't retain", "temporarily stored", "deleted after"],
        "validation_question": "What unique data asset compounds as deployments increase, and how is consent/privacy handled?",
    },
    {
        "id": "evaluation_rigor",
        "name": "Evaluation rigor",
        "framework": "NIST AI RMF — Measure / Manage",
        "why_it_matters": "Claims are not technically reliable unless the team can measure quality, regressions, false positives, drift, and production performance.",
        "positive_terms": ["benchmark", "precision", "recall", "a/b testing", "shadow mode", "evaluation", "red team", "continuous evaluation", "test suite", "false positive"],
        "negative_terms": ["no benchmark", "no evaluation", "no a/b", "accuracy only", "manual review only"],
        "validation_question": "What benchmark or production metric would falsify the core technical claim?",
    },
    {
        "id": "genai_security",
        "name": "GenAI security and agency controls",
        "framework": "OWASP LLM Top 10 — Prompt Injection / Excessive Agency",
        "why_it_matters": "Agentic systems need controls for prompt injection, unsafe tool use, data leakage, and unchecked autonomy before enterprise deployment.",
        "positive_terms": ["guardrail", "policy", "validator", "sandbox", "human approval", "least privilege", "prompt injection", "data residency", "safety policy", "access control"],
        "negative_terms": ["autonomously", "unchecked", "no guardrails", "no validation", "full access", "execute arbitrary"],
        "validation_question": "What prevents the agent from taking an unsafe action when given malicious or ambiguous input?",
    },
    {
        "id": "supply_chain_dependency",
        "name": "Model and vendor dependency",
        "framework": "OWASP LLM Top 10 — Supply Chain / Unbounded Consumption",
        "why_it_matters": "Thin dependency on third-party models creates pricing, reliability, differentiation, and data-governance risk.",
        "positive_terms": ["on-premise", "air-gapped", "fallback", "self-hosted", "vllm", "quantized", "model weights", "custom batching", "multi-region"],
        "negative_terms": ["single-server", "railway", "vercel", "openai api", "anthropic", "third-party api", "no caching", "vendor lock"],
        "validation_question": "What breaks if the primary model provider raises prices, changes policy, or has a 24-hour outage?",
    },
    {
        "id": "production_readiness",
        "name": "Production scale and reliability",
        "framework": "Enterprise readiness",
        "why_it_matters": "A startup selling to enterprises needs credible latency, uptime, deployment, observability, and scalability plans.",
        "positive_terms": ["p99", "latency", "kubernetes", "queue", "caching", "load balancing", "observability", "multi-region", "batching", "feature store"],
        "negative_terms": ["single-server", "no caching", "not implemented", "prototype", "manual", "no monitoring"],
        "validation_question": "Where are the bottlenecks at 10x usage, and how would the team detect degradation before customers do?",
    },
]


def extract_json(text: str) -> dict:
    """Parse a JSON object from provider output."""
    text = text.strip()
    # Trim surrounding prose while preserving the JSON body.
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        text = text[start:end+1]
    return json.loads(text)


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    """Clamp a numeric score into a bounded range."""
    return max(low, min(high, value))


def normalize_text(text: str) -> str:
    """Normalize free text for phrase-level checks."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def negates_prompt_only_claim(normalized_text: str) -> bool:
    """Avoid counting negated prompt-engineering references as wrapper evidence."""
    negation_patterns = [
        r"can't be replicated with prompt engineering",
        r"cannot be replicated with prompt engineering",
        r"not just prompt engineering",
        r"not prompt engineering",
        r"beyond prompt engineering",
        r"not merely prompt",
    ]
    return any(re.search(pattern, normalized_text) for pattern in negation_patterns)


def sanitize_review_language(value: Any) -> Any:
    """
    Keep generated copy aligned with technical diligence language.

    Provider outputs occasionally drift into investment-memo phrasing; this
    pass normalizes those terms before data reaches the UI.
    """
    if isinstance(value, str):
        replacements = [
            (r"\binvestment opportunity\b", "technical diligence candidate"),
            (r"\bventure opportunity\b", "technical diligence candidate"),
            (r"\binvestment memo\b", "technical diligence brief"),
            (r"\binvestment committee\b", "technical review team"),
            (r"\binvestment pipeline\b", "technical diligence pipeline"),
            (r"\binvestment lens\b", "technical diligence lens"),
            (r"\binvestment review\b", "technical review"),
            (r"\binvestable\b", "technically credible"),
            (r"\bcandidate for investment\b", "candidate for a technical deep dive"),
            (r"\bfor investment\b", "for technical review"),
            (r"\bsignificant investment in\b", "significant technical work in"),
            (r"\binfrastructure investment\b", "infrastructure depth"),
            (r"\binvestment\b", "technical diligence"),
            (r"\bCTO-ready\b", "review-ready"),
            (r"\ba CTO or technical partner\b", "a technical reviewer"),
            (r"\bCTO/founding engineer\b", "technical owner"),
            (r"\bCTO\b", "technical reviewer"),
            (r"\bVC firm\b", "technical diligence team"),
            (r"\bVC\b", "review"),
            (r"\bIC\b", "technical review"),
            (r"\bfounder proof\b", "source evidence"),
            (r"\bdisprove\b", "validate"),
            (r"\bprove\b", "validate"),
            (r"\binterrogation\b", "validation"),
        ]
        sanitized = value
        for pattern, replacement in replacements:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        return sanitized

    if isinstance(value, list):
        return [sanitize_review_language(item) for item in value]

    if isinstance(value, dict):
        return {key: sanitize_review_language(item) for key, item in value.items()}

    return value


def extract_snippets(document_text: str, terms: list[str], max_items: int = 4, radius: int = 160) -> list[dict]:
    """
    Return source excerpts containing the requested evidence terms.

    Snippets let reviewers inspect the document basis for each risk signal
    instead of relying only on generated summaries.
    """
    snippets = []
    seen_ranges: list[tuple[int, int]] = []
    lowered = document_text.lower()

    for term in terms:
        if not term:
            continue
        match = re.search(re.escape(term.lower()), lowered)
        if not match:
            continue

        start = max(match.start() - radius, 0)
        end = min(match.end() + radius, len(document_text))

        # Suppress repeated excerpts from the same local context.
        if any(abs(start - existing_start) < 80 or abs(end - existing_end) < 80 for existing_start, existing_end in seen_ranges):
            continue

        snippet = document_text[start:end].strip()
        snippets.append({
            "term": term,
            "snippet": re.sub(r"\s+", " ", snippet),
        })
        seen_ranges.append((start, end))

        if len(snippets) >= max_items:
            break

    return snippets


def detect_direct_anti_patterns(document_text: str) -> list[dict]:
    """Detect high-signal wrapper patterns directly from source text."""
    normalized = normalize_text(document_text)
    detected = []

    doc_signals = {
        "thin_api_proxy": ["openai gpt", "gpt-4", "gpt-4o", "claude api", "sent to openai", "via api"],
        "generic_prompts": ["prompt template", "prompt templates", "prompts are our moat", "custom prompts"],
        "no_evaluation_framework": ["no benchmark", "no benchmarks", "no evaluation", "no a/b", "no testing framework"],
        "no_scale_architecture": ["single-server", "no caching", "railway", "vercel", "no load balancing"],
        "over_reliance_external": ["openai api", "anthropic claude", "third-party api", "data leaves our system"],
    }

    for pattern in WRAPPER_ANTI_PATTERNS:
        signals = doc_signals.get(pattern["id"], [])
        matches = [signal for signal in signals if signal in normalized]
        if pattern["id"] == "generic_prompts" and negates_prompt_only_claim(normalized):
            matches = [signal for signal in matches if signal == "prompts are our moat"]
        if matches:
            detected.append({
                **pattern,
                "evidence": f"Document contains direct signal(s): {', '.join(matches[:3])}",
                "source": "deterministic_document_scan",
            })

    return detected


def dedupe_patterns(patterns: list[dict]) -> list[dict]:
    """Collapse duplicate anti-patterns while preserving strongest evidence."""
    by_id = {}
    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    for pattern in patterns:
        existing = by_id.get(pattern["id"])
        if not existing:
            by_id[pattern["id"]] = pattern
            continue
        if severity_rank.get(pattern.get("severity", "low"), 1) >= severity_rank.get(existing.get("severity", "low"), 1):
            merged_evidence = existing.get("evidence", "")
            new_evidence = pattern.get("evidence", "")
            if new_evidence and new_evidence not in merged_evidence:
                pattern["evidence"] = f"{merged_evidence} | {new_evidence}" if merged_evidence else new_evidence
            by_id[pattern["id"]] = pattern
    return list(by_id.values())


def build_risk_register(document_text: str, components: dict, detected_patterns: list[dict]) -> list[dict]:
    """
    Build the technical risk register from source evidence and extracted components.

    The register uses deterministic scoring so the final posture is not solely
    dependent on model judgment.
    """
    register = []
    pattern_text = " ".join([f"{p.get('name', '')} {p.get('evidence', '')}" for p in detected_patterns]).lower()

    for risk in RISK_TAXONOMY:
        positive_evidence = extract_snippets(document_text, risk["positive_terms"], max_items=3)
        negative_evidence = extract_snippets(document_text, risk["negative_terms"], max_items=3)

        risk_score = 55 - (len(positive_evidence) * 12) + (len(negative_evidence) * 16)
        if any(term in pattern_text for term in risk["negative_terms"]):
            risk_score += 10

        # Fold structured component signals into the evidence score.
        if risk["id"] == "data_moat" and components.get("data_pipeline", {}).get("proprietary_data"):
            risk_score -= 18
        if risk["id"] == "architecture_defensibility" and len(components.get("custom_logic", [])) >= 2:
            risk_score -= 12
        if risk["id"] == "production_readiness" and components.get("infrastructure", {}).get("custom_infra"):
            risk_score -= 10

        risk_score = round(clamp(risk_score, 5, 95))
        status = "controlled" if risk_score <= 34 else "watch" if risk_score <= 64 else "critical"

        register.append({
            "id": risk["id"],
            "name": risk["name"],
            "framework": risk["framework"],
            "risk_score": risk_score,
            "status": status,
            "why_it_matters": risk["why_it_matters"],
            "positive_evidence": positive_evidence,
            "negative_evidence": negative_evidence,
            "validation_question": risk["validation_question"],
        })

    return register


def build_reliability_report(document_text: str, components: dict, risk_register: list[dict], llm_confidence: int) -> dict:
    """Estimate analysis confidence from document quality and evidence density."""
    word_count = len(document_text.split())
    heading_count = len(re.findall(r"^\s{0,3}#{1,4}\s+", document_text, flags=re.MULTILINE))
    metric_count = len(re.findall(r"(\d+(\.\d+)?\s?(%|ms|sec|s|m|b|k|x|params|events/day|arr))", document_text.lower()))
    evidence_count = sum(len(r["positive_evidence"]) + len(r["negative_evidence"]) for r in risk_register)

    deterministic_checks = [
        {
            "name": "Architecture components extracted",
            "status": "present" if components.get("models_used") or components.get("custom_logic") else "missing",
            "detail": f"{len(components.get('models_used', []))} models and {len(components.get('custom_logic', []))} custom components extracted.",
        },
        {
            "name": "Proprietary data described",
            "status": "present" if components.get("data_pipeline", {}).get("proprietary_data") else "missing",
            "detail": components.get("data_pipeline", {}).get("description", "No proprietary data pipeline confirmed."),
        },
        {
            "name": "Evaluation evidence present",
            "status": "present" if metric_count >= 3 or any(r["id"] == "evaluation_rigor" and r["positive_evidence"] for r in risk_register) else "missing",
            "detail": f"Found {metric_count} quantitative claim(s) and evaluation-related evidence snippets.",
        },
        {
            "name": "Security and agency controls present",
            "status": "present" if any(r["id"] == "genai_security" and r["positive_evidence"] for r in risk_register) else "missing",
            "detail": "Looks for guardrails, validators, least privilege, human approval, sandboxing, or prompt-injection controls.",
        },
        {
            "name": "Production readiness described",
            "status": "present" if components.get("infrastructure", {}).get("scaling_approach") or any(r["id"] == "production_readiness" and r["positive_evidence"] for r in risk_register) else "partial",
            "detail": components.get("infrastructure", {}).get("scaling_approach", "Only partial scale/reliability evidence found."),
        },
    ]

    doc_quality = clamp((min(word_count, 900) / 900) * 42 + min(heading_count, 8) * 4 + min(metric_count, 8) * 3)
    evidence_quality = clamp(min(evidence_count, 18) / 18 * 100)
    confidence = round(clamp((llm_confidence * 10 * 0.42) + (doc_quality * 0.30) + (evidence_quality * 0.28)))

    return {
        "analysis_confidence": confidence,
        "document_quality_score": round(doc_quality),
        "evidence_density_score": round(evidence_quality),
        "word_count": word_count,
        "heading_count": heading_count,
        "quantitative_claims": metric_count,
        "source_evidence_snippets": evidence_count,
        "deterministic_checks": deterministic_checks,
        "caveat": "This is a first-pass technical diligence assistant. A reviewer should validate company claims, inspect repos, and request benchmarks before drawing final conclusions.",
    }


def build_technical_diligence_brief(result_context: dict, detected_patterns: list[dict], risk_register: list[dict], reliability: dict) -> dict:
    """Assemble the final review posture from scores, risks, and reliability."""
    verdict = result_context.get("overall_verdict", "UNKNOWN")
    avg_score = result_context.get("average_score", 0)
    critical_risks = [risk for risk in risk_register if risk["status"] == "critical"]
    watch_risks = [risk for risk in risk_register if risk["status"] == "watch"]
    critical_patterns = [pattern for pattern in detected_patterns if pattern.get("severity") in {"critical", "high"}]

    if avg_score >= 7 and not critical_risks and reliability["analysis_confidence"] >= 65:
        review_posture = "Advance to focused technical diligence"
        posture_detail = "The architecture appears strong enough for a deeper technical walkthrough."
    elif avg_score >= 5 and len(critical_patterns) <= 1:
        review_posture = "Investigate with targeted evidence"
        posture_detail = "The company may be technically interesting, but specific architecture claims need evidence."
    elif avg_score >= 3:
        review_posture = "Hold for architecture evidence"
        posture_detail = "Do not rely on the technical depth claim until source evidence addresses wrapper risk."
    else:
        review_posture = "Reject current technical claims"
        posture_detail = "The current document reads as low-defensibility or insufficiently evidenced."

    must_validate = []
    for risk in (critical_risks + watch_risks)[:4]:
        must_validate.append(risk["validation_question"])
    for pattern in critical_patterns[:3]:
        must_validate.append(f"Validate signal: {pattern['name']} — {pattern.get('evidence', 'No evidence supplied')}")

    if not must_validate:
        must_validate = [
            "Provide repository walkthrough for the hardest-to-copy technical subsystem.",
            "Share production evaluation metrics and failure cases.",
            "Explain how the architecture improves with proprietary data over time.",
        ]

    return {
        "review_posture": review_posture,
        "posture_detail": posture_detail,
        "verdict": verdict,
        "technical_confidence_score": round(clamp((avg_score * 8) + (reliability["analysis_confidence"] * 0.2) - (len(critical_risks) * 8) - (len(critical_patterns) * 6))),
        "top_reasons": [
            f"Technical depth average: {avg_score}/10.",
            f"Analysis confidence: {reliability['analysis_confidence']} based on document completeness and source evidence.",
            f"{len(detected_patterns)} wrapper anti-pattern(s) and {len(critical_risks)} critical AI risk(s) detected.",
        ],
        "must_validate_next": must_validate[:6],
        "next_technical_diligence_actions": [
            "Request architecture diagram and repo walkthrough with the technical owner.",
            "Ask for benchmark design, raw evaluation set, false-positive/false-negative analysis, and drift monitoring.",
            "Validate data rights, customer-consent model, and whether proprietary data actually compounds.",
            "Pressure-test vendor dependency, inference cost sensitivity, and outage fallback plan.",
        ],
    }


def analyze_startup(document_text: str, startup_name: str = "Startup") -> dict:
    """
    Run the full architecture review pipeline and return UI-ready analysis.
    """
    logger = ReasoningLogger(task_name=f"Architecture Diligence — {startup_name}")
    llm = get_llm()

    # Pipeline phase: component extraction.
    logger.start_step(
        title="Technical Component Extraction",
        description="Parsing the document to identify all technical components: models, data pipelines, APIs, custom logic, infrastructure.",
        step_type="processing",
        input_data=f"Document: {len(document_text)} chars from {startup_name}"
    )

    extract_response = llm.chat(
        messages=[
            {"role": "system", "content": """You are a senior technical diligence reviewer. You specialize in evaluating AI/ML startup architectures.

Given a startup's technical documentation, extract ALL technical components into a structured analysis. Be thorough and specific.

Respond in JSON with these keys:
{
  "models_used": [{"name": "...", "type": "proprietary/fine-tuned/off-the-shelf API", "purpose": "...", "detail": "..."}],
  "data_pipeline": {"description": "...", "proprietary_data": true/false, "data_sources": [...], "processing_steps": [...]},
  "custom_logic": [{"component": "...", "description": "...", "complexity": "high/medium/low"}],
  "api_dependencies": [{"service": "...", "usage": "...", "criticality": "core/supporting/optional"}],
  "infrastructure": {"hosting": "...", "scaling_approach": "...", "custom_infra": [...] },
  "agentic_patterns": [{"pattern": "...", "description": "..."}],
  "key_claims": ["..."],
  "technical_differentiators": ["..."]
}

Be precise. If something is unclear from the document, note it as "[UNCLEAR]". Respond ONLY with valid JSON."""},
            {"role": "user", "content": f"Analyze this technical documentation from {startup_name}:\n\n{document_text}"}
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    try:
        components = extract_json(extract_response)
    except json.JSONDecodeError as e:
        print(f"\n[trace] Component extraction JSON parse error: {e}")
        print(f"[trace] Provider response excerpt:\n{extract_response}\n")
        components = {"error": "Failed to parse component extraction", "raw": extract_response[:500]}

    logger.end_step(output_data=f"Extracted: {len(components.get('models_used', []))} models, {len(components.get('custom_logic', []))} custom components, {len(components.get('api_dependencies', []))} API deps")

    # Pipeline phase: wrapper anti-pattern detection.
    logger.start_step(
        title="Wrapper Anti-Pattern Detection",
        description=f"Checking extracted architecture against {len(WRAPPER_ANTI_PATTERNS)} known wrapper anti-patterns.",
        step_type="retrieval",
        input_data=f"Checking against anti-pattern database"
    )

    detected_patterns = []
    for pattern in WRAPPER_ANTI_PATTERNS:
        # Model-level dependency signals.
        models = components.get("models_used", [])
        for model in models:
            if model.get("type") == "off-the-shelf API" and pattern["id"] == "thin_api_proxy":
                detected_patterns.append({**pattern, "evidence": f"Model '{model.get('name', 'unknown')}' is an off-the-shelf API call"})

        # Data-moat signals.
        pipeline = components.get("data_pipeline", {})
        if not pipeline.get("proprietary_data") and pattern["id"] == "no_proprietary_data":
            detected_patterns.append({**pattern, "evidence": "No proprietary data pipeline identified"})

        # Custom-logic signals.
        custom = components.get("custom_logic", [])
        if len(custom) == 0 and pattern["id"] == "no_custom_logic":
            detected_patterns.append({**pattern, "evidence": "No custom logic components found in architecture"})

        # Agentic-loop signals.
        agentic = components.get("agentic_patterns", [])
        if len(agentic) == 0 and pattern["id"] == "no_agentic_loop":
            detected_patterns.append({**pattern, "evidence": "No agentic patterns or feedback loops detected"})

        # External-dependency concentration signals.
        api_deps = components.get("api_dependencies", [])
        core_deps = [d for d in api_deps if d.get("criticality") == "core"]
        if len(core_deps) >= 2 and pattern["id"] == "over_reliance_external":
            detected_patterns.append({**pattern, "evidence": f"{len(core_deps)} core API dependencies: {', '.join(d.get('service','') for d in core_deps)}"})

    detected_patterns.extend(detect_direct_anti_patterns(document_text))
    detected_patterns = dedupe_patterns(detected_patterns)

    logger.end_step(output_data=f"Detected {len(detected_patterns)} anti-patterns: {', '.join(p['name'] for p in detected_patterns)}" if detected_patterns else "No major wrapper anti-patterns detected ✓")

    # Pipeline phase: depth scoring.
    logger.start_step(
        title="Technical Depth Scoring",
        description=f"Scoring the startup across {len(DEPTH_DIMENSIONS)} technical depth dimensions.",
        step_type="decision",
        input_data="Dimensions: " + ", ".join(d["name"] for d in DEPTH_DIMENSIONS)
    )

    scoring_response = llm.chat(
        messages=[
            {"role": "system", "content": f"""You are scoring an AI startup's technical depth across specific dimensions.
Based on the extracted architecture components and anti-pattern analysis, score each dimension from 1-10.

Dimensions to score:
{json.dumps(DEPTH_DIMENSIONS, indent=2)}

Components extracted:
{json.dumps(components, indent=2)}

Anti-patterns detected:
{json.dumps([{"name": p["name"], "evidence": p.get("evidence","")} for p in detected_patterns], indent=2)}

For each dimension, provide:
- score (1-10)
- evidence (specific reference to what you found or didn't find)
- concern (if score < 6, what's the specific concern)

Also provide:
- overall_verdict: "DEEP TECH" | "MODERATE DEPTH" | "POTENTIAL WRAPPER" | "LIKELY WRAPPER"
- confidence: 1-10 (how confident you are in this assessment)
- one_line_summary: A single sentence summary for the technical diligence team.

Language constraints:
- This is a technical architecture review, not an investment memo.
- Do not use phrases like "investment opportunity", "investable", "IC", "deal", or "memo".
- Write the one_line_summary as a review-ready technical assessment of architecture depth, wrapper risk, and what needs validation next.

Respond in JSON:
{{
  "dimension_scores": [
    {{"dimension": "...", "score": N, "evidence": "...", "concern": "..."}}
  ],
  "overall_verdict": "...",
  "confidence": N,
  "one_line_summary": "..."
}}"""},
            {"role": "user", "content": "Score this startup's technical depth now."}
        ],
        temperature=0.3,
        max_tokens=1500,
    )

    try:
        scores = extract_json(scoring_response)
    except json.JSONDecodeError:
        scores = {"dimension_scores": [], "overall_verdict": "ANALYSIS ERROR", "confidence": 0, "one_line_summary": "Scoring failed — manual review needed"}
    scores = sanitize_review_language(scores)

    avg_score = 0
    if scores.get("dimension_scores"):
        avg_score = round(sum(d.get("score", 0) for d in scores["dimension_scores"]) / len(scores["dimension_scores"]), 1)

    logger.end_step(output_data=f"Verdict: {scores.get('overall_verdict', 'N/A')} | Avg Score: {avg_score}/10 | Confidence: {scores.get('confidence', 'N/A')}/10")

    # Pipeline phase: follow-up question generation.
    logger.start_step(
        title="Diligence Question Generation",
        description="Generating specific, targeted validation questions based on identified gaps and concerns.",
        step_type="generation",
    )

    questions_response = llm.chat(
        messages=[
            {"role": "system", "content": """You are generating technical diligence questions for a reviewer to use in a follow-up conversation with the company.
Based on the technical analysis, generate 5-8 specific, probing questions that would help the reviewer understand:
1. Whether the technical claims are genuine
2. The actual depth of the proprietary technology
3. The defensibility of the approach
4. Potential risks

Each question should reference specific findings from the analysis. Don't ask generic questions — be surgical.

Respond in JSON:
{
  "questions": [
    {
      "question": "...",
      "rationale": "why this question matters",
      "expected_strong_answer": "specific evidence that would make the answer technically credible",
      "red_flag_answer": "answer pattern or missing evidence that would increase concern"
    }
  ]
}"""},
            {"role": "user", "content": f"""Analysis context:
Startup: {startup_name}
Components: {json.dumps(components, indent=2)[:2000]}
Anti-patterns: {json.dumps([p["name"] for p in detected_patterns])}
Depth scores: {json.dumps(scores, indent=2)[:1000]}

Generate targeted diligence questions."""}
        ],
        temperature=0.5,
        max_tokens=2000,
    )

    try:
        questions = extract_json(questions_response)
    except json.JSONDecodeError:
        questions = {"questions": [{"question": "Manual review recommended.", "rationale": "Auto-generation failed", "expected_strong_answer": "", "red_flag_answer": ""}]}
    questions = sanitize_review_language(questions)

    logger.end_step(output_data=f"Generated {len(questions.get('questions', []))} targeted diligence questions")

    # Pipeline phase: risk register and evidence calibration.
    logger.start_step(
        title="Risk Register and Evidence Calibration",
        description="Building a deterministic risk register aligned to Together's technical diligence lens, NIST AI RMF, and OWASP LLM risk categories.",
        step_type="retrieval",
    )

    risk_register = build_risk_register(document_text, components, detected_patterns)
    reliability = build_reliability_report(
        document_text=document_text,
        components=components,
        risk_register=risk_register,
        llm_confidence=int(scores.get("confidence", 0) or 0),
    )

    logger.end_step(output_data=f"Risk register complete: {sum(1 for r in risk_register if r['status'] == 'critical')} critical, {sum(1 for r in risk_register if r['status'] == 'watch')} watch. Analysis confidence: {reliability['analysis_confidence']}/100")

    # Pipeline phase: final report assembly.
    logger.start_step(
        title="Compiling Diligence Report",
        description="Assembling the complete architecture diligence report.",
        step_type="decision",
    )

    technical_diligence_brief = build_technical_diligence_brief(
        result_context={
            "overall_verdict": scores.get("overall_verdict", "N/A"),
            "average_score": avg_score,
        },
        detected_patterns=detected_patterns,
        risk_register=risk_register,
        reliability=reliability,
    )

    result = {
        "startup_name": startup_name,
        "components": components,
        "anti_patterns_detected": detected_patterns,
        "depth_scores": scores,
        "average_score": avg_score,
        "diligence_questions": questions.get("questions", []),
        "risk_register": risk_register,
        "reliability": reliability,
        "technical_diligence_brief": technical_diligence_brief,
        "reasoning_log": logger.get_all_steps(),
    }
    result = sanitize_review_language(result)

    logger.end_step(output_data=f"Report complete. Review posture: {technical_diligence_brief['review_posture']} | Verdict: {scores.get('overall_verdict', 'N/A')} | {len(detected_patterns)} anti-patterns | {len(questions.get('questions', []))} questions generated")

    return result
