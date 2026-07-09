import { useEffect, useMemo, useState, type ReactNode } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001'

interface ReasoningStep {
  step_number: number
  title: string
  description: string
  input_data?: string
  output_data?: string
  duration_ms?: number
  step_type: string
  timestamp: string
}

interface ScoreBreakdown {
  domain_match: number
  skill_match: number
  role_fit: number
  bio_relevance: number
  advisory_relevance: number
  corridor_fit: number
  stage_fit: number
  availability: number
  urgency_fit: number
  conflict_penalty: number
}

interface Evidence {
  domain_matches: string[]
  skill_matches: string[]
  bio_terms: string[]
  advisory_terms: string[]
  roles: string[]
  stage_fit: string[]
}

interface Expert {
  rank: number
  id: string
  name: string
  title: string
  location: string
  bio: string
  domains: string[]
  expertise_tags: string[]
  past_advisory: string[]
  match_score: number
  confidence: number
  fit_label: string
  routing_role: string
  match_reasons: string[]
  score_breakdown: ScoreBreakdown
  evidence: Evidence
  availability: 'high' | 'medium' | 'low' | 'unknown'
  corridor_expertise: string
}

interface Recommendation {
  name: string
  rationale: string
  conversation_starter: string
  complementary_value: string
}

interface Rationale {
  recommendations: Recommendation[]
  routing_strategy: string
}

interface DispatchStep {
  step: number
  label: string
  expert: string
  role: string
  objective: string
  timebox: string
}

interface DispatchPlan {
  decision: string
  primary_expert: string
  primary_role: string
  confidence: number
  urgency: string
  stage: string
  why_now: string
  sequence: DispatchStep[]
  routing_strategy: string
  clarifying_question: string
}

interface IntroPack {
  subject: string
  intro_email: string
  context_to_send: string[]
  prep_questions: string[]
  success_criteria: string[]
}

interface NearMiss {
  name: string
  title: string
  match_score: number
  why_not_selected: string
  use_if: string
}

interface CoverageGap {
  role: string
  severity: 'high' | 'medium' | 'low'
  reason: string
  recruiting_signal: string
}

interface NetworkStats {
  profiles_loaded: number
  demo_slice_note: string
  roles_covered: number
  top_roles: Array<{ role: string; count: number }>
  availability: Record<string, number>
  location_mix: Record<string, number>
}

interface SampleQuery {
  label: string
  query: string
}

interface RoutingResult {
  query: string
  intent: {
    primary_domains?: string[]
    specific_skills?: string[]
    context_summary?: string
    urgency?: string
    corridor_relevance?: string
    company_stage?: string
    inferred_need_type?: string
    hidden_risks?: string[]
    desired_outcome?: string
    suggested_expert_roles?: string[]
    clarifying_question?: string
    confidence?: number
  }
  network_stats: NetworkStats
  dispatch_plan: DispatchPlan
  top_experts: Expert[]
  candidate_pool: Expert[]
  near_misses: NearMiss[]
  coverage_gaps: CoverageGap[]
  rationale: Rationale
  intro_pack: IntroPack
  reasoning_log: ReasoningStep[]
}

type SectionId = 'intent' | 'experts' | 'nearMisses' | 'intro' | 'coverage' | 'reasoning'

const DEFAULT_OPEN: Record<SectionId, boolean> = {
  intent: true,
  experts: true,
  nearMisses: true,
  intro: true,
  coverage: true,
  reasoning: false,
}

const FALLBACK_SAMPLES: SampleQuery[] = [
  {
    label: 'Security pilot blocked',
    query:
      "We are an Indian AI security startup trying to land our first Fortune 500 pilot. The buyer is asking for SOC2, data residency, and a formal security review. We don't know if this is a sales problem, compliance problem, or product architecture problem.",
  },
  {
    label: 'US enterprise GTM',
    query:
      'Our PLG motion is working for technical SMB users, but enterprise shadow IT adoption is creating pull from larger accounts. We need to build an outbound US enterprise sales motion without hiring the wrong VP Sales too early.',
  },
  {
    label: 'Entity flip before Series A',
    query:
      'We need to flip our Indian entity to a Delaware C-Corp before our Series A. We are worried about IP assignment, ESOP pool sizing, transfer pricing, and how this affects the next financing round.',
  },
  {
    label: 'AI infra cost burn',
    query:
      'We are burning through cloud credits faster than expected while serving LLM inference on GCP. We need help reducing cost per request before credits run out and before usage scales 10x.',
  },
  {
    label: 'Healthcare AI procurement',
    query:
      'We are building a clinical AI workflow product and a US hospital wants a pilot. They are asking about HIPAA, EHR integration, patient safety, and procurement steps. We need to know who can prepare us.',
  },
]

const processingSteps = [
  'Extract operating need',
  'Retrieve expert candidates',
  'Score role and evidence fit',
  'Calibrate near misses',
  'Prepare outreach pack',
]

const graphPositions = [
  { x: 51, y: 16 },
  { x: 78, y: 31 },
  { x: 75, y: 68 },
  { x: 50, y: 83 },
  { x: 23, y: 68 },
  { x: 21, y: 31 },
  { x: 88, y: 51 },
  { x: 12, y: 51 },
]

const clamp = (value: number, min = 0, max = 100) => Math.max(min, Math.min(max, value))

const truncate = (value: string | undefined, length = 120) => {
  const text = value?.trim() || ''
  return text.length > length ? `${text.slice(0, length).trim()}…` : text
}

function normalizeLabel(value: string | undefined, fallback = 'Unknown') {
  if (!value) return fallback
  return value
    .replace(/-/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

type LooseRecord = Record<string, unknown>

const FALLBACK_NETWORK_STATS: NetworkStats = {
  profiles_loaded: 25,
  demo_slice_note: 'Synthetic demo slice; production can connect to the live expert CRM.',
  roles_covered: 12,
  top_roles: [
    { role: 'Enterprise GTM', count: 4 },
    { role: 'Security / compliance', count: 3 },
    { role: 'Cloud infrastructure', count: 3 },
    { role: 'Legal structuring', count: 2 },
    { role: 'Product / PLG', count: 4 },
    { role: 'Finance / operations', count: 3 },
  ],
  availability: { high: 9, medium: 10, low: 6 },
  location_mix: { India: 10, US: 10, Global: 5 },
}

function isRecord(value: unknown): value is LooseRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function asString(value: unknown, fallback = '') {
  return typeof value === 'string' && value.trim() ? value.trim() : fallback
}

function asNumber(value: unknown, fallback = 0) {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const parsed = Number(value.replace('%', ''))
    if (Number.isFinite(parsed)) return parsed
  }
  return fallback
}

function asStringArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => asString(item)).filter(Boolean)
  if (typeof value === 'string' && value.trim()) return [value.trim()]
  return []
}

