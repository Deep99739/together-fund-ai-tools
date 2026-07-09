import { type ReactNode, useEffect, useMemo, useState } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8003'

interface DimensionScore {
  dimension: string
  score: number
  evidence: string
  concern?: string
}

interface AntiPattern {
  id: string
  name: string
  description: string
  severity: string
  evidence: string
}

interface DiligenceQuestion {
  question: string
  rationale: string
  expected_strong_answer: string
  red_flag_answer: string
}

interface ReasoningStep {
  step_number: number
  title: string
  description: string
  output_data?: string
  step_type: string
  duration_ms?: number
}

interface SourceEvidence {
  term: string
  snippet: string
}

interface RiskRegisterItem {
  id: string
  name: string
  framework: string
  risk_score: number
  status: 'controlled' | 'watch' | 'critical'
  why_it_matters: string
  positive_evidence: SourceEvidence[]
  negative_evidence: SourceEvidence[]
  validation_question: string
}

interface ReliabilityCheck {
  name: string
  status: 'present' | 'missing' | 'partial'
  detail: string
}

interface ReliabilityReport {
  analysis_confidence: number
  document_quality_score: number
  evidence_density_score: number
  word_count: number
  heading_count: number
  quantitative_claims: number
  source_evidence_snippets: number
  deterministic_checks: ReliabilityCheck[]
  caveat: string
}

interface TechnicalDiligenceBrief {
  review_posture: string
  posture_detail: string
  verdict: string
  technical_confidence_score: number
  top_reasons: string[]
  must_validate_next: string[]
  next_technical_diligence_actions: string[]
}

interface ComponentItem {
  name?: string
  type?: string
  purpose?: string
  detail?: string
  component?: string
  description?: string
  complexity?: string
  service?: string
  usage?: string
  criticality?: string
  pattern?: string
}

interface ComponentAnalysis {
  models_used?: ComponentItem[]
  data_pipeline?: {
    description?: string
    proprietary_data?: boolean
    data_sources?: string[]
    processing_steps?: string[]
  }
  custom_logic?: ComponentItem[]
  api_dependencies?: ComponentItem[]
  infrastructure?: {
    hosting?: string
    scaling_approach?: string
    custom_infra?: string[]
  }
  agentic_patterns?: ComponentItem[]
  key_claims?: string[]
  technical_differentiators?: string[]
  error?: string
  raw?: string
}

interface AnalysisResult {
  startup_name: string
  components: ComponentAnalysis
  anti_patterns_detected: AntiPattern[]
  depth_scores: {
    dimension_scores: DimensionScore[]
    overall_verdict: string
    confidence: number
    one_line_summary: string
  }
  average_score: number
  diligence_questions: DiligenceQuestion[]
  risk_register?: RiskRegisterItem[]
  reliability?: ReliabilityReport
  technical_diligence_brief?: TechnicalDiligenceBrief
  reasoning_log: ReasoningStep[]
}

interface SampleDoc {
  filename: string
  name: string
  content: string
}

type Signal = 'strong' | 'watch' | 'weak'

interface XrayNode {
  label: string
  value: string
  detail: string
  signal: Signal
}

type SectionId =
  | 'sourceChecks'
  | 'defensibility'
  | 'depthScores'
  | 'wrapperSignals'
  | 'riskRegister'
  | 'technicalBrief'
  | 'validation'
  | 'reasoning'

const DEFAULT_OPEN_SECTIONS: Record<SectionId, boolean> = {
  sourceChecks: false,
  defensibility: true,
  depthScores: true,
  wrapperSignals: true,
  riskRegister: false,
  technicalBrief: true,
  validation: true,
  reasoning: false,
}

const pipelineSteps = [
  'Parse source material',
  'Extract architecture signals',
  'Check wrapper risk',
  'Score technical depth',
  'Prepare validation checklist',
]

const signalLabel: Record<Signal, string> = {
  strong: 'High confidence',
  watch: 'Needs validation',
  weak: 'Risk signal',
}

const clamp = (value: number, min = 0, max = 100) => Math.min(max, Math.max(min, value))

const truncate = (value: string | undefined, fallback: string, max = 150) => {
  const text = value?.trim() || fallback
  return text.length > max ? `${text.slice(0, max)}…` : text
}

const pluralize = (count: number, singular: string, plural = `${singular}s`) => `${count} ${count === 1 ? singular : plural}`

