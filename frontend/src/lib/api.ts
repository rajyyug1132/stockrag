// Dev: Vite proxies /api -> localhost:8000 (see vite.config.ts). Prod (Vercel):
// set VITE_API_URL to the deployed API origin (e.g. the HF Space URL).
const BASE_URL = import.meta.env.VITE_API_URL ?? '/api'

// Field names mirror stockrag.factor_engine.report.FactorReport exactly —
// ratios come back as fractions (roe 1.52 = 152%), not percentages.
export interface FactorReport {
  ticker: string
  cik: number
  fiscal_year_end: string | null
  price: number | null
  market_cap: number | null
  beta: number | null
  revenue: number | null
  revenue_growth: number | null
  net_margin: number | null
  roe: number | null
  eps: number | null
  pe_ratio: number | null
  free_cash_flow: number | null
  p_fcf_ratio: number | null
  piotroski_score: number | null
  piotroski_signals: Record<string, boolean | null>
  gross_profitability: number | null
  book_to_market: number | null
  momentum_12_1: number | null
  checks: Record<string, boolean | null>
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

export interface IngestResponse {
  ticker: string
  filings_ingested: number
  filings_skipped: number
  chunks_added: number
}

/** Error carrying the HTTP status, so callers can react to e.g. 403. */
export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const UNREACHABLE = "Can't reach the API. Check that the server is running, then try again."

/** FastAPI returns {"detail": "..."} on 4xx; validation errors return a list. */
async function readDetail(res: Response): Promise<string | null> {
  try {
    const body = await res.json()
    const detail = body?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0]
      if (typeof first?.msg === 'string') return first.msg
    }
  } catch {
    // body was not JSON
  }
  return null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE_URL}${path}`, init)
  } catch {
    throw new ApiError(UNREACHABLE, 0)
  }
  if (!res.ok) {
    const detail = await readDetail(res)
    let message: string
    if (detail) message = detail
    else if (res.status >= 500) message = `The server hit an error (${res.status}). Try again in a moment.`
    else message = `The request failed (${res.status} ${res.statusText}).`
    throw new ApiError(message, res.status)
  }
  try {
    return (await res.json()) as T
  } catch {
    throw new ApiError('The server sent a response the app could not read.', res.status)
  }
}

export async function getFactors(ticker: string): Promise<FactorReport> {
  return request<FactorReport>(`/factors/${encodeURIComponent(ticker)}`)
}

export async function ask(question: string, ticker: string, llm?: string): Promise<AskResponse> {
  return request<AskResponse>('/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, ticker, llm }),
  })
}

export async function getThesis(ticker: string, llm?: string): Promise<ThesisResponse> {
  const query = llm ? `?llm=${encodeURIComponent(llm)}` : ''
  return request<ThesisResponse>(`/thesis/${encodeURIComponent(ticker)}${query}`)
}

export async function ingest(ticker: string, token?: string): Promise<IngestResponse> {
  try {
    return await request<IngestResponse>(`/ingest/${encodeURIComponent(ticker)}`, {
      method: 'POST',
      headers: token ? { 'X-Ingest-Token': token } : {},
    })
  } catch (err) {
    if (err instanceof ApiError && err.status === 403) {
      throw new ApiError(
        token
          ? 'The server rejected the ingest token. Check it under "Ingest token" and try again.'
          : 'This server requires an ingest token. Enter it under "Ingest token" and try again.',
        403,
      )
    }
    throw err
  }
}

export async function getMetrics(): Promise<MetricsEntry[]> {
  return request<MetricsEntry[]>('/metrics')
}

export async function getHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/health`)
    return res.ok
  } catch {
    return false
  }
}