function asRecordArray(value: unknown): LooseRecord[] {
  return Array.isArray(value) ? value.filter(isRecord) : []
}

function normalizeScore(value: unknown, fallback: number) {
  const score = asNumber(value, fallback)
  const scaled = score > 0 && score <= 1 ? score * 100 : score
  return Math.round(clamp(scaled) * 10) / 10
}

function normalizeNetworkStats(value: unknown, fallback?: NetworkStats | null): NetworkStats {
  if (!isRecord(value)) return fallback || FALLBACK_NETWORK_STATS
  return {
    profiles_loaded: asNumber(value.profiles_loaded, fallback?.profiles_loaded || FALLBACK_NETWORK_STATS.profiles_loaded),
    demo_slice_note: asString(value.demo_slice_note, fallback?.demo_slice_note || FALLBACK_NETWORK_STATS.demo_slice_note),
    roles_covered: asNumber(value.roles_covered, fallback?.roles_covered || FALLBACK_NETWORK_STATS.roles_covered),
    top_roles: asRecordArray(value.top_roles).map((role) => ({
      role: asString(role.role, 'Operator'),
      count: asNumber(role.count, 1),
    })).slice(0, 8) || fallback?.top_roles || FALLBACK_NETWORK_STATS.top_roles,
    availability: isRecord(value.availability) ? Object.fromEntries(Object.entries(value.availability).map(([key, count]) => [key, asNumber(count, 0)])) : fallback?.availability || FALLBACK_NETWORK_STATS.availability,
    location_mix: isRecord(value.location_mix) ? Object.fromEntries(Object.entries(value.location_mix).map(([key, count]) => [key, asNumber(count, 0)])) : fallback?.location_mix || FALLBACK_NETWORK_STATS.location_mix,
  }
}

function normalizeIntent(value: unknown, query: string): RoutingResult['intent'] {
  const record = isRecord(value) ? value : {}
  const lowerQuery = query.toLowerCase()
  const fallbackRoles = [
    lowerQuery.includes('soc2') || lowerQuery.includes('security') ? 'security_compliance' : '',
    lowerQuery.includes('fortune 500') || lowerQuery.includes('sales') || lowerQuery.includes('gtm') ? 'enterprise_gtm' : '',
    lowerQuery.includes('gcp') || lowerQuery.includes('cloud') || lowerQuery.includes('inference') ? 'cloud_infra' : '',
    lowerQuery.includes('delaware') || lowerQuery.includes('entity') || lowerQuery.includes('ip assignment') ? 'legal_structuring' : '',
    lowerQuery.includes('hospital') || lowerQuery.includes('hipaa') ? 'healthcare_regulatory' : '',
  ].filter(Boolean)

  return {
    primary_domains: asStringArray(record.primary_domains || record.domains).length ? asStringArray(record.primary_domains || record.domains) : fallbackRoles.map((role) => normalizeLabel(role)),
    specific_skills: asStringArray(record.specific_skills || record.skills || record.expertise_needed).length ? asStringArray(record.specific_skills || record.skills || record.expertise_needed) : ['operator diagnosis', 'expert routing', 'founder support'],
    context_summary: asString(record.context_summary || record.summary || record.problem_summary, truncate(query, 260)),
    urgency: asString(record.urgency, lowerQuery.includes('blocked') || lowerQuery.includes('pilot') ? 'high' : 'medium'),
    corridor_relevance: asString(record.corridor_relevance, lowerQuery.includes('india') || lowerQuery.includes('us') ? 'yes' : 'no'),
    company_stage: asString(record.company_stage || record.stage, lowerQuery.includes('series a') ? 'series-a' : 'seed'),
    inferred_need_type: asString(record.inferred_need_type || record.need_type, fallbackRoles.length ? normalizeLabel(fallbackRoles[0]) : 'Operator support'),
    hidden_risks: asStringArray(record.hidden_risks || record.risks),
    desired_outcome: asString(record.desired_outcome, 'Route the founder to the fastest useful expert conversation and prepare the context needed for that call.'),
    suggested_expert_roles: asStringArray(record.suggested_expert_roles || record.expert_roles).length ? asStringArray(record.suggested_expert_roles || record.expert_roles) : fallbackRoles,
    clarifying_question: asString(record.clarifying_question),
    confidence: asNumber(record.confidence, fallbackRoles.length ? 72 : 52),
  }
}

function extractExpertRecords(payload: LooseRecord): LooseRecord[] {
  const possibleArrays = [
    payload.top_experts,
    payload.candidate_pool,
    payload.top_matches,
    payload.matches,
    payload.experts,
    payload.recommendations,
    payload.results,
  ]
  const firstArray = possibleArrays.find((value) => Array.isArray(value))
  return asRecordArray(firstArray)
}

