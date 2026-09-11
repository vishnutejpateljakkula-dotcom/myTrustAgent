import { useCallback, useEffect, useState } from 'react'
import {
  Activity, AlertCircle, CheckCircle2, Database, ExternalLink, FileSearch,
  LayoutDashboard, LoaderCircle, Network, RefreshCw, Search, Server, ShieldCheck,
} from 'lucide-react'
import TrustAgentLogo from './TrustAgentLogo'

const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const steps = ['Orchestrator', 'Research Agent', 'Fact Checker', 'Critic', 'Trust Engine', 'Final Generator']
const tabs = [
  { id: 'dashboard', label: 'Dashboard', path: '/', icon: LayoutDashboard },
  { id: 'evidence', label: 'Evidence', path: '/evidence', icon: FileSearch },
  { id: 'agents', label: 'Agents', path: '/agents', icon: Network },
  { id: 'server', label: 'Server', path: '/server', icon: Server },
]
let pendingHealthRequest = null

function Card({ title, children, className = '' }) {
  return <section className={'card ' + className}><h2>{title}</h2>{children}</section>
}

function EmptyState({ title, children }) {
  return <div className="empty-state"><ShieldCheck size={26} aria-hidden="true" /><h2>{title}</h2><p>{children}</p></div>
}

function activeTabFromPath() {
  return tabs.find((tab) => tab.path === window.location.pathname)?.id || 'dashboard'
}

function formatUptime(seconds) {
  if (!Number.isFinite(seconds)) return 'Unavailable'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (days) return days + 'd ' + hours + 'h ' + minutes + 'm'
  if (hours) return hours + 'h ' + minutes + 'm'
  return minutes + 'm'
}

