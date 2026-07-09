import { useEffect, useRef, useState } from 'react'
import './App.css'

const API_BASE = 'http://localhost:8002'

type Difficulty = 'friendly' | 'skeptical' | 'hostile_procurement'
type SpeechRecognitionInstance = {
  continuous: boolean
  interimResults: boolean
  lang: string
  onresult: ((event: { results: ArrayLike<{ 0: { transcript: string } }> }) => void) | null
  onend: (() => void) | null
  onerror: (() => void) | null
  start: () => void
  stop: () => void
}
type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance

interface Persona {
  id: string
  name: string
  title: string
  company_type: string
  personality: string
  priorities: string[]
  deal_stage?: string
  risk_tolerance?: string
  procurement_power?: string
  compliance_sensitivity?: string
  budget_authority?: string
  hidden_objection?: string
  success_condition?: string
}

interface Message {
  role: 'buyer' | 'founder'
  content: string
  internal_strategy?: string
  turn?: number
}

interface ReasoningStep {
  step_number: number
  title: string
  description: string
  output_data?: string
  step_type: string
}

interface DealHealth {
  buyer_trust: number
  compliance_risk: number
  budget_confidence: number
  urgency: number
  procurement_friction: number
}

interface StageInfo {
  id: string
  label: string
  description: string
}

interface ObjectionItem {
  id: string
  label: string
  description: string
  status: 'unopened' | 'active' | 'handled' | 'watch'
  severity: number
  latest_signal?: string
}

interface BattleReplayItem {
  turn: number
  stage: string
  stage_label: string
  founder_message: string
  buyer_response: string
  score?: number | null
  label?: string
  what_worked?: string
  missed_moment?: string
  better_response?: string
  next_best_move?: string
  internal_strategy?: string
}

interface CoachingReport {
  overall_score: number
  score_label: string
  summary: string
  board_summary?: string
  deal_health_summary?: string
  strongest_moment?: { quote: string; why_it_worked: string }
  weakest_moment?: { quote: string; why_it_hurt: string }
  strengths: { title: string; detail: string; impact: string }[]
  weaknesses: { title: string; detail: string; missed_opportunity: string }[]
  coaching_tips: { tip: string; practice: string }[]
  objection_handling_breakdown: { objection: string; founder_response: string; rating: string; better_response: string }[]
  next_call_plan?: string[]
  recommended_founder_script?: string
  readiness_assessment: string
  reasoning_log: ReasoningStep[]
}

interface DealStatePayload {
  stage?: string
  stage_label?: string
  stages?: StageInfo[]
  deal_health?: DealHealth
  objection_stack?: ObjectionItem[]
  battle_replay?: BattleReplayItem[]
  latest_strategy?: string
  latest_evaluation_status?: string
  reasoning_steps?: ReasoningStep[]
}

const DEFAULT_HEALTH: DealHealth = {
  buyer_trust: 48,
  compliance_risk: 58,
  budget_confidence: 46,
  urgency: 42,
  procurement_friction: 60,
}

const DEFAULT_STAGES: StageInfo[] = [
  { id: 'discovery', label: 'Discovery', description: 'Business problem and buying context.' },
  { id: 'technical_validation', label: 'Technical validation', description: 'Architecture, evidence, integration, reliability.' },
  { id: 'security_review', label: 'Security review', description: 'Data handling, controls, and compliance.' },
  { id: 'procurement', label: 'Procurement', description: 'Legal, approval path, onboarding, stakeholders.' },
  { id: 'pricing_negotiation', label: 'Pricing negotiation', description: 'ROI, budget, and commercial fit.' },
  { id: 'next_step_close', label: 'Next-step close', description: 'Clear next action or no-deal.' },
]

const DEMO_CONTEXTS = [
  {
    title: 'AI security platform',
    text: 'We are an Indian AI security startup selling to US enterprises. Our platform analyzes cloud and endpoint telemetry to detect novel attacks, uses a mix of custom models and LLM-assisted investigation summaries, and is currently live with 4 mid-market customers. We are trying to land our first Fortune 500 pilot, but the buyer is asking about SOC2, data residency, model provider risk, and whether our team can support a strict enterprise rollout.',
  },
  {
    title: 'Healthcare workflow AI',
    text: 'We are building an AI copilot for hospital operations teams. It predicts staffing bottlenecks, summarizes operational incidents, and integrates with Epic exports through a secure data connector. We have strong early pilots in India and one paid US clinic design partner, but a regional hospital network is pushing us on HIPAA, clinical validation, liability, and workflow adoption by nursing staff.',
  },
  {
    title: 'Developer infrastructure tool',
    text: 'We are building an AI observability layer for engineering teams that diagnoses production incidents from logs, traces, alerts, and deployment history. We have strong technical adoption in startups, but a Series D SaaS company is concerned about integration effort, P99 latency, API reliability, pricing at scale, and whether our agent can safely access production systems.',
  },
]