function normalizeExpert(raw: LooseRecord, index: number): Expert {
  const name = asString(raw.name || raw.expert_name || raw.expert, `Expert ${index + 1}`)
  const title = asString(raw.title || raw.role || raw.position, 'Operator / advisor')
  const domains = asStringArray(raw.domains || raw.domain)
  const expertiseTags = asStringArray(raw.expertise_tags || raw.tags || raw.skills || raw.expertise)
  const matchScore = normalizeScore(raw.match_score || raw.score || raw.relevance_score || raw.confidence, Math.max(84 - index * 8, 58))
  const scoreBreakdown = isRecord(raw.score_breakdown) ? raw.score_breakdown : {}
  const evidence = isRecord(raw.evidence) ? raw.evidence : {}
  const matchReasons = asStringArray(raw.match_reasons || raw.reasons || raw.reason || raw.why_match || raw.rationale || raw.explanation)

  return {
    rank: asNumber(raw.rank, index + 1),
    id: asString(raw.id, `expert-${index + 1}-${name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`),
    name,
    title,
    location: asString(raw.location, 'Global'),
    bio: asString(raw.bio || raw.summary || raw.description || raw.rationale, 'Legacy router response did not include full profile metadata.'),
    domains,
    expertise_tags: expertiseTags,
    past_advisory: asStringArray(raw.past_advisory || raw.advisory_history),
    match_score: matchScore,
    confidence: normalizeScore(raw.confidence, Math.min(96, matchScore + 6)),
    fit_label: asString(raw.fit_label, index === 0 ? 'Primary route' : index === 1 ? 'Backup route' : 'Specialist fit'),
    routing_role: asString(raw.routing_role || raw.role_label || raw.role, domains[0] || expertiseTags[0] || 'Operator'),
    match_reasons: matchReasons.length ? matchReasons : ['Returned by the router as a relevant expert for this founder request.'],
    score_breakdown: {
      domain_match: asNumber(scoreBreakdown.domain_match, Math.max(18 - index * 2, 10)),
      skill_match: asNumber(scoreBreakdown.skill_match, Math.max(22 - index * 2, 12)),
      role_fit: asNumber(scoreBreakdown.role_fit, Math.max(14 - index * 2, 8)),
      bio_relevance: asNumber(scoreBreakdown.bio_relevance, 10),
      advisory_relevance: asNumber(scoreBreakdown.advisory_relevance, 8),
      corridor_fit: asNumber(scoreBreakdown.corridor_fit, 6),
      stage_fit: asNumber(scoreBreakdown.stage_fit, 7),
      availability: asNumber(scoreBreakdown.availability, 5),
      urgency_fit: asNumber(scoreBreakdown.urgency_fit, 5),
      conflict_penalty: asNumber(scoreBreakdown.conflict_penalty, 0),
    },
    evidence: {
      domain_matches: asStringArray(evidence.domain_matches),
      skill_matches: asStringArray(evidence.skill_matches),
      bio_terms: asStringArray(evidence.bio_terms),
      advisory_terms: asStringArray(evidence.advisory_terms),
      roles: asStringArray(evidence.roles),
      stage_fit: asStringArray(evidence.stage_fit),
    },
    availability: ['high', 'medium', 'low', 'unknown'].includes(asString(raw.availability)) ? asString(raw.availability) as Expert['availability'] : 'unknown',
    corridor_expertise: asString(raw.corridor_expertise, 'Operator network support'),
  }
}

