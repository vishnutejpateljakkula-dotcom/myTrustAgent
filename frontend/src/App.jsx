import { useState } from 'react'

// When served by FastAPI, use the current origin so UI and API share one server.
const API_URL = import.meta.env.VITE_API_URL || ''
const steps = ['Orchestrator', 'Research Agent', 'Fact Checker', 'Critic', 'Trust Engine', 'Final Generator']

function Card({ title, children, className = '' }) { return <section className={`card ${className}`}><h2>{title}</h2>{children}</section> }

export default function App() {
  const [question, setQuestion] = useState('Who invented the telephone?')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const factChecks = Array.isArray(result?.fact_check)
    ? result.fact_check
    : result?.fact_check
      ? [{ claim: String(result.fact_check), status: 'Uncertain', reasoning: 'The API returned an unstructured fact-check result.' }]
      : []
  async function analyze(event) {
    event.preventDefault(); setError(''); setResult(null)
    if (!question.trim()) return setError('Enter a question before analyzing it.')
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/api/analyze`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Analysis failed.')
      setResult(data)
    } catch (err) { setError(`Could not reach TrustAgent: ${err.message}. Ensure the backend is running on port 8000.`) }
    finally { setLoading(false) }
  }
  return <main>
    <header><div className="logo">TA</div><div><h1>TrustAgent</h1><p>A Trust-Aware Multi-Agent Framework for Reliable and Verifiable Generative AI</p></div></header>
    <Card title="Ask a research question" className="question-card"><form onSubmit={analyze}><textarea value={question} onChange={e => setQuestion(e.target.value)} maxLength="2000" placeholder="Ask a factual question…"/><button disabled={loading}>{loading ? 'Analyzing…' : 'Analyze'}</button></form>{error && <p className="error">{error}</p>}</Card>
    <Card title="Verification pipeline"><div className="pipeline">{steps.map((step, i) => <div className={loading ? 'step running' : result ? 'step done' : 'step'} key={step}><span>{result ? '✓' : i + 1}</span>{step}</div>)}</div></Card>
    {result && <div className="results">
      {result.demo_mode && <p className="notice">Demo mode: no LLM key was used and/or live retrieval was unavailable. Results remain safe but are not a substitute for primary sources.</p>}
      <Card title="Verified final answer" className="final"><p>{result.final_answer}</p></Card>
      <div className="metrics"><Card title="Confidence score"><div className="score">{result.confidence_score}<small>/100</small></div><div className="bar"><i style={{ width: `${result.confidence_score}%` }}/></div></Card><Card title="Trust level"><strong className={`level ${result.trust_level.toLowerCase()}`}>{result.trust_level}</strong><p>{result.verification_status}</p></Card></div>
      <Card title="Evidence / sources">{result.evidence.length ? <ul className="sources">{result.evidence.map(source => <li key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.title}</a><span>{source.quality} quality · {source.snippet}</span></li>)}</ul> : <p>No source was retrieved. The result is intentionally marked unverified.</p>}</Card>
      <div className="compare"><Card title="Initial AI answer"><p>{result.initial_answer}</p></Card><Card title="Detected issues">{result.detected_issues.length ? <ul>{result.detected_issues.map(issue => <li key={issue}>{issue}</li>)}</ul> : <p>No critical issues detected by the critic.</p>}</Card></div>
      <Card title="Agent analysis"><div className="analysis">{Object.entries(result.agent_analysis).map(([name, value]) => <div key={name}><h3>{name.replace('_', ' ')}</h3><p>{value}</p></div>)}</div></Card>
      <Card title="Fact-check results"><div className="checks">{factChecks.length ? factChecks.map((check, i) => <div key={i}><b className={(check.status || 'Uncertain').toLowerCase()}>{check.status || 'Uncertain'}</b><p>{check.claim || 'No claim returned.'}</p><small>{check.reasoning || 'No fact-check reasoning returned.'}</small></div>) : <p>No fact-check result was returned.</p>}</div></Card>
    </div>}
  </main>
}
