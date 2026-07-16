// Dev: Vite proxies /api -> localhost:8000 (see vite.config.ts). Prod (Vercel):
// set VITE_API_URL to the deployed API origin (e.g. the HF Space URL).
const BASE_URL = import.meta.env.VITE_API_URL ?? '/api'

// Mirrors stockrag.factor_engine.report.FactorReport. roe/net_margin are
// ratios (0.27 = 27%), not pre-multiplied percentages.
export interface FactorReport {
  ticker: string
  roe: number | null
  net_margin: number | null
  pe_ratio: number | null
  piotroski_score: number | null
  beta: number | null
  revenue_growth: number | null
  missing: string[]
}

export interface Source {
  index: number
  form: string
  filing_date: string
  section: string
  accession: string
}

export interface AskResponse {
  answer: string
  sources: Source[]
  prompt_version: string
}

// Mirrors the records rag/metrics.py appends to requests.jsonl.
export interface MetricsEntry {
  timestamp: string
  ticker: string
  llm?: string
  model?: string
  prompt_version?: string
  retrieval_ms?: number
  llm_ms?: number
  total_ms?: number
  cost_usd?: number
  citation_coverage?: number
  refused?: boolean
  error?: string
  n_sources?: number
}

export async function getFactors(ticker: string): Promise<FactorReport> {
  const res = await fetch(`${BASE_URL}/factors/${encodeURIComponent(ticker)}`)
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`)
  return res.json()
}

export async function ask(question: string, ticker: string, llm?: string): Promise<AskResponse> {
  const res = await fetch(`${BASE_URL}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, ticker, llm }),
  })
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`)
  return res.json()
}

// SSE over fetch (EventSource can't POST a body). Calls onToken per token,
// resolves with the server's validated final answer — render that, not the
// accumulated tokens (backend may replace uncited answers with a refusal).
export async function askStream(
  question: string,
  ticker: string,
  onToken: (token: string) => void,
  llm?: string,
): Promise<AskResponse> {
  const res = await fetch(`${BASE_URL}/ask/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, ticker, llm }),
  })
  if (!res.ok || !res.body) throw new Error(`${res.status}: ${res.statusText}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  let final: AskResponse | null = null
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const events = buf.split('\n\n')
    buf = events.pop() ?? ''
    for (const evt of events) {
      if (!evt.startsWith('data: ')) continue
      const data = JSON.parse(evt.slice(6))
      if (data.done) final = data
      else if (data.token) onToken(data.token)
    }
  }
  if (!final) throw new Error('Stream ended without a final answer')
  return final
}

export interface ThesisSection {
  topic: string
  question: string
  answer: string
  grounding: number
  sources: Source[]
}

export interface ThesisResponse {
  ticker: string
  synthesis: string
  sections: ThesisSection[]
  prompt_version: string
}

export async function getThesis(ticker: string): Promise<ThesisResponse> {
  const res = await fetch(`${BASE_URL}/thesis/${encodeURIComponent(ticker)}`)
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`)
  return res.json()
}

export interface IngestResponse {
  ticker: string
  filings_ingested: number
  filings_skipped: number
  chunks_added: number
}

export async function ingest(ticker: string, token?: string): Promise<IngestResponse> {
  const res = await fetch(`${BASE_URL}/ingest/${encodeURIComponent(ticker)}`, {
    method: 'POST',
    headers: token ? { 'X-Ingest-Token': token } : {},
  })
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`)
  return res.json()
}

export async function getMetrics(): Promise<MetricsEntry[]> {
  try {
    const res = await fetch(`${BASE_URL}/metrics`)
    if (!res.ok) return []
    return res.json()
  } catch {
    return []
  }
}

export async function getHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/health`)
    return res.ok
  } catch {
    return false
  }
}