function normalizeRoutingResult(payload: unknown, submittedQuery: string, fallbackStats?: NetworkStats | null): RoutingResult {
  if (!isRecord(payload)) {
    throw new Error('Router returned an unreadable response. Please restart the Tool 2 backend and try again.')
  }

  const intent = normalizeIntent(payload.intent || payload.query_intent || payload.analysis, submittedQuery)
  const expertRecords = extractExpertRecords(payload)
  const topExperts = expertRecords.slice(0, 3).map(normalizeExpert)

  if (!topExperts.length) {
    throw new Error('Router response did not include expert matches. The backend on port 8001 looks stale; restart Tool 2 backend and refresh the page.')
  }

  const candidateRecords = asRecordArray(payload.candidate_pool).length ? asRecordArray(payload.candidate_pool) : expertRecords
  const candidatePool = candidateRecords.slice(0, 8).map(normalizeExpert)
  const dispatchRecord = isRecord(payload.dispatch_plan) ? payload.dispatch_plan : {}
  const primary = topExperts[0]
  const backup = topExperts[1]
  const specialist = topExperts[2]
  const sequence = asRecordArray(dispatchRecord.sequence).length
    ? asRecordArray(dispatchRecord.sequence).map((step, index) => ({
        step: asNumber(step.step, index + 1),
        label: asString(step.label, index === 0 ? 'Primary diagnosis call' : index === 1 ? 'Backup operator call' : 'Specialist review'),
        expert: asString(step.expert, topExperts[index]?.name || primary.name),
        role: asString(step.role, topExperts[index]?.routing_role || 'Operator'),
        objective: asString(step.objective, 'Convert the founder request into a concrete next action.'),
        timebox: asString(step.timebox, index === 2 ? '20 minutes' : '30 minutes'),
      }))
    : [
        {
          step: 1,
          label: 'Primary diagnosis call',
          expert: primary.name,
          role: primary.routing_role,
          objective: 'Identify the true blocker and the artifact needed before the next external conversation.',
          timebox: '30 minutes',
        },
        ...(backup ? [{
          step: 2,
          label: 'Backup operator call',
          expert: backup.name,
          role: backup.routing_role,
          objective: 'Convert the diagnosis into a tactical sequence and backup route.',
          timebox: '30 minutes',
        }] : []),
        ...(specialist ? [{
          step: 3,
          label: 'Specialist review',
          expert: specialist.name,
          role: specialist.routing_role,
          objective: 'Pressure-test the highest-risk specialist area before the next customer, investor, or partner conversation.',
          timebox: '20 minutes',
        }] : []),
      ]

  const rationaleRecord = isRecord(payload.rationale) ? payload.rationale : {}
  const introRecord = isRecord(payload.intro_pack) ? payload.intro_pack : {}

  return {
    query: asString(payload.query, submittedQuery),
    intent,
    network_stats: normalizeNetworkStats(payload.network_stats, fallbackStats),
    dispatch_plan: {
      decision: asString(dispatchRecord.decision, `Start with ${primary.name}`),
      primary_expert: asString(dispatchRecord.primary_expert, primary.name),
      primary_role: asString(dispatchRecord.primary_role, primary.routing_role),
      confidence: asNumber(dispatchRecord.confidence, Math.round(topExperts.reduce((sum, expert) => sum + expert.confidence, 0) / topExperts.length)),
      urgency: asString(dispatchRecord.urgency, intent.urgency || 'medium'),
      stage: asString(dispatchRecord.stage, intent.company_stage || 'seed'),
      why_now: asString(dispatchRecord.why_now, intent.desired_outcome || 'Fast expert diagnosis is likely to unblock the next operating decision.'),
      sequence,
      routing_strategy: asString(dispatchRecord.routing_strategy || rationaleRecord.routing_strategy, `Start with ${primary.name}, keep ${backup?.name || 'a backup operator'} as the follow-up lane, and use the specialist only if the first call exposes a deeper blocker.`),
      clarifying_question: asString(dispatchRecord.clarifying_question, intent.clarifying_question || ''),
    },
    top_experts: topExperts,
    candidate_pool: candidatePool.length ? candidatePool : topExperts,
    near_misses: asRecordArray(payload.near_misses).map((expert, index) => ({
      name: asString(expert.name, `Near miss ${index + 1}`),
      title: asString(expert.title, 'Adjacent expert'),
      match_score: normalizeScore(expert.match_score || expert.score, Math.max(58 - index * 4, 42)),
      why_not_selected: asString(expert.why_not_selected || expert.reason, 'Useful adjacent profile, but the selected route is stronger for the immediate blocker.'),
      use_if: asString(expert.use_if, 'Use if the primary route exposes this specialist need.'),
    })),
    coverage_gaps: asRecordArray(payload.coverage_gaps).map((gap) => ({
      role: asString(gap.role, 'Coverage gap'),
      severity: ['high', 'medium', 'low'].includes(asString(gap.severity)) ? asString(gap.severity) as CoverageGap['severity'] : 'medium',
      reason: asString(gap.reason, 'The current profile slice has weak coverage for this need.'),
      recruiting_signal: asString(gap.recruiting_signal, 'Add or tag one more operator with this experience.'),
    })),
    rationale: {
      recommendations: asRecordArray(rationaleRecord.recommendations).length
        ? asRecordArray(rationaleRecord.recommendations).map((recommendation, index) => ({
            name: asString(recommendation.name, topExperts[index]?.name || primary.name),
            rationale: asString(recommendation.rationale, topExperts[index]?.match_reasons[0] || 'Strong route fit.'),
            conversation_starter: asString(recommendation.conversation_starter, 'What would you diagnose first, and what artifact should the founder prepare?'),
            complementary_value: asString(recommendation.complementary_value, 'Adds a complementary operator perspective.'),
          }))
        : topExperts.map((expert) => ({
            name: expert.name,
            rationale: expert.match_reasons[0],
            conversation_starter: 'What would you diagnose first, and what artifact should the founder prepare?',
            complementary_value: expert.corridor_expertise,
          })),
      routing_strategy: asString(rationaleRecord.routing_strategy, `Start with ${primary.name}; use the next experts as backup and specialist lanes.`),
    },
    intro_pack: {
      subject: asString(introRecord.subject, `Intro: ${primary.name} <> founder on ${intent.inferred_need_type || 'operator support'}`),
      intro_email: asString(introRecord.intro_email, `Hi ${primary.name.split(' ')[0]},\n\nWe have a founder who could use your perspective on ${String(intent.inferred_need_type || 'an operating blocker').toLowerCase()}.\n\nContext: ${intent.context_summary || submittedQuery}\n\nWhy you: ${primary.match_reasons[0]}\n\nWould you be open to a focused 30-minute diagnosis call?`),
      context_to_send: asStringArray(introRecord.context_to_send).length ? asStringArray(introRecord.context_to_send) : [intent.context_summary || submittedQuery],
      prep_questions: asStringArray(introRecord.prep_questions).length ? asStringArray(introRecord.prep_questions) : [
        'What would you diagnose first?',
        'What artifact should the founder prepare before the next external conversation?',
        'What would make this route fail?',
      ],
      success_criteria: asStringArray(introRecord.success_criteria).length ? asStringArray(introRecord.success_criteria) : [
        'Founder leaves with a concrete next artifact.',
        'The real blocker is separated from the surface request.',
        'A backup expert lane is clear if needed.',
      ],
    },
    reasoning_log: asRecordArray(payload.reasoning_log).map((step, index) => ({
      step_number: asNumber(step.step_number, index + 1),
      title: asString(step.title, `Step ${index + 1}`),
      description: asString(step.description, 'Legacy reasoning step.'),
      input_data: asString(step.input_data),
      output_data: asString(step.output_data),
      duration_ms: asNumber(step.duration_ms, 0),
      step_type: asString(step.step_type, 'processing'),
      timestamp: asString(step.timestamp, new Date().toISOString()),
    })),
  }
}

function CollapsibleSection({
  id,
  title,
  kicker,
  preview,
  open,
  onToggle,
  children,
}: {
  id: SectionId
  title: string
  kicker: string
  preview: string
  open: boolean
  onToggle: (id: SectionId) => void
  children: ReactNode
}) {
  return (
    <section className={`section-card ${open ? 'open' : 'closed'}`}>
      <button className="section-toggle" type="button" onClick={() => onToggle(id)} aria-expanded={open}>
        <span className="section-symbol">{open ? '−' : '+'}</span>
        <span className="section-copy">
          <span className="section-kicker">{kicker}</span>
          <span className="section-title">{title}</span>
          <span className="section-preview">{preview}</span>
        </span>
        <span className="section-action">{open ? 'Collapse' : 'Expand'}</span>
      </button>
      {open && <div className="section-body">{children}</div>}
    </section>
  )
}