const sanitizeGeneratedCopy = (value: unknown): unknown => {
  if (typeof value === 'string') {
    return [
      [/\binvestment opportunity\b/gi, 'technical diligence candidate'],
      [/\bventure opportunity\b/gi, 'technical diligence candidate'],
      [/\binvestment memo\b/gi, 'technical diligence brief'],
      [/\binvestment committee\b/gi, 'technical review team'],
      [/\binvestment pipeline\b/gi, 'technical diligence pipeline'],
      [/\binvestment lens\b/gi, 'technical diligence lens'],
      [/\binvestment review\b/gi, 'technical review'],
      [/\binvestable\b/gi, 'technically credible'],
      [/\bcandidate for investment\b/gi, 'candidate for a technical deep dive'],
      [/\bfor investment\b/gi, 'for technical review'],
      [/\bsignificant investment in\b/gi, 'significant technical work in'],
      [/\binfrastructure investment\b/gi, 'infrastructure depth'],
      [/\binvestment\b/gi, 'technical diligence'],
      [/\bCTO-ready\b/gi, 'review-ready'],
      [/\ba CTO or technical partner\b/gi, 'a technical reviewer'],
      [/\bCTO\/founding engineer\b/gi, 'technical owner'],
      [/\bCTO\b/g, 'technical reviewer'],
      [/\bVC firm\b/gi, 'technical diligence team'],
      [/\bVC\b/g, 'review'],
      [/\bIC\b/g, 'technical review'],
      [/\bfounder proof\b/gi, 'source evidence'],
      [/\bdisprove\b/gi, 'validate'],
      [/\bprove\b/gi, 'validate'],
      [/\binterrogation\b/gi, 'validation'],
    ].reduce((text, [pattern, replacement]) => text.replace(pattern as RegExp, replacement as string), value)
  }

  if (Array.isArray(value)) {
    return value.map((item) => sanitizeGeneratedCopy(item))
  }

  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, sanitizeGeneratedCopy(item)]),
    )
  }

  return value
}

const documentNegatesPromptOnlySignal = (documentText: string) =>
  /can't be replicated with prompt engineering|cannot be replicated with prompt engineering|not just prompt engineering|not prompt engineering|beyond prompt engineering/i.test(
    documentText,
  )

const isGenericPromptPattern = (pattern: AntiPattern) => {
  const name = `${pattern.id} ${pattern.name}`.toLowerCase()
  return name.includes('generic') && name.includes('prompt')
}

const isNoisyPromptPattern = (pattern: AntiPattern, documentText: string) => {
  const evidence = pattern.evidence.toLowerCase()

  return (
    isGenericPromptPattern(pattern) &&
    (documentNegatesPromptOnlySignal(documentText) ||
      evidence.includes("can't be replicated") ||
      evidence.includes('cannot be replicated') ||
      evidence.includes('beyond prompt engineering') ||
      evidence.includes('not prompt engineering'))
  )
}

const cleanAnalysisResult = (payload: AnalysisResult, documentText: string): AnalysisResult => {
  const sanitized = sanitizeGeneratedCopy(payload) as AnalysisResult

  return {
    ...sanitized,
    anti_patterns_detected: sanitized.anti_patterns_detected.filter((pattern) => !isNoisyPromptPattern(pattern, documentText)),
  }
}

const getVerdictTone = (verdict: string): Signal => {
  const normalized = verdict.toLowerCase()
  if (normalized.includes('deep')) return 'strong'
  if (normalized.includes('moderate')) return 'watch'
  return 'weak'
}

const getRecommendedStep = (verdict: string) => {
  const normalized = verdict.toLowerCase()
  if (normalized.includes('deep')) return 'Advance to focused technical diligence'
  if (normalized.includes('moderate')) return 'Continue with targeted validation'
  if (normalized.includes('potential')) return 'Request architecture evidence before relying on claims'
  return 'Do not rely on current technical claims'
}

const getScoreSignal = (score: number): Signal => {
  if (score >= 7) return 'strong'
  if (score >= 4) return 'watch'
  return 'weak'
}

const formatListCount = (count: number, singular: string, plural?: string) => {
  const label = count === 1 ? singular : (plural || `${singular}s`)
  return `${count} ${label}`
}

