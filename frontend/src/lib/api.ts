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

export interface AskResponse {
  answer: string
  sources: Array<{
    document: string
    page: number | null
    content: string
  }>
  prompt_version: string
}

export interface MetricsEntry {
  timestamp: string
  ticker: string
  question: string
  stage_latencies: Record<string, number>
  token_usage: Record<string, number>
  refusal: boolean
  error: boolean
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
