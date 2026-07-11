const BASE_URL = '/api'

export interface FactorReport {
  ticker: string
  roe_pct: number | null
  net_margin_pct: number | null
  pe_ratio: number | null
  piotroski_score: number | null
  beta: number | null
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

export async function ingest(ticker: string, forms?: string, years?: number): Promise<void> {
  const params = new URLSearchParams()
  if (forms) params.append('forms', forms)
  if (years) params.append('years', String(years))
  const res = await fetch(`${BASE_URL}/ingest/${encodeURIComponent(ticker)}?${params}`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`)
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