function buildXrayNodes(components: ComponentAnalysis, apiCount: number): XrayNode[] {
  const modelCount = components.models_used?.length || 0
  const customCount = components.custom_logic?.length || 0
  const agentCount = components.agentic_patterns?.length || 0
  const infraCount = components.infrastructure?.custom_infra?.length || 0
  const hasProprietaryData = Boolean(components.data_pipeline?.proprietary_data)

  return [
    {
      label: 'Model layer',
      value: formatListCount(modelCount, 'model'),
      detail: truncate(components.models_used?.[0]?.detail || components.models_used?.[0]?.purpose, 'No model details extracted'),
      signal: modelCount > 1 ? 'strong' : modelCount === 1 ? 'watch' : 'weak',
    },
    {
      label: 'Data moat',
      value: hasProprietaryData ? 'Proprietary signal' : 'No moat confirmed',
      detail: truncate(components.data_pipeline?.description, 'Data source not sufficiently differentiated'),
      signal: hasProprietaryData ? 'strong' : 'weak',
    },
    {
      label: 'Custom logic',
      value: formatListCount(customCount, 'component'),
      detail: truncate(components.custom_logic?.[0]?.description, 'Custom algorithms not clearly identified'),
      signal: customCount >= 3 ? 'strong' : customCount >= 1 ? 'watch' : 'weak',
    },
    {
      label: 'Agentic loop',
      value: formatListCount(agentCount, 'loop'),
      detail: truncate(
        components.agentic_patterns?.[0]?.description || components.agentic_patterns?.[0]?.pattern,
        'No planning or self-correction loop detected',
      ),
      signal: agentCount >= 2 ? 'strong' : agentCount === 1 ? 'watch' : 'weak',
    },
    {
      label: 'Infrastructure moat',
      value: infraCount ? formatListCount(infraCount, 'asset') : 'Standard stack',
      detail: truncate(components.infrastructure?.scaling_approach || components.infrastructure?.hosting, 'No custom infrastructure advantage extracted'),
      signal: infraCount >= 2 ? 'strong' : infraCount === 1 ? 'watch' : 'weak',
    },
    {
      label: 'API exposure',
      value: formatListCount(apiCount, 'dependency', 'dependencies'),
      detail: apiCount > 0 ? 'Core value may depend on third-party services; review replaceability.' : 'No critical external dependency extracted.',
      signal: apiCount >= 2 ? 'weak' : apiCount === 1 ? 'watch' : 'strong',
    },
  ]
}

interface CollapsibleSectionProps {
  id: SectionId
  kicker: string
  title: string
  preview: string
  open: boolean
  tone?: Signal | 'neutral'
  onToggle: (id: SectionId) => void
  children: ReactNode
}