export default function App() {
  const [question, setQuestion] = useState('Who invented the telephone?')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState(activeTabFromPath)
  const [health, setHealth] = useState(null)
  const [healthLoading, setHealthLoading] = useState(false)
  const [healthError, setHealthError] = useState('')
  const [checkedAt, setCheckedAt] = useState(null)
  const factChecks = Array.isArray(result?.fact_check)
    ? result.fact_check
    : result?.fact_check
      ? [{ claim: String(result.fact_check), status: 'Uncertain', reasoning: 'The API returned an unstructured fact-check result.' }]
      : []

  const navigate = useCallback((tabId) => {
    const tab = tabs.find((item) => item.id === tabId)
    if (!tab) return
    if (window.location.pathname !== tab.path) window.history.pushState({}, '', tab.path)
    setActiveTab(tabId)
  }, [])

  useEffect(() => {
    const onPopState = () => setActiveTab(activeTabFromPath())
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const loadHealth = useCallback(async () => {
    setHealthError('')
    setHealthLoading(true)
    try {
      if (!pendingHealthRequest) {
        pendingHealthRequest = fetch(API_URL + '/api/health', { headers: { Accept: 'application/json' } })
          .then(async (response) => {
            const contentType = response.headers.get('content-type') || ''
            if (!contentType.includes('application/json')) throw new Error('The health endpoint returned ' + response.status + ' instead of JSON.')
            const data = await response.json()
            if (!response.ok) throw new Error(data.detail || 'The health check failed.')
            return data
          })
          .finally(() => { pendingHealthRequest = null })
      }
      const data = await pendingHealthRequest
      setHealth(data)
      setCheckedAt(new Date())
    } catch (err) {
      setHealthError('Could not load server status: ' + err.message)
    } finally {
      setHealthLoading(false)
    }
  }, [])

  useEffect(() => {
    if (activeTab === 'server' && !health && !healthLoading && !healthError) loadHealth()
  }, [activeTab, health, healthLoading, healthError, loadHealth])

  async function analyze(event) {
    event.preventDefault()
    setError('')
    setResult(null)
    if (!question.trim()) return setError('Enter a question before analyzing it.')
    setLoading(true)
    try {
      const response = await fetch(API_URL + '/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      const contentType = response.headers.get('content-type') || ''
      if (!contentType.includes('application/json')) {
        throw new Error(response.status === 404
          ? 'The TrustAgent API is not deployed at /api/analyze. Redeploy after verifying the API route configuration.'
          : 'The API returned ' + response.status + ' instead of JSON.')
      }
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Analysis failed.')
      setResult(data)
      navigate('evidence')
    } catch (err) {
      setError('Could not reach TrustAgent: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  return <main>
    <header className="app-header">
      <div className="brand-lockup"><TrustAgentLogo /><div><p className="eyebrow">Verification workspace</p><p className="tagline">Evidence-aware research, with transparent confidence.</p></div></div>
      <div className="api-indicator" title="Open the Server tab for a full health check"><span aria-hidden="true" />Local server</div>
    </header>

    <nav className="tabs" aria-label="Primary navigation">
      {tabs.map(({ id, label, icon: Icon }) => <button key={id} type="button" className={'tab ' + (activeTab === id ? 'active' : '')} onClick={() => navigate(id)} aria-current={activeTab === id ? 'page' : undefined}><Icon size={17} strokeWidth={2} aria-hidden="true" /><span>{label}</span></button>)}
    </nav>

    {activeTab === 'dashboard' && <>
      <section className="page-heading"><div><p className="eyebrow">Research dashboard</p><h1>Ask a question. Inspect the evidence.</h1><p>TrustAgent separates a preliminary answer from its verification trail.</p></div></section>
      <Card title="Ask a research question" className="question-card"><form onSubmit={analyze}><div className="question-field"><label htmlFor="research-question">Your question</label><textarea id="research-question" value={question} onChange={e => setQuestion(e.target.value)} maxLength="2000" placeholder="Ask a factual question…" /></div><button type="submit" disabled={loading}>{loading ? <><LoaderCircle size={17} className="spin" aria-hidden="true" />Analyzing</> : <><Search size={17} aria-hidden="true" />Analyze</>}</button></form>{error && <p className="error" role="alert"><AlertCircle size={18} aria-hidden="true" />{error}</p>}</Card>
      <Card title="Verification pipeline"><div className="pipeline">{steps.map((step, index) => <div className={loading ? 'step running' : result ? 'step done' : 'step'} key={step}><span>{result ? <CheckCircle2 size={14} aria-hidden="true" /> : index + 1}</span>{step}</div>)}</div><p className="pipeline-note">Each stage is shown in the Agents tab after a result is available.</p></Card>
    </>}

    {activeTab === 'evidence' && <>
      <section className="page-heading"><div><p className="eyebrow">Evidence review</p><h1>Results you can inspect.</h1><p>Confidence reflects retrieved sources, claim checks, and review flags.</p></div>{result && <button type="button" className="secondary-button" onClick={() => navigate('dashboard')}><Search size={16} aria-hidden="true" />New question</button>}</section>
      {!result ? <EmptyState title="No analysis yet">Run a research question from the Dashboard to inspect the answer, sources, and verification results.</EmptyState> : <div className="results">
        {result.demo_mode && !result.service_warnings?.length && <p className="notice"><AlertCircle size={18} aria-hidden="true" />Demo mode: no LLM key was used and/or live retrieval was unavailable. Results are not a substitute for primary sources.</p>}
        {result.service_warnings?.length > 0 && <p className="notice"><AlertCircle size={18} aria-hidden="true" />Verification warning: {result.service_warnings.join(' ')}</p>}
        <Card title="Verified final answer" className="final"><p>{result.final_answer}</p></Card>
        <div className="metrics"><Card title="Confidence score"><div className="score">{result.confidence_score}<small>/100</small></div><div className="bar" aria-label={'Confidence score: ' + result.confidence_score + ' out of 100'}><i style={{ width: result.confidence_score + '%' }} /></div></Card><Card title="Trust level"><strong className={'level ' + result.trust_level.toLowerCase()}>{result.trust_level}</strong><p>{result.verification_status}</p></Card></div>
        <Card title="Evidence sources">{result.evidence.length ? <ul className="sources">{result.evidence.map(source => <li key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.title}<ExternalLink size={14} aria-label="Opens in a new tab" /></a><span>{source.quality} quality · {source.snippet}</span></li>)}</ul> : <p>No source was retrieved. The result is intentionally marked unverified.</p>}</Card>
        <div className="compare"><Card title="Initial AI answer"><p>{result.initial_answer}</p></Card><Card title="Detected issues">{result.detected_issues.length ? <ul>{result.detected_issues.map(issue => <li key={issue}>{issue}</li>)}</ul> : <p>No critical issues were identified by the critic.</p>}</Card></div>
        <Card title="Fact-check results"><div className="checks">{factChecks.length ? factChecks.map((check, index) => <div key={check.claim + '-' + index}><b className={(check.status || 'Uncertain').toLowerCase()}>{check.status || 'Uncertain'}</b><p>{check.claim || 'No claim returned.'}</p><small>{check.reasoning || 'No fact-check reasoning returned.'}</small></div>) : <p>No fact-check result was returned.</p>}</div></Card>
      </div>}
    </>}

    {activeTab === 'agents' && <>
      <section className="page-heading"><div><p className="eyebrow">Agent trace</p><h1>A visible verification workflow.</h1><p>Review what each stage contributes before relying on the final response.</p></div></section>
      {!result ? <EmptyState title="The agent trace appears after analysis">The pipeline stages are ready, but they need a research question to produce an audit trail.</EmptyState> : <><Card title="Verification pipeline"><div className="pipeline detailed">{steps.map((step, index) => <div className="step done" key={step}><span><CheckCircle2 size={14} aria-hidden="true" /></span>{index + 1}. {step}</div>)}</div></Card><Card title="Agent analysis"><div className="analysis">{Object.entries(result.agent_analysis).map(([name, value]) => <div key={name}><h3>{name.replaceAll('_', ' ')}</h3><p>{value}</p></div>)}</div></Card></>}
    </>}

    {activeTab === 'server' && <>
      <section className="page-heading"><div><p className="eyebrow">Server status</p><h1>Safe operational health.</h1><p>Status intentionally excludes keys, tokens, environment values, and other credentials.</p></div><button type="button" className="secondary-button" onClick={loadHealth} disabled={healthLoading}>{healthLoading ? <LoaderCircle size={16} className="spin" aria-hidden="true" /> : <RefreshCw size={16} aria-hidden="true" />}Refresh</button></section>
      {healthError && <p className="error" role="alert"><AlertCircle size={18} aria-hidden="true" />{healthError}</p>}
      {healthLoading && !health ? <EmptyState title="Checking server health">Loading API and application status…</EmptyState> : health && <><div className="status-summary"><Activity size={19} aria-hidden="true" /><div><strong>{health.status === 'ok' ? 'Operational' : 'Check required'}</strong><span>{health.api_status || 'API status reported by the server'}</span></div><span className="status-time">{checkedAt ? 'Checked ' + checkedAt.toLocaleTimeString() : ''}</span></div><div className="status-grid"><Card title="API"><dl><dt>API status</dt><dd><span className={health.status === 'ok' ? 'status-good' : 'status-caution'}>{health.api_status || health.status}</span></dd><dt>Response mode</dt><dd>{health.mode === 'llm' ? 'LLM enabled' : 'Safe demo mode'}</dd></dl></Card><Card title="Runtime"><dl><dt>Uptime</dt><dd>{formatUptime(health.uptime_seconds)}</dd><dt>Frontend build</dt><dd>{health.frontend_available ? 'Available' : 'Not built'}</dd></dl></Card><Card title="Services"><dl><dt>Language model</dt><dd>{health.llm_configured ? 'Configured' : 'Not configured'}</dd><dt><Database size={15} aria-hidden="true" />Database</dt><dd>{health.database_configured ? 'Connected' : 'Not used by this app'}</dd></dl></Card></div></>}
    </>}
  </main>
}