function ScoreBar({ label, value, max = 26 }: { label: string; value: number; max?: number }) {
  const pct = clamp((value / max) * 100)
  return (
    <div className="score-bar-row">
      <div className="score-bar-meta">
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
      <div className="score-bar-track">
        <div style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function ExpertNetworkMap({ result }: { result: RoutingResult }) {
  const topNames = new Set(result.top_experts.map((expert) => expert.name))
  const nearMissNames = new Set(result.near_misses.map((expert) => expert.name))
  const graphExperts = result.candidate_pool.slice(0, 8)
  const centerLabel = result.intent.inferred_need_type || 'Founder need'

  return (
    <section className="network-map-card">
      <div className="map-heading">
        <div>
          <span className="section-kicker">Expert graph</span>
          <h2>Network command center</h2>
        </div>
        <div className="map-legend">
          <span><i className="legend-dot selected" /> selected route</span>
          <span><i className="legend-dot near" /> near miss</span>
          <span><i className="legend-dot pool" /> candidate pool</span>
        </div>
      </div>

      <div className="network-map">
        <svg viewBox="0 0 100 100" className="network-lines" aria-hidden="true">
          <circle cx="50" cy="50" r="26" />
          <circle cx="50" cy="50" r="39" />
          {graphExperts.map((expert, index) => {
            const pos = graphPositions[index] || graphPositions[0]
            return (
              <line
                key={expert.id}
                x1="50"
                y1="50"
                x2={pos.x}
                y2={pos.y}
                className={topNames.has(expert.name) ? 'selected' : nearMissNames.has(expert.name) ? 'near' : 'pool'}
              />
            )
          })}
        </svg>

        <div className="founder-node">
          <span>Founder need</span>
          <strong>{centerLabel}</strong>
          <small>{normalizeLabel(result.dispatch_plan.stage)} · {normalizeLabel(result.dispatch_plan.urgency)} urgency</small>
        </div>

        {graphExperts.map((expert, index) => {
          const pos = graphPositions[index] || graphPositions[0]
          const state = topNames.has(expert.name) ? 'selected' : nearMissNames.has(expert.name) ? 'near' : 'pool'
          return (
            <article
              className={`expert-node ${state}`}
              key={expert.id}
              style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
              title={`${expert.name}: ${expert.match_score}/100`}
            >
              <span>{Math.round(expert.match_score)}</span>
              <strong>{expert.name.split(' ')[0]}</strong>
              <small>{expert.routing_role}</small>
            </article>
          )
        })}
      </div>
    </section>
  )
}

function expertRouteNote(expert: Expert, result: RoutingResult) {
  const selectedIndex = result.top_experts.findIndex((item) => item.id === expert.id || item.name === expert.name)
  if (selectedIndex === 0) return 'Primary route: strongest immediate fit for the first diagnostic call.'
  if (selectedIndex === 1) return 'Backup lane: strong adjacent fit if the first conversation exposes this operating angle.'
  if (selectedIndex === 2) return 'Specialist review: useful after the first call narrows the blocker.'

  const nearMiss = result.near_misses.find((item) => item.name === expert.name)
  if (nearMiss) return nearMiss.why_not_selected

  return 'Not first choice because the selected route has stronger immediate role, stage, or urgency fit for this request.'
}

function buildDispatchMarkdown(result: RoutingResult) {
  return [
    '# The Zone Dispatch Brief',
    '',
    `**Decision:** ${result.dispatch_plan.decision}`,
    `**Confidence:** ${result.dispatch_plan.confidence}%`,
    `**Founder need:** ${result.intent.inferred_need_type || 'Operator support'}`,
    '',
    '## Context',
    result.intent.context_summary || result.query,
    '',
    '## Route sequence',
    ...result.dispatch_plan.sequence.map((step) => `- **${step.label} — ${step.expert}** (${step.timebox}): ${step.objective}`),
    '',
    '## Ranked expert pool',
    ...result.candidate_pool.slice(0, 6).map((expert) => `- **#${expert.rank} ${expert.name}** — ${expert.match_score}/100, ${expert.routing_role}. ${expertRouteNote(expert, result)}`),
    '',
    '## Near misses',
    ...(result.near_misses.length
      ? result.near_misses.map((expert) => `- **${expert.name}**: ${expert.why_not_selected} Use if: ${expert.use_if}`)
      : ['- No strong near-miss route returned.']),
    '',
    '## Intro email',
    `Subject: ${result.intro_pack.subject}`,
    '',
    result.intro_pack.intro_email,
  ].join('\n')
}

function IdleNetworkMap({
  query,
  loading,
  stats,
}: {
  query: string
  loading: boolean
  stats: NetworkStats | null | undefined
}) {
  const roleNodes = (stats?.top_roles?.length ? stats.top_roles : [
    { role: 'Enterprise GTM', count: 4 },
    { role: 'Security / compliance', count: 3 },
    { role: 'Cloud infrastructure', count: 3 },
    { role: 'Legal structuring', count: 2 },
    { role: 'Product / PLG', count: 4 },
    { role: 'Finance / operations', count: 3 },
    { role: 'Healthcare regulatory', count: 2 },
    { role: 'Partnerships', count: 2 },
  ]).slice(0, 8)

  return (
    <section className={`network-map-card idle-map ${loading ? 'routing' : ''}`}>
      <div className="map-heading">
        <div>
          <span className="section-kicker">Expert graph</span>
          <h2>{loading ? 'Routing through The Zone' : 'Network map is waiting for signal'}</h2>
        </div>
        <div className="map-legend">
          <span><i className="legend-dot selected" /> primary path</span>
          <span><i className="legend-dot near" /> backup lane</span>
          <span><i className="legend-dot pool" /> coverage</span>
        </div>
      </div>

      <div className="network-map">
        <svg viewBox="0 0 100 100" className="network-lines" aria-hidden="true">
          <circle cx="50" cy="50" r="18" />
          <circle cx="50" cy="50" r="31" />
          <circle cx="50" cy="50" r="43" />
          {roleNodes.map((role, index) => {
            const pos = graphPositions[index] || graphPositions[0]
            return (
              <line
                key={role.role}
                x1="50"
                y1="50"
                x2={pos.x}
                y2={pos.y}
                className={index < 2 ? 'selected' : index < 5 ? 'near' : 'pool'}
              />
            )
          })}
        </svg>

        <div className="founder-node">
          <span>Founder signal</span>
          <strong>{query.trim() ? 'Request staged' : 'Awaiting request'}</strong>
          <small>{query.trim() ? `${query.trim().split(/\s+/).length} words ready to route` : 'Paste a blocker or use a demo scenario'}</small>
        </div>

        {roleNodes.map((role, index) => {
          const pos = graphPositions[index] || graphPositions[0]
          const state = index < 2 ? 'selected' : index < 5 ? 'near' : 'pool'
          return (
            <article
              className={`expert-node ${state}`}
              key={role.role}
              style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
              title={`${role.role}: ${role.count} modeled profiles`}
            >
              <span>{role.count}</span>
              <strong>{role.role.split(' ')[0]}</strong>
              <small>{role.role}</small>
            </article>
          )
        })}
      </div>
    </section>
  )
}

function App() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<RoutingResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [networkStats, setNetworkStats] = useState<NetworkStats | null>(null)
  const [openSections, setOpenSections] = useState<Record<SectionId, boolean>>(DEFAULT_OPEN)
  const [copied, setCopied] = useState(false)
  const [copiedBrief, setCopiedBrief] = useState(false)
  const [selectedExpert, setSelectedExpert] = useState<Expert | null>(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/health`)
      .then((response) => response.ok ? response.json() : null)
      .then((data) => {
        if (!data) return
        if (isRecord(data) && data.network_stats) {
          setNetworkStats(normalizeNetworkStats(data.network_stats))
        } else if (isRecord(data)) {
          setNetworkStats({
            ...FALLBACK_NETWORK_STATS,
            profiles_loaded: asNumber(data.experts_loaded, FALLBACK_NETWORK_STATS.profiles_loaded),
          })
        }
      })
      .catch(() => setNetworkStats(null))
  }, [])

  const activeStats = result?.network_stats || networkStats

  const queryStats = useMemo(() => {
    const words = query.trim() ? query.trim().split(/\s+/).length : 0
    return { words, chars: query.length, capacity: clamp((query.length / 2400) * 100) }
  }, [query])

  const handleSubmit = async () => {
    if (!query.trim() || loading) return

    setLoading(true)
    setResult(null)
    setError(null)
    setCopied(false)
    setCopiedBrief(false)
    setSelectedExpert(null)
    setOpenSections(DEFAULT_OPEN)

    try {
      const submittedQuery = query.trim()
      const response = await fetch(`${API_BASE}/api/route`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: submittedQuery }),
      })

      const rawText = await response.text()
      let data: unknown = {}
      try {
        data = rawText ? JSON.parse(rawText) : {}
      } catch {
        throw new Error(`Router returned non-JSON response (${response.status}). Restart the Tool 2 backend and try again.`)
      }

      if (!response.ok) {
        const detail = isRecord(data) ? asString(data.detail, 'Routing failed') : 'Routing failed'
        throw new Error(detail)
      }

      setResult(normalizeRoutingResult(data, submittedQuery, activeStats))
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  const toggleSection = (id: SectionId) => {
    setOpenSections((current) => ({ ...current, [id]: !current[id] }))
  }

  const loadSample = (sample: SampleQuery) => {
    setQuery(sample.query)
    setResult(null)
    setError(null)
    setCopied(false)
    setCopiedBrief(false)
    setSelectedExpert(null)
  }

  const copyIntro = async () => {
    if (!result) return
    await navigator.clipboard.writeText(`Subject: ${result.intro_pack.subject}\n\n${result.intro_pack.intro_email}`)
    setCopied(true)
  }

  const copyDispatchBrief = async () => {
    if (!result) return
    await navigator.clipboard.writeText(buildDispatchMarkdown(result))
    setCopiedBrief(true)
  }

  return (
    <div className="zone-shell">
      <div className="zone-grid" />
      <div className="zone-glow zone-glow-a" />
      <div className="zone-glow zone-glow-b" />

      <header className="zone-topbar">
        <div className="zone-brand">
          <div className="zone-brand-mark">Zone</div>
          <div>
            <strong>The Zone Router</strong>
            <span>Expert dispatch command center</span>
          </div>
        </div>
        <div className="zone-status-strip">
          <span>{activeStats?.profiles_loaded || 25} modeled profiles</span>
          <span>{activeStats?.roles_covered || 12} role lanes</span>
          <span>Local-first prototype</span>
        </div>
      </header>

      <main className="zone-command">
        <aside className="signal-console">
          <div className="console-chrome">
            <span>(02)</span>
            <i>operator network intelligence</i>
          </div>

          <div className="console-intro">
            <span className="section-kicker">Founder signal intake</span>
            <h1>Expert routing, not another search box.</h1>
            <p>
              Paste the messy operating blocker. The system turns it into a primary expert,
              backup lane, specialist review, near-miss explanation, and intro-ready dispatch pack.
            </p>
          </div>

          <label className="signal-input-wrap">
            <span>Founder request</span>
            <textarea
              className="signal-input"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Example: We are an Indian AI security startup trying to land our first Fortune 500 pilot. The buyer is asking for SOC2, data residency, and a formal security review..."
              onKeyDown={(event) => {
                if (event.key === 'Enter' && event.metaKey) handleSubmit()
              }}
            />
          </label>

          <div className="signal-footer">
            <div className="signal-meter">
              <strong>{queryStats.words}</strong>
              <span>words</span>
              <div><i style={{ width: `${queryStats.capacity}%` }} /></div>
            </div>
            <button className="dispatch-button" type="button" onClick={handleSubmit} disabled={!query.trim() || loading}>
              <span>{loading ? 'Routing' : 'Build route'}</span>
              <i>↗</i>
            </button>
          </div>

          <div className="scenario-rail">
            <div className="scenario-heading">
              <span className="section-kicker">Demo scenarios</span>
              <small>Load one, then watch the graph reroute.</small>
            </div>
                {FALLBACK_SAMPLES.map((sample, index) => (
              <button className="scenario-card" type="button" onClick={() => loadSample(sample)} key={sample.label}>
                <span>{String(index + 1).padStart(2, '0')}</span>
                <strong>{sample.label}</strong>
                <small>{truncate(sample.query, 92)}</small>
              </button>
            ))}
          </div>
        </aside>

        <section className="graph-console">
          {result ? <ExpertNetworkMap result={result} /> : <IdleNetworkMap query={query} loading={loading} stats={activeStats} />}
        </section>

        <aside className="dispatch-dock">
          <div className="dock-header">
            <span className="section-kicker">Dispatch dock</span>
            <strong>{result ? 'Route compiled' : loading ? 'Routing request' : 'Ready to dispatch'}</strong>
          </div>

          {error && (
            <div className="dock-alert">
              <strong>Routing failed</strong>
              <p>{error}</p>
            </div>
          )}

          {!result && !error && (
            <>
              <div className="dock-claim">
                <span>Why this is not keyword search</span>
                <p>
                  It scores role fit, stage fit, urgency, availability, corridor relevance,
                  advisory history, and weak-but-serious near misses.
                </p>
              </div>
              <div className={`dock-pipeline ${loading ? 'active' : ''}`}>
                {processingSteps.map((step, index) => (
                  <div key={step}>
                    <span>{String(index + 1).padStart(2, '0')}</span>
                    <strong>{step}</strong>
                  </div>
                ))}
              </div>
              <div className="dock-note">
                <strong>Modeled from The Zone</strong>
                <p>{activeStats?.demo_slice_note || 'Synthetic demo slice; production can connect to the live expert CRM.'}</p>
              </div>
            </>
          )}

          {result && (
            <>
              <div className="dock-decision">
                <small>Recommended first move</small>
                <strong>{result.dispatch_plan.decision}</strong>
                <p>{result.dispatch_plan.why_now}</p>
              </div>
              <div className="dock-score">
                <span>{result.dispatch_plan.confidence}%</span>
                <small>route confidence</small>
              </div>
              <div className="dock-sequence">
                {result.dispatch_plan.sequence.map((step) => (
                  <article key={`${step.step}-${step.expert}`}>
                    <span>{String(step.step).padStart(2, '0')}</span>
                    <div>
                      <strong>{step.expert}</strong>
                      <small>{step.label} · {step.role}</small>
                    </div>
                  </article>
                ))}
              </div>
            </>
          )}
        </aside>
      </main>

      <section className={`detail-deck ${result ? 'with-result' : 'empty-state'}`}>
        {!result && (
          <>
            <article>
              <span>01</span>
              <strong>Graph-first routing</strong>
              <p>The homepage starts with the network map so the reviewer sees expert relationships immediately.</p>
            </article>
            <article>
              <span>02</span>
              <strong>Selection and rejection logic</strong>
              <p>Selected experts and near misses appear together, making the decision auditable instead of magical.</p>
            </article>
            <article>
              <span>03</span>
              <strong>Actionable dispatch pack</strong>
              <p>The output includes first-call sequence, backup expert, intro copy, and coverage gaps.</p>
            </article>
          </>
        )}

        {result && (
          <div className="result-stack">
            <section className="dispatch-brief">
              <div className="brief-top">
                <div>
                  <span className="section-kicker">Routing brief</span>
                  <h2>{result.dispatch_plan.decision}</h2>
                  <p>{result.dispatch_plan.routing_strategy || result.dispatch_plan.why_now}</p>
                </div>
                <div className="confidence-orb">
                  <span>{result.dispatch_plan.confidence}%</span>
                  <small>confidence</small>
                </div>
              </div>
              <div className="brief-grid">
                <div>
                  <span>Primary route</span>
                  <strong>{result.dispatch_plan.primary_expert}</strong>
                  <small>{result.dispatch_plan.primary_role}</small>
                </div>
                <div>
                  <span>Urgency</span>
                  <strong>{normalizeLabel(result.dispatch_plan.urgency)}</strong>
                  <small>{normalizeLabel(result.dispatch_plan.stage)} stage</small>
                </div>
                <div>
                  <span>Candidate pool</span>
                  <strong>{result.candidate_pool.length}</strong>
                  <small>ranked profiles shown</small>
                </div>
              </div>
              <div className="dispatch-actions">
                <button type="button" onClick={copyDispatchBrief}>{copiedBrief ? 'Dispatch brief copied' : 'Copy dispatch brief'}</button>
                <span>Markdown export for Slack, email, or internal notes.</span>
              </div>
            </section>

            <section className="route-sequence">
              <div className="section-heading">
                <span className="section-kicker">Route strategy</span>
                <h3>First call, backup, specialist review</h3>
              </div>
              <div className="sequence-grid">
                {result.dispatch_plan.sequence.map((step) => (
                  <article className="sequence-card" key={`${step.step}-${step.expert}`}>
                    <span>{String(step.step).padStart(2, '0')}</span>
                    <strong>{step.label}</strong>
                    <h4>{step.expert}</h4>
                    <p>{step.objective}</p>
                    <small>{step.role} · {step.timebox}</small>
                  </article>
                ))}
              </div>
            </section>

            <CollapsibleSection
              id="intent"
              kicker="Need extraction"
              title="What the founder is really asking"
              preview={`${result.intent.inferred_need_type || 'Operator support'} · ${result.intent.specific_skills?.slice(0, 3).join(', ') || 'skills extracted'}`}
              open={openSections.intent}
              onToggle={toggleSection}
            >
              <div className="intent-grid">
                <div className="intent-card wide">
                  <span>Context summary</span>
                  <p>{result.intent.context_summary}</p>
                </div>
                <div className="intent-card">
                  <span>Domains</span>
                  <div className="tag-list">{result.intent.primary_domains?.map((item) => <i key={item}>{item}</i>)}</div>
                </div>
                <div className="intent-card">
                  <span>Specific skills</span>
                  <div className="tag-list">{result.intent.specific_skills?.map((item) => <i key={item}>{item}</i>)}</div>
                </div>
                {(result.intent.hidden_risks || []).length > 0 && (
                  <div className="intent-card wide">
                    <span>Hidden risks</span>
                    <ul>{result.intent.hidden_risks?.map((risk) => <li key={risk}>{risk}</li>)}</ul>
                  </div>
                )}
              </div>
            </CollapsibleSection>

            <CollapsibleSection
              id="experts"
              kicker="Ranked expert pool"
              title="Selected route plus backup bench"
              preview={result.candidate_pool.slice(0, 6).map((expert) => `${expert.name}: ${expert.match_score}/100`).join(' · ')}
              open={openSections.experts}
              onToggle={toggleSection}
            >
              <div className="expert-card-grid">
                {result.candidate_pool.slice(0, 6).map((expert) => {
                  const rec = result.rationale.recommendations.find((item) => item.name === expert.name)
                  const selected = result.top_experts.some((item) => item.id === expert.id || item.name === expert.name)
                  return (
                    <article className={`expert-card ${selected ? 'selected-route' : 'bench-route'}`} key={expert.id}>
                      <div className="expert-card-top">
                        <span>{selected ? expert.fit_label : `Rank ${expert.rank}`}</span>
                        <strong>{expert.match_score}</strong>
                      </div>
                      <h4>{expert.name}</h4>
                      <p className="expert-title">{expert.title}</p>
                      <p>{expert.bio}</p>
                      <div className="tag-list compact">
                        {expert.match_reasons.map((reason) => <i key={reason}>{reason}</i>)}
                      </div>
                      <div className="score-bars">
                        <ScoreBar label="Skill" value={expert.score_breakdown.skill_match} />
                        <ScoreBar label="Domain" value={expert.score_breakdown.domain_match} max={24} />
                        <ScoreBar label="Role" value={expert.score_breakdown.role_fit} max={16} />
                        <ScoreBar label="Advisory" value={expert.score_breakdown.advisory_relevance} max={10} />
                      </div>
                      {rec && (
                        <div className="rationale-box">
                          <span>Opening angle</span>
                          <p>{rec.conversation_starter}</p>
                        </div>
                      )}
                      <div className="selection-note">
                        <span>{selected ? 'Why selected' : 'Why not first choice'}</span>
                        <p>{expertRouteNote(expert, result)}</p>
                      </div>
                      <button className="profile-button" type="button" onClick={() => setSelectedExpert(expert)}>
                        Open expert profile
                      </button>
                    </article>
                  )
                })}
              </div>
            </CollapsibleSection>

            <CollapsibleSection
              id="nearMisses"
              kicker="Calibration"
              title="Why not these experts"
              preview={`${result.near_misses.length} near misses shown so the route is auditable`}
              open={openSections.nearMisses}
              onToggle={toggleSection}
            >
              <div className="near-miss-grid">
                {result.near_misses.map((expert) => (
                  <article className="near-miss-card" key={expert.name}>
                    <div>
                      <span>{expert.match_score}/100</span>
                      <h4>{expert.name}</h4>
                      <small>{expert.title}</small>
                    </div>
                    <p>{expert.why_not_selected}</p>
                    <strong>{expert.use_if}</strong>
                  </article>
                ))}
              </div>
            </CollapsibleSection>

            <CollapsibleSection
              id="intro"
              kicker="Outreach pack"
              title="Generated intro and prep plan"
              preview={result.intro_pack.subject}
              open={openSections.intro}
              onToggle={toggleSection}
            >
              <div className="intro-grid">
                <div className="intro-email">
                  <div className="intro-email-top">
                    <span>{result.intro_pack.subject}</span>
                    <button type="button" onClick={copyIntro}>{copied ? 'Copied' : 'Copy intro'}</button>
                  </div>
                  <pre>{result.intro_pack.intro_email}</pre>
                </div>
                <div className="prep-pack">
                  <span>Prep questions</span>
                  <ol>{result.intro_pack.prep_questions.map((item) => <li key={item}>{item}</li>)}</ol>
                  <span>Success criteria</span>
                  <ul>{result.intro_pack.success_criteria.map((item) => <li key={item}>{item}</li>)}</ul>
                </div>
              </div>
            </CollapsibleSection>

            <CollapsibleSection
              id="coverage"
              kicker="Network coverage"
              title="Coverage gaps and recruiting signal"
              preview={result.coverage_gaps.length ? `${result.coverage_gaps.length} gap signals found` : 'No critical coverage gap detected for this request'}
              open={openSections.coverage}
              onToggle={toggleSection}
            >
              {result.coverage_gaps.length > 0 ? (
                <div className="coverage-grid">
                  {result.coverage_gaps.map((gap) => (
                    <article className={`coverage-card ${gap.severity}`} key={`${gap.role}-${gap.reason}`}>
                      <span>{gap.severity}</span>
                      <h4>{gap.role}</h4>
                      <p>{gap.reason}</p>
                      <strong>{gap.recruiting_signal}</strong>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="clear-card">
                  <strong>No critical coverage gap detected.</strong>
                  <p>The modeled network slice contains a credible primary route and backup route for this founder request.</p>
                </div>
              )}
            </CollapsibleSection>

            <CollapsibleSection
              id="reasoning"
              kicker="Visible reasoning"
              title="Auditable execution trace"
              preview={`${result.reasoning_log.length} steps · retrieval, scoring, near-miss calibration, dispatch compilation`}
              open={openSections.reasoning}
              onToggle={toggleSection}
            >
              <div className="timeline">
                {result.reasoning_log.map((step) => (
                  <article className="timeline-step" key={`${step.step_number}-${step.title}`}>
                    <span>{String(step.step_number).padStart(2, '0')}</span>
                    <div>
                      <div className="timeline-top">
                        <strong>{step.title}</strong>
                        <small>{step.step_type}{step.duration_ms ? ` · ${step.duration_ms}ms` : ''}</small>
                      </div>
                      <p>{step.description}</p>
                      {step.input_data && <pre>{step.input_data}</pre>}
                      {step.output_data && <pre>{step.output_data}</pre>}
                    </div>
                  </article>
                ))}
              </div>
            </CollapsibleSection>
          </div>
        )}
      </section>

      {selectedExpert && result && (
        <div className="profile-modal-backdrop" role="presentation" onClick={() => setSelectedExpert(null)}>
          <section className="profile-modal" role="dialog" aria-modal="true" aria-label={`${selectedExpert.name} profile`} onClick={(event) => event.stopPropagation()}>
            <button className="profile-close" type="button" onClick={() => setSelectedExpert(null)}>Close</button>
            <div className="profile-modal-top">
              <div>
                <span className="section-kicker">Expert profile</span>
                <h2>{selectedExpert.name}</h2>
                <p>{selectedExpert.title}</p>
              </div>
              <div className="profile-score">
                <strong>{selectedExpert.match_score}</strong>
                <span>/100 match</span>
              </div>
            </div>
            <p className="profile-bio">{selectedExpert.bio}</p>
            <div className="profile-meta-grid">
              <div><span>Location</span><strong>{selectedExpert.location}</strong></div>
              <div><span>Availability</span><strong>{normalizeLabel(selectedExpert.availability)}</strong></div>
              <div><span>Route role</span><strong>{selectedExpert.routing_role}</strong></div>
            </div>
            <div className="profile-section-grid">
              <div>
                <span>Domains</span>
                <div className="tag-list">{selectedExpert.domains.map((item) => <i key={item}>{item}</i>)}</div>
              </div>
              <div>
                <span>Expertise</span>
                <div className="tag-list">{selectedExpert.expertise_tags.map((item) => <i key={item}>{item}</i>)}</div>
              </div>
            </div>
            <div className="profile-advisory">
              <span>Past advisory context</span>
              <ul>{selectedExpert.past_advisory.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
            <div className="selection-note modal-note">
              <span>Route calibration</span>
              <p>{expertRouteNote(selectedExpert, result)}</p>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}

export default App