function CollapsibleSection({ id, kicker, title, preview, open, tone = 'neutral', onToggle, children }: CollapsibleSectionProps) {
  return (
    <section className={`collapsible-section ${open ? 'open' : 'closed'} ${tone}`}>
      <button className="section-toggle" type="button" onClick={() => onToggle(id)} aria-expanded={open}>
        <span className="section-toggle-index">{open ? '−' : '+'}</span>
        <span className="section-toggle-copy">
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

function buildMarkdownBrief(result: AnalysisResult) {
  const brief = result.technical_diligence_brief
  const reliability = result.reliability
  const topRisks = result.risk_register?.slice(0, 4) || []
  const questions = result.diligence_questions.slice(0, 6)

  const lines = [
    `# ${result.startup_name} — Architecture Diligence Brief`,
    '',
    `**Verdict:** ${result.depth_scores.overall_verdict}`,
    `**Average technical depth:** ${result.average_score}/10`,
    `**Model confidence:** ${result.depth_scores.confidence}/10`,
    reliability ? `**Source confidence:** ${reliability.analysis_confidence}%` : '',
    '',
    '## Summary',
    result.depth_scores.one_line_summary,
    '',
    '## Recommended posture',
    brief?.review_posture || 'Continue with targeted technical validation.',
    brief?.posture_detail || '',
    '',
    '## Top reasons',
    ...(brief?.top_reasons?.length ? brief.top_reasons.map((item) => `- ${item}`) : result.depth_scores.dimension_scores.slice(0, 3).map((item) => `- ${item.dimension}: ${item.evidence}`)),
    '',
    '## Wrapper / architecture signals',
    ...(result.anti_patterns_detected.length
      ? result.anti_patterns_detected.slice(0, 6).map((pattern) => `- **${pattern.name} (${pattern.severity})**: ${pattern.evidence}`)
      : ['- No major wrapper-risk signal detected from the provided source material.']),
    '',
    '## Technical risks to validate',
    ...(topRisks.length
      ? topRisks.map((risk) => `- **${risk.name} (${risk.status}, ${risk.framework})**: ${risk.validation_question}`)
      : ['- No technical risk register items returned.']),
    '',
    '## Validation questions',
    ...questions.map((item, index) => `${index + 1}. ${item.question}`),
    '',
    '## Source quality',
    reliability
      ? `Document quality ${reliability.document_quality_score}/100 · evidence snippets ${reliability.source_evidence_snippets} · quantitative claims ${reliability.quantitative_claims}.`
      : 'Source reliability data was not returned.',
  ].filter(Boolean)

  return lines.join('\n')
}

function App() {
  const [startupName, setStartupName] = useState('')
  const [docText, setDocText] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [samples, setSamples] = useState<SampleDoc[]>([])
  const [error, setError] = useState<string | null>(null)
  const [sourceCollapsed, setSourceCollapsed] = useState(false)
  const [openSections, setOpenSections] = useState<Record<SectionId, boolean>>(DEFAULT_OPEN_SECTIONS)
  const [copiedBrief, setCopiedBrief] = useState(false)

  useEffect(() => {
    fetch(`${API_BASE}/api/sample-docs`)
      .then((response) => response.json())
      .then((data) => setSamples(data.samples || []))
      .catch(() => setSamples([]))
  }, [])

  const handleAnalyze = async () => {
    if (!docText.trim() || loading) return
    setLoading(true)
    setResult(null)
    setError(null)
    setSourceCollapsed(false)
    setCopiedBrief(false)

    try {
      const response = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          document_text: docText,
          startup_name: startupName || 'Startup',
        }),
      })

      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'Analysis failed')
      setResult(cleanAnalysisResult(payload, docText))
      setOpenSections(DEFAULT_OPEN_SECTIONS)
      setSourceCollapsed(true)
      setCopiedBrief(false)
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  const loadSample = (sample: SampleDoc) => {
    setDocText(sample.content)
    setStartupName(sample.name)
    setResult(null)
    setError(null)
    setSourceCollapsed(false)
    setCopiedBrief(false)
  }

  const toggleSection = (sectionId: SectionId) => {
    setOpenSections((current) => ({ ...current, [sectionId]: !current[sectionId] }))
  }

  const docStats = useMemo(() => {
    const words = docText.trim() ? docText.trim().split(/\s+/).length : 0
    return {
      characters: docText.length.toLocaleString(),
      words: words.toLocaleString(),
      rawWords: words,
      capacity: clamp((docText.length / 50000) * 100),
    }
  }, [docText])

  const derived = useMemo(() => {
    if (!result) return null
    const components = result.components || {}
    const apiCount = components.api_dependencies?.length || 0
    const antiPatternCount = result.anti_patterns_detected.length
    const wrapperRisk = clamp(((10 - result.average_score) * 7) + (antiPatternCount * 12))
    const moatStrength = clamp((result.average_score * 10) - (antiPatternCount * 4))
    const xrayNodes = buildXrayNodes(components, apiCount)
    const tone = getVerdictTone(result.depth_scores.overall_verdict)
    const riskRegister = result.risk_register || []
    const criticalRisks = riskRegister.filter((risk) => risk.status === 'critical').length
    const watchRisks = riskRegister.filter((risk) => risk.status === 'watch').length
    const recommendedStep = result.technical_diligence_brief?.review_posture || getRecommendedStep(result.depth_scores.overall_verdict)
    const postureDetail = result.technical_diligence_brief?.posture_detail || ''

    return {
      components,
      apiCount,
      antiPatternCount,
      wrapperRisk,
      moatStrength,
      xrayNodes,
      tone,
      recommendedStep,
      postureDetail,
      differentiators: components.technical_differentiators || [],
      claims: components.key_claims || [],
      riskRegister,
      criticalRisks,
      watchRisks,
      reliability: result.reliability,
      brief: result.technical_diligence_brief,
    }
  }, [result])

  const copyMarkdownBrief = async () => {
    if (!result) return
    await navigator.clipboard.writeText(buildMarkdownBrief(result))
    setCopiedBrief(true)
  }

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark">Together</div>
          <div>
            <div className="brand-name">Together Fund</div>
            <div className="brand-product">AI-native architecture diligence</div>
          </div>
        </div>
        <div className="topbar-right">
          <span className="status-pill">Local-first</span>
          <span className="status-pill subdued">Transparent reasoning</span>
        </div>
      </header>

      <main className="workspace">
        <section className="hero-panel">
          <div className="hero-copy">
            <div className="eyebrow">(01) Technical diligence</div>
            <h1>Evidence-backed architecture review for AI-native companies.</h1>
            <p>
              Review source material, separate durable technical wedges from thin wrapper risk, and convert
              uncertain claims into a validation checklist for the next conversation.
            </p>
          </div>
          <div className="hero-metrics">
            <div className="metric-card">
              <span className="metric-value">5</span>
              <span className="metric-label">Depth dimensions</span>
            </div>
            <div className="metric-card">
              <span className="metric-value">8</span>
              <span className="metric-label">Wrapper patterns</span>
            </div>
            <div className="metric-card">
              <span className="metric-value">50K</span>
              <span className="metric-label">Character limit</span>
            </div>
          </div>
        </section>

        <section className={`analysis-grid ${sourceCollapsed && result ? 'source-collapsed' : ''}`}>
          <aside className={`input-console glass-panel ${sourceCollapsed && result ? 'collapsed' : ''}`}>
            {sourceCollapsed && result ? (
              <div className="source-rail">
                <button className="source-rail-button" type="button" onClick={() => setSourceCollapsed(false)}>
                  <span>Source</span>
                  <strong>{docStats.words}</strong>
                  <small>words</small>
                </button>
                <button className="source-rail-edit" type="button" onClick={() => setSourceCollapsed(false)}>
                  View / edit
                </button>
              </div>
            ) : (
              <>
                <div className="panel-heading">
                  <div>
                    <div className="section-kicker">Source material</div>
                    <h2>Startup architecture document</h2>
                  </div>
                  <div className="doc-meter">
                    <span>{docStats.characters} chars</span>
                    <div className="doc-meter-track">
                      <div className="doc-meter-fill" style={{ width: `${docStats.capacity}%` }} />
                    </div>
                  </div>
                </div>

                {result && (
                  <button className="source-collapse-button" type="button" onClick={() => setSourceCollapsed(true)}>
                    Collapse source panel
                  </button>
                )}

                <label className="field-label" htmlFor="startup-name">Startup name</label>
                <input
                  id="startup-name"
                  className="text-input"
                  value={startupName}
                  onChange={(event) => setStartupName(event.target.value)}
                  placeholder="Cortex Security"
                />

                {samples.length > 0 && (
                  <div className="sample-row">
                    <span className="field-label">Demo data</span>
                    <div className="sample-actions">
                      {samples.map((sample) => (
                        <button
                          key={sample.filename}
                          className="ghost-button"
                          type="button"
                          onClick={() => loadSample(sample)}
                        >
                          {sample.name}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <label className="field-label" htmlFor="document-text">Architecture notes</label>
                <textarea
                  id="document-text"
                  className="document-input"
                  value={docText}
                  onChange={(event) => setDocText(event.target.value)}
                  placeholder="Paste technical architecture, model stack, data pipeline, infrastructure notes, or pitch-deck technical section..."
                />

                <div className="input-footer">
                  <div className="doc-stats">
                    <span>{docStats.words} words</span>
                    <span>{samples.length} sample docs loaded</span>
                  </div>
                  <button
                    className="primary-action"
                    type="button"
                    onClick={handleAnalyze}
                    disabled={!docText.trim() || loading}
                  >
                    {loading ? 'Running review' : result ? 'Run updated review' : 'Review architecture'}
                  </button>
                </div>
              </>
            )}
          </aside>

          <section className="output-console glass-panel">
            {!loading && !result && !error && (
              <div className="preflight">
                <div className="preflight-card">
                  <div className="preflight-label">Ready for analysis</div>
                  <h2>Run a first-pass technical review from architecture notes.</h2>
                  <p>
                    The output is organized as a review brief, source-grounded signals, wrapper-risk checks,
                    technical risks, validation questions, and an auditable reasoning trace.
                  </p>
                </div>
                <div className="pipeline-preview">
                  {pipelineSteps.map((step, index) => (
                    <div className="pipeline-step" key={step}>
                      <span>{String(index + 1).padStart(2, '0')}</span>
                      <p>{step}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {error && (
              <div className="error-state">
                <div className="error-label">Pipeline failed</div>
                <p>{error}</p>
              </div>
            )}

            {loading && (
              <div className="processing-state">
                <div className="scan-card">
                  <div className="scan-line" />
                  <h2>Running technical diligence</h2>
                  <p>Extracting source-grounded architecture signals, checking wrapper risk, and preparing a validation checklist.</p>
                </div>
                <div className="pipeline-preview active">
                  {pipelineSteps.map((step, index) => (
                    <div className="pipeline-step" key={step}>
                      <span>{String(index + 1).padStart(2, '0')}</span>
                      <p>{step}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {result && derived && (
              <div className="result-stack">
                <section className={`review-brief-card ${derived.tone}`}>
                  <div className="review-brief-top">
                    <div>
                      <span className="section-kicker">Review brief</span>
                      <h2>{result.depth_scores.overall_verdict}</h2>
                      <p>{result.depth_scores.one_line_summary}</p>
                    </div>
                    <div className="brief-score">
                      <span>{result.average_score}</span>
                      <small>/10 depth</small>
                    </div>
                  </div>

                  <div className="recommended-step">
                    <span>Recommended next step</span>
                    <strong>{derived.recommendedStep}</strong>
                  </div>
                  {derived.postureDetail && <p className="posture-detail">{derived.postureDetail}</p>}

                  <div className="brief-metric-grid">
                    <div className="brief-metric">
                      <span>Wrapper risk</span>
                      <strong>{Math.round(derived.wrapperRisk)}%</strong>
                    </div>
                    <div className="brief-metric">
                      <span>Moat strength</span>
                      <strong>{Math.round(derived.moatStrength)}%</strong>
                    </div>
                    <div className="brief-metric">
                      <span>Signals to review</span>
                      <strong>{derived.antiPatternCount}</strong>
                    </div>
                    {derived.reliability && (
                      <div className="brief-metric">
                        <span>Source confidence</span>
                        <strong>{derived.reliability.analysis_confidence}%</strong>
                      </div>
                    )}
                  </div>

                  <div className="result-actions">
                    <button type="button" onClick={copyMarkdownBrief}>
                      {copiedBrief ? 'Markdown brief copied' : 'Copy diligence brief'}
                    </button>
                    <span>Exports verdict, risks, source confidence, and validation questions.</span>
                  </div>
                </section>

                {derived.reliability && (
                  <CollapsibleSection
                    id="sourceChecks"
                    kicker="Source-grounded checks"
                    title="Reliability layer"
                    preview={`${derived.reliability.analysis_confidence}% analysis confidence · ${derived.reliability.source_evidence_snippets} source snippets · ${derived.reliability.quantitative_claims} quantitative claims`}
                    open={openSections.sourceChecks}
                    onToggle={toggleSection}
                  >
                    <div className="reliability-grid">
                      <div className="reliability-score">
                        <span>Analysis confidence</span>
                        <strong>{derived.reliability.analysis_confidence}%</strong>
                        <p>Blends model confidence, document completeness, and direct source-evidence density.</p>
                      </div>
                      <div className="reliability-facts">
                        <div><span>Words</span><strong>{derived.reliability.word_count}</strong></div>
                        <div><span>Quant claims</span><strong>{derived.reliability.quantitative_claims}</strong></div>
                        <div><span>Evidence</span><strong>{derived.reliability.source_evidence_snippets}</strong></div>
                      </div>
                    </div>
                    <div className="check-grid">
                      {derived.reliability.deterministic_checks.map((check) => (
                        <article className={`check-card ${check.status}`} key={check.name}>
                          <div className="check-card-top">
                            <span>{check.name}</span>
                            <small>{check.status}</small>
                          </div>
                          <p>{check.detail}</p>
                        </article>
                      ))}
                    </div>
                  </CollapsibleSection>
                )}

                <CollapsibleSection
                  id="defensibility"
                  kicker="Architecture signals"
                  title="Defensibility map"
                  preview={derived.xrayNodes.map((node) => `${node.label}: ${node.value}`).slice(0, 3).join(' · ')}
                  open={openSections.defensibility}
                  tone={derived.tone}
                  onToggle={toggleSection}
                >
                  <div className="xray-grid">
                    {derived.xrayNodes.map((node) => (
                      <article className={`xray-node ${node.signal}`} key={node.label}>
                        <div className="node-header">
                          <span>{node.label}</span>
                          <small>{signalLabel[node.signal]}</small>
                        </div>
                        <strong>{node.value}</strong>
                        <p>{node.detail}</p>
                      </article>
                    ))}
                  </div>
                  {(derived.differentiators.length > 0 || derived.claims.length > 0) && (
                    <div className="signal-appendix">
                      <div>
                        <span>Claims worth validating</span>
                        <ul>
                          {derived.claims.slice(0, 4).map((claim) => <li key={claim}>{claim}</li>)}
                        </ul>
                      </div>
                      <div>
                        <span>Potential differentiators</span>
                        <ul>
                          {derived.differentiators.slice(0, 4).map((claim) => <li key={claim}>{claim}</li>)}
                        </ul>
                      </div>
                    </div>
                  )}
                </CollapsibleSection>

                <CollapsibleSection
                  id="depthScores"
                  kicker="Technical depth model"
                  title="Depth scores"
                  preview={`${result.depth_scores.overall_verdict} · average ${result.average_score}/10 · confidence ${result.depth_scores.confidence}/10`}
                  open={openSections.depthScores}
                  tone={derived.tone}
                  onToggle={toggleSection}
                >
                  <div className="score-guide">
                    <div>
                      <span>1–3</span>
                      <strong>Thin or unverified</strong>
                      <p>Mostly API orchestration, generic prompts, or unsupported architecture claims.</p>
                    </div>
                    <div>
                      <span>4–6</span>
                      <strong>Meaningful but exposed</strong>
                      <p>Some proprietary data, workflow logic, or evaluation, but durable technical depth is not yet proven.</p>
                    </div>
                    <div>
                      <span>7–10</span>
                      <strong>Defensible depth</strong>
                      <p>Custom models, data flywheel, production evaluation, or infrastructure that is hard to copy quickly.</p>
                    </div>
                  </div>
                  <div className="score-list">
                    {result.depth_scores.dimension_scores?.map((dimension) => {
                      const signal = getScoreSignal(dimension.score)
                      return (
                        <article className="score-row" key={dimension.dimension}>
                          <div className="score-row-top">
                            <span>{dimension.dimension}</span>
                            <strong className={signal}>{dimension.score}/10</strong>
                          </div>
                          <div className="score-track">
                            <div className={signal} style={{ width: `${dimension.score * 10}%` }} />
                          </div>
                          <p>{dimension.evidence}</p>
                          {dimension.concern && <small>{dimension.concern}</small>}
                        </article>
                      )
                    })}
                  </div>
                </CollapsibleSection>

                <CollapsibleSection
                  id="wrapperSignals"
                  kicker="Wrapper risk"
                  title="Risk signals"
                  preview={
                    result.anti_patterns_detected.length
                      ? `${pluralize(result.anti_patterns_detected.length, 'signal')} found · ${Math.round(derived.wrapperRisk)}% wrapper risk`
                      : `No major wrapper signal found · ${Math.round(derived.wrapperRisk)}% wrapper risk`
                  }
                  open={openSections.wrapperSignals}
                  tone={derived.antiPatternCount ? 'weak' : 'strong'}
                  onToggle={toggleSection}
                >
                  {result.anti_patterns_detected.length === 0 ? (
                    <div className="clear-card">
                      <strong>No major wrapper-risk signal detected</strong>
                      <p>The extracted architecture shows enough original technical surface area to justify deeper review.</p>
                    </div>
                  ) : (
                    <div className="risk-grid">
                      {result.anti_patterns_detected.map((pattern) => (
                        <article className={`risk-card severity-${pattern.severity}`} key={`${pattern.id}-${pattern.evidence}`}>
                          <div className="risk-card-top">
                            <span>{pattern.name}</span>
                            <small>{pattern.severity}</small>
                          </div>
                          <p>{pattern.evidence}</p>
                        </article>
                      ))}
                    </div>
                  )}
                </CollapsibleSection>

                {derived.riskRegister.length > 0 && (
                  <CollapsibleSection
                    id="riskRegister"
                    kicker="Technical risk register"
                    title="NIST / OWASP-aligned risks"
                    preview={`${derived.criticalRisks} critical · ${derived.watchRisks} watch · ${derived.riskRegister.length} total risks`}
                    open={openSections.riskRegister}
                    tone={derived.criticalRisks ? 'weak' : derived.watchRisks ? 'watch' : 'strong'}
                    onToggle={toggleSection}
                  >
                    <div className="risk-register-list">
                      {derived.riskRegister.map((risk) => (
                        <article className={`risk-register-card ${risk.status}`} key={risk.id}>
                          <div className="risk-register-top">
                            <div>
                              <span>{risk.framework}</span>
                              <h4>{risk.name}</h4>
                            </div>
                            <strong>{risk.risk_score}</strong>
                          </div>
                          <p>{risk.why_it_matters}</p>
                          <div className="risk-register-evidence">
                            <div>
                              <span>Positive evidence</span>
                              <p>{risk.positive_evidence[0]?.snippet || 'No strong source evidence found.'}</p>
                            </div>
                            <div>
                              <span>Risk evidence</span>
                              <p>{risk.negative_evidence[0]?.snippet || 'No direct risk evidence found.'}</p>
                            </div>
                          </div>
                          <div className="validation-question">{risk.validation_question}</div>
                        </article>
                      ))}
                    </div>
                  </CollapsibleSection>
                )}

                {derived.brief && (
                  <CollapsibleSection
                    id="technicalBrief"
                    kicker="Validation plan"
                    title="What to verify next"
                    preview={`${derived.brief.technical_confidence_score}% technical confidence · ${derived.brief.must_validate_next.length} validation items`}
                    open={openSections.technicalBrief}
                    tone={derived.tone}
                    onToggle={toggleSection}
                  >
                    <div className="brief-grid">
                      <div className="brief-card">
                        <span>Technical confidence</span>
                        <strong>{derived.brief.technical_confidence_score}%</strong>
                        {derived.brief.top_reasons.map((reason) => <p key={reason}>{reason}</p>)}
                      </div>
                      <div className="brief-card">
                        <span>Evidence to validate</span>
                        <ul>
                          {derived.brief.must_validate_next.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
                        </ul>
                      </div>
                      <div className="brief-card">
                        <span>Suggested next actions</span>
                        <ul>
                          {derived.brief.next_technical_diligence_actions.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
                        </ul>
                      </div>
                    </div>
                  </CollapsibleSection>
                )}

                <CollapsibleSection
                  id="validation"
                  kicker="Validation checklist"
                  title="Open technical questions"
                  preview={`${result.diligence_questions.length} follow-up questions · good evidence vs concern if missing`}
                  open={openSections.validation}
                  onToggle={toggleSection}
                >
                  <div className="question-stack">
                    {result.diligence_questions.map((question, index) => (
                      <article className="question-card" key={`${question.question}-${index}`}>
                        <div className="question-index">{String(index + 1).padStart(2, '0')}</div>
                        <div className="question-body">
                          <h4>{question.question}</h4>
                          <p>{question.rationale}</p>
                          <div className="answer-grid">
                            <div>
                              <span>Good evidence</span>
                              <p>{question.expected_strong_answer}</p>
                            </div>
                            <div>
                              <span>Concern if missing</span>
                              <p>{question.red_flag_answer}</p>
                            </div>
                          </div>
                        </div>
                      </article>
                    ))}
                  </div>
                </CollapsibleSection>

                <CollapsibleSection
                  id="reasoning"
                  kicker="Reasoning trace"
                  title="Auditable execution log"
                  preview={`${result.reasoning_log.length} pipeline steps · extraction, scoring, validation, risk calibration`}
                  open={openSections.reasoning}
                  onToggle={toggleSection}
                >
                  <div className="timeline">
                    {result.reasoning_log.map((step) => (
                      <article className="timeline-step" key={`${step.step_number}-${step.title}`}>
                        <span className="timeline-index">{String(step.step_number).padStart(2, '0')}</span>
                        <div>
                          <div className="timeline-title">
                            <strong>{step.title}</strong>
                            <small>{step.step_type}{step.duration_ms ? ` · ${step.duration_ms}ms` : ''}</small>
                          </div>
                          <p>{step.description}</p>
                          {step.output_data && <pre>{step.output_data}</pre>}
                        </div>
                      </article>
                    ))}
                  </div>
                </CollapsibleSection>
              </div>
            )}
          </section>
        </section>
      </main>
    </div>
  )
}

export default App