const difficultyOptions: { id: Difficulty; label: string; description: string }[] = [
  { id: 'skeptical', label: 'Skeptical buyer', description: 'Realistic senior enterprise pressure.' },
  { id: 'friendly', label: 'Friendly buyer', description: 'Constructive but still rigorous.' },
  { id: 'hostile_procurement', label: 'Hostile procurement', description: 'Hard-mode legal, compliance, and budget pushback.' },
]

const healthMetrics: { key: keyof DealHealth; label: string; intent: 'good' | 'risk' }[] = [
  { key: 'buyer_trust', label: 'Buyer trust', intent: 'good' },
  { key: 'compliance_risk', label: 'Compliance risk', intent: 'risk' },
  { key: 'budget_confidence', label: 'Budget confidence', intent: 'good' },
  { key: 'urgency', label: 'Urgency', intent: 'good' },
  { key: 'procurement_friction', label: 'Procurement friction', intent: 'risk' },
]

const responseShortcuts = [
  {
    label: 'Risky vague answer',
    text: 'We can meet all the standard enterprise requirements and have all the certifications you need. Our AI platform is very secure, and we are confident your team will be comfortable once they review it.',
  },
  {
    label: 'Enterprise-grade answer',
    text: 'I would separate production procurement from a controlled evaluation. Today, we can support a narrow pilot with non-sensitive or synthetic data, a documented data-flow boundary, SOC2 evidence, named subprocessors, deletion terms, and a written path for your security/procurement team. If that is viable, I can send a one-page control matrix and pilot boundary by Friday.',
  },
  {
    label: 'Next-step close',
    text: 'The right next step is not a broad rollout decision yet. I suggest a 30-minute security and procurement fit check with your risk owner, where we confirm data boundary, approval path, required evidence, and the smallest safe pilot scope. If we fail that checklist, we should pause rather than waste your team’s time.',
  },
]

function scoreTone(score?: number | null) {
  if (score === null || score === undefined) return 'neutral'
  if (score >= 8) return 'strong'
  if (score >= 5) return 'watch'
  return 'risk'
}

function statusLabel(status: ObjectionItem['status']) {
  if (status === 'active') return 'Active'
  if (status === 'handled') return 'Handled'
  if (status === 'watch') return 'Watch'
  return 'Unopened'
}

function extractJsonishStringField(raw: string, fieldName: string) {
  const marker = `"${fieldName}"`
  const start = raw.indexOf(marker)
  if (start === -1) return ''
  const colon = raw.indexOf(':', start + marker.length)
  if (colon === -1) return ''
  const quote = raw.indexOf('"', colon + 1)
  if (quote === -1) return ''

  let value = ''
  let escaped = false
  for (const char of raw.slice(quote + 1)) {
    if (escaped) {
      const escapes: Record<string, string> = {
        '"': '"',
        '\\': '\\',
        '/': '/',
        b: '\b',
        f: '\f',
        n: '\n',
        r: '\r',
        t: '\t',
      }
      value += escapes[char] ?? char
      escaped = false
      continue
    }
    if (char === '\\') {
      escaped = true
      continue
    }
    if (char === '"') break
    value += char
  }
  return value.trim()
}

function displayMessageContent(content: string) {
  const trimmed = content.trim()
  if (!trimmed.includes('"buyer_response"')) return content
  const buyerResponse = extractJsonishStringField(trimmed, 'buyer_response')
  if (buyerResponse) return buyerResponse
  return 'I want to keep this practical: give me the specific evidence, the risk boundary, and the next step you can commit to.'
}

function evaluationStatusLabel(status: string) {
  const normalized = status.toLowerCase()
  if (normalized.includes('unparsed') || normalized.includes('recovered') || normalized.includes('scorecard')) {
    return 'response recovered'
  }
  if (normalized === 'scored') return 'scored'
  if (normalized === 'ready') return 'ready'
  return 'updated'
}

