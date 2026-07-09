"""
Wrapper-risk taxonomy and technical-depth scoring dimensions.

The diligence pipeline uses these definitions for repeatable architecture
review, independent of any single model response.
"""

WRAPPER_ANTI_PATTERNS = [
    {
        "id": "thin_api_proxy",
        "name": "Thin API Proxy",
        "description": "The product is essentially a UI layer over a third-party LLM API with minimal custom logic.",
        "severity": "critical",
        "indicators": ["Direct GPT-4/Claude API passthrough", "No custom model training", "Simple prompt templates", "Value comes from UX not technology"],
    },
    {
        "id": "no_proprietary_data",
        "name": "No Proprietary Data Pipeline",
        "description": "No proprietary or curated dataset that gives the product a unique advantage.",
        "severity": "high",
        "indicators": ["Only uses publicly available data", "No data collection moat", "No domain-specific training data", "RAG over public documents only"],
    },
    {
        "id": "no_custom_logic",
        "name": "No Custom Logic Layer",
        "description": "No meaningful custom algorithms, processing, or business logic beyond API orchestration.",
        "severity": "critical",
        "indicators": ["No custom scoring/ranking", "No proprietary algorithms", "No domain-specific processing", "Simple CRUD operations only"],
    },
    {
        "id": "no_agentic_loop",
        "name": "No Agentic Feedback Loop",
        "description": "System makes single-pass API calls without iterative reasoning, self-correction, or multi-step orchestration.",
        "severity": "medium",
        "indicators": ["Single API call per request", "No retry/correction logic", "No multi-step planning", "No tool use or function calling"],
    },
    {
        "id": "over_reliance_external",
        "name": "Over-Reliance on External APIs",
        "description": "Core functionality depends entirely on third-party services that could be replicated by competitors.",
        "severity": "high",
        "indicators": ["Multiple core-critical API dependencies", "No fallback if API goes down", "Vendor lock-in risk", "Competitors can use same APIs"],
    },
    {
        "id": "no_evaluation_framework",
        "name": "No Evaluation/Testing Framework",
        "description": "No systematic way to measure, test, or improve model performance.",
        "severity": "medium",
        "indicators": ["No benchmarks mentioned", "No A/B testing", "No quality metrics", "No evaluation pipeline"],
    },
    {
        "id": "generic_prompts",
        "name": "Generic Prompt Engineering Only",
        "description": "The only 'AI' is carefully crafted prompts with no deeper technical work.",
        "severity": "high",
        "indicators": ["Prompt engineering as primary moat", "No fine-tuning or training", "Templates could be replicated in hours", "No retrieval augmentation"],
    },
    {
        "id": "no_scale_architecture",
        "name": "No Scale Architecture",
        "description": "Architecture doesn't demonstrate thinking about scale, latency, or production reliability.",
        "severity": "medium",
        "indicators": ["No mention of caching", "No load balancing", "No async processing", "Single-server deployment"],
    },
]


DEPTH_DIMENSIONS = [
    {
        "name": "Custom Model / Fine-tuning",
        "description": "Does the startup have custom-trained or fine-tuned models, or do they rely entirely on off-the-shelf LLM APIs?",
        "weight": 0.25,
        "scoring_guide": {
            "1-3": "Pure API wrapper — no custom models, just prompt engineering",
            "4-6": "Some fine-tuning or embeddings customization, but core reasoning is third-party",
            "7-10": "Custom-trained models, proprietary architectures, or significant fine-tuning with domain data"
        }
    },
    {
        "name": "Proprietary Data Pipeline",
        "description": "Does the startup have access to unique, proprietary data that gives them an advantage?",
        "weight": 0.20,
        "scoring_guide": {
            "1-3": "Public data only — anyone could replicate",
            "4-6": "Some proprietary data collection, but not deeply differentiated",
            "7-10": "Unique data moat — exclusive partnerships, proprietary datasets, or novel data collection methods"
        }
    },
    {
        "name": "Agentic Architecture",
        "description": "Does the system demonstrate multi-step reasoning, tool use, self-correction, or autonomous operation?",
        "weight": 0.20,
        "scoring_guide": {
            "1-3": "Single-pass API calls — no autonomy",
            "4-6": "Some multi-step orchestration or tool use",
            "7-10": "Sophisticated agentic loops with planning, execution, evaluation, and self-correction"
        }
    },
    {
        "name": "Infrastructure Moat",
        "description": "Has the startup built significant infrastructure that would be hard to replicate?",
        "weight": 0.15,
        "scoring_guide": {
            "1-3": "Standard cloud deployment — no custom infrastructure",
            "4-6": "Some custom infrastructure (caching, queuing, etc.)",
            "7-10": "Deep infrastructure depth — custom inference engines, distributed processing, proprietary deployment"
        }
    },
    {
        "name": "Domain-Specific Logic",
        "description": "Does the product encode deep domain knowledge that goes beyond generic AI capabilities?",
        "weight": 0.20,
        "scoring_guide": {
            "1-3": "Generic AI application — no domain specificity",
            "4-6": "Some domain customization in prompts or data",
            "7-10": "Deep domain logic — custom rules engines, industry-specific algorithms, regulatory knowledge"
        }
    },
]