function App() {
  const [personas, setPersonas] = useState<Persona[]>([])
  const [selectedPersona, setSelectedPersona] = useState<string>('')
  const [productContext, setProductContext] = useState('')
  const [difficulty, setDifficulty] = useState<Difficulty>('skeptical')
  const [meetingObjective, setMeetingObjective] = useState('Earn a credible next-step commitment from the buyer.')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [isComplete, setIsComplete] = useState(false)
  const [reasoningSteps, setReasoningSteps] = useState<ReasoningStep[]>([])
  const [coaching, setCoaching] = useState<CoachingReport | null>(null)
  const [coachingLoading, setCoachingLoading] = useState(false)
  const [copiedReport, setCopiedReport] = useState(false)
  const [personaInfo, setPersonaInfo] = useState<Persona | null>(null)
  const [dealHealth, setDealHealth] = useState<DealHealth>(DEFAULT_HEALTH)
  const [stages, setStages] = useState<StageInfo[]>(DEFAULT_STAGES)
  const [stage, setStage] = useState('discovery')
  const [stageLabel, setStageLabel] = useState('Discovery')
  const [objectionStack, setObjectionStack] = useState<ObjectionItem[]>([])
  const [battleReplay, setBattleReplay] = useState<BattleReplayItem[]>([])
  const [latestStrategy, setLatestStrategy] = useState('')
  const [latestEvaluationStatus, setLatestEvaluationStatus] = useState('ready')
  const [listening, setListening] = useState(false)
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null)

  const selectedPersonaInfo = personas.find(p => p.id === selectedPersona) || null
  const latestReplay = battleReplay.at(-1)
  const founderTurns = messages.filter(m => m.role === 'founder').length
  const latestBuyerMessage = displayMessageContent([...messages].reverse().find(m => m.role === 'buyer')?.content || '')
  const recoveredStructuredOutput = evaluationStatusLabel(latestEvaluationStatus) === 'response recovered'

  useEffect(() => {
    fetch(`${API_BASE}/api/personas`)
      .then(r => r.json())
      .then(d => {
        const loadedPersonas = d.personas || []
        setPersonas(loadedPersonas)
        if (loadedPersonas[0]) setSelectedPersona(prev => prev || loadedPersonas[0].id)
      })
      .catch(() => {})
  }, [])

  const updateDealState = (payload: DealStatePayload) => {
    if (payload.deal_health) setDealHealth(payload.deal_health)
    if (payload.stages?.length) setStages(payload.stages)
    if (payload.stage) setStage(payload.stage)
    if (payload.stage_label) setStageLabel(payload.stage_label)
    if (payload.objection_stack) setObjectionStack(payload.objection_stack)
    if (payload.battle_replay) setBattleReplay(payload.battle_replay)
    if (payload.latest_strategy !== undefined) setLatestStrategy(payload.latest_strategy)
    if (payload.latest_evaluation_status) setLatestEvaluationStatus(payload.latest_evaluation_status)
    if (payload.reasoning_steps) setReasoningSteps(payload.reasoning_steps)
  }

  const resetSession = () => {
    window.speechSynthesis?.cancel()
    recognitionRef.current?.stop()
    setSessionId(null)
    setMessages([])
    setInput('')
    setLoading(false)
    setIsComplete(false)
    setReasoningSteps([])
    setCoaching(null)
    setCopiedReport(false)
    setPersonaInfo(null)
    setDealHealth(DEFAULT_HEALTH)
    setStages(DEFAULT_STAGES)
    setStage('discovery')
    setStageLabel('Discovery')
    setObjectionStack([])
    setBattleReplay([])
    setLatestStrategy('')
    setLatestEvaluationStatus('ready')
    setListening(false)
    window.setTimeout(() => window.scrollTo({ top: 0, behavior: 'auto' }), 0)
  }

  const readBuyerAloud = () => {
    if (!latestBuyerMessage || !('speechSynthesis' in window)) return
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(latestBuyerMessage)
    utterance.rate = 0.92
    utterance.pitch = 0.92
    utterance.volume = 0.9
    window.speechSynthesis.speak(utterance)
  }

  const dictateAnswer = () => {
    const speechWindow = window as Window & {
      SpeechRecognition?: SpeechRecognitionConstructor
      webkitSpeechRecognition?: SpeechRecognitionConstructor
    }
    const Recognition = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition
    if (!Recognition) {
      alert('Dictation is not available in this browser. The typed simulation still works.')
      return
    }
    if (listening && recognitionRef.current) {
      recognitionRef.current.stop()
      setListening(false)
      return
    }
    const recognition = new Recognition()
    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = 'en-US'
    recognition.onresult = event => {
      const transcript = Array.from(event.results)
        .map(result => result[0]?.transcript || '')
        .join(' ')
        .trim()
      if (transcript) {
        setInput(prev => `${prev}${prev ? ' ' : ''}${transcript}`)
      }
    }
    recognition.onend = () => setListening(false)
    recognition.onerror = () => setListening(false)
    recognitionRef.current = recognition
    setListening(true)
    recognition.start()
  }

  const startSession = async () => {
    if (!selectedPersona || !productContext.trim()) return
    setLoading(true)
    setCoaching(null)
    setCopiedReport(false)
    try {
      const res = await fetch(`${API_BASE}/api/session/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          persona_id: selectedPersona,
          product_context: productContext,
          difficulty,
          meeting_objective: meetingObjective,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail)
      setSessionId(data.session_id)
      setMessages([{ role: 'buyer', content: data.opening.content, turn: 1 }])
      setIsComplete(false)
      setPersonaInfo(personas.find(p => p.id === selectedPersona) || null)
      updateDealState(data.opening)
      window.setTimeout(() => window.scrollTo({ top: 0, behavior: 'auto' }), 0)
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Failed to start simulation')
    } finally {
      setLoading(false)
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || !sessionId || loading) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'founder', content: userMsg }])
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/session/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: userMsg }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail)
      setMessages(prev => [...prev, {
        role: 'buyer',
        content: data.content,
        internal_strategy: data.internal_strategy,
        turn: data.turn,
      }])
      updateDealState(data)
      if (data.is_complete) setIsComplete(true)
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Response generation failed')
    } finally {
      setLoading(false)
    }
  }

  const requestCoaching = async () => {
    if (!sessionId) return
    setCoachingLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/session/coach`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail)
      setCoaching(data)
      if (data.reasoning_log) setReasoningSteps(data.reasoning_log)
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Coaching analysis failed')
    } finally {
      setCoachingLoading(false)
    }
  }

  const buildBoardReport = () => {
    if (!coaching) return ''
    const persona = personaInfo?.name || 'Buyer'
    const strengths = coaching.strengths?.map(s => `- ${s.title}: ${s.detail}`).join('\n') || ''
    const weaknesses = coaching.weaknesses?.map(w => `- ${w.title}: ${w.detail}`).join('\n') || ''
    const plan = coaching.next_call_plan?.map(item => `- ${item}`).join('\n') || ''
    return `# Enterprise Objection Simulation Report

Buyer: ${persona} — ${personaInfo?.title || ''}
Difficulty: ${difficultyOptions.find(d => d.id === difficulty)?.label || difficulty}
Score: ${coaching.overall_score}/10 — ${coaching.score_label}

## Partner Summary
${coaching.board_summary || coaching.summary}

## Deal Health
${coaching.deal_health_summary || 'No deal-health summary returned.'}

## Strengths
${strengths}

## Risks / Missed Moments
${weaknesses}

## Next Call Plan
${plan}

## Recommended Founder Script
${coaching.recommended_founder_script || ''}

## Readiness
${coaching.readiness_assessment}
`
  }

  const copyBoardReport = async () => {
    const report = buildBoardReport()
    if (!report) return
    await navigator.clipboard.writeText(report)
    setCopiedReport(true)
    window.setTimeout(() => setCopiedReport(false), 1800)
  }

  if (!sessionId) {
    return (
      <div className="app surface-light">
        <header className="topbar">
          <div className="brand-lockup">
            <div className="brand-mark">TF</div>
            <div>
              <div className="brand-title">Enterprise Objection Simulator</div>
              <div className="brand-subtitle">Deal-room training for portfolio founders</div>
            </div>
          </div>
          <div className="topbar-pills">
            <span>Role-play engine</span>
            <span>Board-ready coaching</span>
          </div>
        </header>

        <main className="setup-workspace">
          <section className="setup-intro panel">
            <div className="eyebrow">Tool 03 / Enterprise sales readiness</div>
            <h1>Practice the call before the call costs momentum.</h1>
            <p>
              Simulate a senior enterprise buyer, expose the hidden objection stack, and leave with a coaching report a partner could use with the founder.
            </p>
            <div className="intro-metrics">
              <div>
                <strong>6</strong>
                <span>deal stages</span>
              </div>
              <div>
                <strong>5</strong>
                <span>live health signals</span>
              </div>
              <div>
                <strong>7</strong>
                <span>objection lanes</span>
              </div>
            </div>
          </section>

          <section className="setup-form panel">
            <div className="section-heading">
              <span>Deal brief</span>
              <small>What the buyer should know before entering the room</small>
            </div>

            <label className="field-label" htmlFor="objective">Meeting objective</label>
            <input
              id="objective"
              className="text-input"
              value={meetingObjective}
              onChange={e => setMeetingObjective(e.target.value)}
            />

            <label className="field-label" htmlFor="context">Founder context</label>
            <textarea
              id="context"
              className="product-textarea"
              value={productContext}
              onChange={e => setProductContext(e.target.value)}
              placeholder="Describe the product, customer, stage, market, current blocker, and what the founder needs from this meeting."
            />

            <div className="scenario-row">
              {DEMO_CONTEXTS.map(scenario => (
                <button key={scenario.title} className="ghost-chip" onClick={() => setProductContext(scenario.text)}>
                  {scenario.title}
                </button>
              ))}
            </div>
          </section>

          <section className="persona-section panel">
            <div className="section-heading">
              <span>Buyer persona</span>
              <small>Select the stakeholder the founder needs to survive</small>
            </div>
            <div className="persona-grid">
              {personas.map(p => (
                <button
                  key={p.id}
                  aria-label={`Select ${p.name}, ${p.title}`}
                  className={`persona-card ${selectedPersona === p.id ? 'selected' : ''}`}
                  onClick={() => setSelectedPersona(p.id)}
                >
                  <div className="persona-topline">
                    <span>{p.name}</span>
                    <small>{p.risk_tolerance || 'Medium'} risk</small>
                  </div>
                  <strong>{p.title}</strong>
                  <p>{p.company_type}</p>
                  <div className="persona-meta">
                    <span>{p.deal_stage}</span>
                    <span>{p.compliance_sensitivity} compliance</span>
                  </div>
                </button>
              ))}
            </div>

            {selectedPersonaInfo && (
              <div className="persona-intel">
                <div>
                  <span>Procurement power</span>
                  <strong>{selectedPersonaInfo.procurement_power}</strong>
                </div>
                <div>
                  <span>Hidden objection</span>
                  <strong>{selectedPersonaInfo.hidden_objection}</strong>
                </div>
                <div>
                  <span>Success condition</span>
                  <strong>{selectedPersonaInfo.success_condition}</strong>
                </div>
              </div>
            )}
          </section>

          <section className="difficulty-section panel">
            <div className="section-heading">
              <span>Simulation pressure</span>
              <small>Choose how hard the room should push back</small>
            </div>
            <div className="difficulty-grid">
              {difficultyOptions.map(option => (
                <button
                  key={option.id}
                  aria-label={`Select ${option.label}`}
                  className={`difficulty-card ${difficulty === option.id ? 'selected' : ''}`}
                  onClick={() => setDifficulty(option.id)}
                >
                  <strong>{option.label}</strong>
                  <span>{option.description}</span>
                </button>
              ))}
            </div>
            <button
              className="primary-action"
              onClick={startSession}
              disabled={!selectedPersona || !productContext.trim() || loading}
            >
              {loading ? <><span className="spinner" /> Preparing deal room</> : 'Begin simulation'}
            </button>
          </section>
        </main>
      </div>
    )
  }

  return (
    <div className="app surface-light simulation-app">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark">TF</div>
          <div>
            <div className="brand-title">Enterprise Objection Simulator</div>
            <div className="brand-subtitle">{personaInfo?.name} / {stageLabel}</div>
          </div>
        </div>
        <div className="topbar-pills">
          <span>{isComplete ? 'Simulation complete' : 'Live simulation'}</span>
          <span>{difficultyOptions.find(d => d.id === difficulty)?.label}</span>
          <button className="topbar-action" onClick={resetSession}>Back to setup</button>
        </div>
      </header>

      <main className="deal-room">
        <aside className="deal-brief panel review-panel">
          <div className="eyebrow">Deal brief</div>
          <h2>{personaInfo?.name}</h2>
          <p className="muted">{personaInfo?.title}</p>
          <p className="company-line">{personaInfo?.company_type}</p>
          <button className="inline-reset" onClick={resetSession}>Change scenario or buyer</button>

          <div className="brief-card">
            <span>Meeting objective</span>
            <strong>{meetingObjective}</strong>
          </div>

          <div className="brief-card">
            <span>Hidden buyer pressure</span>
            <strong>{personaInfo?.hidden_objection}</strong>
          </div>

          <div className="brief-card">
            <span>Success condition</span>
            <strong>{personaInfo?.success_condition}</strong>
          </div>

          <div className="stage-rail">
            {stages.map((item, index) => (
              <div key={item.id} className={`stage-item ${item.id === stage ? 'active' : ''}`}>
                <span>{String(index + 1).padStart(2, '0')}</span>
                <div>
                  <strong>{item.label}</strong>
                  <small>{item.description}</small>
                </div>
              </div>
            ))}
          </div>
        </aside>

        <section className="live-call panel review-panel">
          <div className="call-header">
            <div>
              <div className="eyebrow">Live simulation</div>
              <h1>{stageLabel}</h1>
            </div>
            <div className={`score-token ${scoreTone(latestReplay?.score)}`}>
              <span>Last answer</span>
              <strong>{latestReplay?.score ? `${latestReplay.score}/10` : 'Waiting'}</strong>
            </div>
          </div>

          <div className="transcript">
            {messages.map((msg, i) => (
              <div key={`${msg.role}-${i}`} className={`turn ${msg.role}`}>
                <div className="turn-label">{msg.role === 'buyer' ? personaInfo?.name : 'Founder'}</div>
                <div className="turn-bubble">{displayMessageContent(msg.content)}</div>
              </div>
            ))}
            {loading && (
              <div className="turn buyer">
                <div className="turn-label">{personaInfo?.name}</div>
                <div className="turn-bubble thinking">
                  <span className="spinner" />
                  Updating buyer stance, deal health, and objection stack
                </div>
              </div>
            )}
          </div>

          {latestReplay && (
            <div className="replay-card">
              <div className="section-heading compact">
                <span>Latest coaching lens</span>
                <small>{latestReplay.stage_label}</small>
              </div>
              <div className="replay-grid">
                <div>
                  <span>What worked</span>
                  <p>
                    {recoveredStructuredOutput && latestReplay.what_worked?.toLowerCase().includes('model returned')
                      ? 'The spoken buyer response was recovered cleanly, but the structured scorecard for this turn was incomplete.'
                      : latestReplay.what_worked || 'Continue the call; this turn has not produced a full scorecard yet.'}
                  </p>
                </div>
                <div>
                  <span>Missed moment</span>
                  <p>
                    {recoveredStructuredOutput && latestReplay.missed_moment?.toLowerCase().includes('review the transcript')
                      ? 'Use the buyer follow-up as the signal: answer with concrete evidence, name the risk boundary, and ask for a specific next step.'
                      : latestReplay.missed_moment || 'No missed moment returned yet.'}
                  </p>
                </div>
              </div>
              {latestReplay.better_response && (
                <div className="better-response">
                  <span>Sharper answer to practice</span>
                  <p>
                    {recoveredStructuredOutput && latestReplay.better_response.toLowerCase().includes('re-run')
                      ? 'Let me be specific: here is the exact control evidence we have today, the pilot boundary we can support safely, and the person/date we need from your side to validate the next step.'
                      : latestReplay.better_response}
                  </p>
                </div>
              )}
            </div>
          )}

          <div className="composer">
            {!isComplete ? (
              <>
                <textarea
                  className="response-input"
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => {
                    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                      e.preventDefault()
                      sendMessage()
                    }
                  }}
                  placeholder="Write the founder response. Use evidence, name the risk, and ask for a concrete next step."
                  disabled={loading}
                />
                <div className="call-tools">
                  <span>Call mode</span>
                  <button onClick={readBuyerAloud} disabled={!latestBuyerMessage}>Read buyer aloud</button>
                  <button onClick={dictateAnswer}>{listening ? 'Stop dictation' : 'Dictate answer'}</button>
                </div>
                <div className="shortcut-row">
                  <span>Demo accelerators</span>
                  {responseShortcuts.map(shortcut => (
                    <button key={shortcut.label} className="shortcut-chip" onClick={() => setInput(shortcut.text)}>
                      {shortcut.label}
                    </button>
                  ))}
                </div>
                <div className="composer-actions">
                  <span>{founderTurns} founder turns / Command+Enter to send</span>
                  <div>
                    <button className="secondary-action" onClick={() => setIsComplete(true)}>End simulation</button>
                    <button className="primary-action small" onClick={sendMessage} disabled={!input.trim() || loading}>Send response</button>
                  </div>
                </div>
              </>
            ) : (
              <div className="simulation-ended">
                <strong>Simulation ended.</strong>
                <span>Generate the board-ready coaching report from the intelligence panel.</span>
              </div>
            )}
          </div>
        </section>

        <aside className="intelligence-panel panel review-panel">
          <div className="section-heading compact">
            <span>Deal health</span>
            <small>{evaluationStatusLabel(latestEvaluationStatus)}</small>
          </div>
          <div className="health-stack">
            {healthMetrics.map(metric => {
              const value = dealHealth[metric.key] ?? 0
              return (
                <div key={metric.key} className={`health-row ${metric.intent}`}>
                  <div>
                    <span>{metric.label}</span>
                    <strong>{value}</strong>
                  </div>
                  <div className="meter">
                    <i style={{ width: `${value}%` }} />
                  </div>
                </div>
              )
            })}
          </div>

          <div className="section-heading compact with-top">
            <span>Objection stack</span>
            <small>{objectionStack.filter(o => o.status === 'active' || o.status === 'watch').length} live lanes</small>
          </div>
          <div className="objection-list">
            {objectionStack.map(item => (
              <div key={item.id} className={`objection-item ${item.status}`}>
                <div>
                  <strong>{item.label}</strong>
                  <span>{item.latest_signal || item.description}</span>
                </div>
                <em>{statusLabel(item.status)} / {item.severity}</em>
              </div>
            ))}
          </div>

          {latestStrategy && (
            <div className="strategy-card">
              <span>Buyer strategy lens</span>
              <p>{latestStrategy}</p>
            </div>
          )}

          {battleReplay.length > 0 && (
            <>
              <div className="section-heading compact with-top">
                <span>Battle replay</span>
                <small>{battleReplay.length} scored turns</small>
              </div>
              <div className="battle-list">
                {battleReplay.map(item => (
                  <div key={item.turn} className="battle-item">
                    <div>
                      <span>Turn {item.turn}</span>
                      <strong>{item.stage_label}</strong>
                    </div>
                    <em className={scoreTone(item.score)}>{item.score ? `${item.score}/10` : item.label || 'Unscored'}</em>
                    <p>{item.next_best_move || item.missed_moment}</p>
                  </div>
                ))}
              </div>
            </>
          )}

          {(isComplete || messages.length >= 4) && !coaching && (
            <button className="report-action" onClick={requestCoaching} disabled={coachingLoading}>
              {coachingLoading ? <><span className="spinner" /> Building coaching report</> : 'Generate board-ready report'}
            </button>
          )}

          {coaching && (
            <div className="coaching-report">
              <div className="report-header">
                <div>
                  <span>Board-ready report</span>
                  <strong>{coaching.overall_score}/10</strong>
                </div>
                <button className="secondary-action" onClick={copyBoardReport}>{copiedReport ? 'Copied' : 'Copy markdown'}</button>
              </div>
              <p className="report-summary">{coaching.board_summary || coaching.summary}</p>

              <div className="moment-grid">
                <div>
                  <span>Strongest moment</span>
                  <p>{coaching.strongest_moment?.why_it_worked || coaching.strengths?.[0]?.detail}</p>
                </div>
                <div>
                  <span>Weakest moment</span>
                  <p>{coaching.weakest_moment?.why_it_hurt || coaching.weaknesses?.[0]?.detail}</p>
                </div>
              </div>

              <div className="report-section">
                <span>Next-call plan</span>
                <ul>
                  {(coaching.next_call_plan || coaching.coaching_tips?.map(t => t.tip) || []).slice(0, 5).map(item => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>

              {coaching.recommended_founder_script && (
                <div className="founder-script">
                  <span>Practice script</span>
                  <p>{coaching.recommended_founder_script}</p>
                </div>
              )}
            </div>
          )}

          {reasoningSteps.length > 0 && (
            <details className="trace-details">
              <summary>System trace</summary>
              {reasoningSteps.slice(-4).map(step => (
                <div key={`${step.step_number}-${step.title}`} className="trace-step">
                  <strong>{step.title}</strong>
                  <span>{step.output_data || step.description}</span>
                </div>
              ))}
            </details>
          )}
        </aside>
      </main>
    </div>
  )
}

export default App
