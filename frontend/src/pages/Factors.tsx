import { useState } from 'react'
import type { FormEvent } from 'react'
import { getFactors, type FactorReport } from '../lib/api'
import { Notice } from '../components/Notice'
import { TickerField } from '../components/TickerField'

interface PageProps {
  ticker: string
  onTickerChange: (ticker: string) => void
}

// null-safe on purpose: the API omits any field its data source couldn't
// supply (and lists it under `missing`), so every formatter takes undefined.
const num = (value: number | null | undefined): string => {
  if (value == null) return '—'
  return Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(2)
}

const pct = (value: number | null | undefined): string => (value == null ? '—' : `${(value * 100).toFixed(1)}%`)

const dollars = (value: number | null | undefined): string => (value == null ? '—' : `$${value.toFixed(2)}`)

const money = (value: number | null | undefined): string => {
  if (value == null) return '—'
  const abs = Math.abs(value)
  if (abs >= 1e12) return `$${(value / 1e12).toFixed(2)}T`
  if (abs >= 1e9) return `$${(value / 1e9).toFixed(1)}B`
  if (abs >= 1e6) return `$${(value / 1e6).toFixed(1)}M`
  return `$${value.toFixed(2)}`
}

const signalLabels: Record<string, string> = {
  positive_roa: 'Positive ROA',
  positive_cfo: 'Positive operating cash flow',
  roa_improving: 'ROA improving',
  cfo_exceeds_net_income: 'CFO > net income',
  leverage_decreasing: 'Leverage decreasing',
  current_ratio_improving: 'Current ratio improving',
  no_dilution: 'No share dilution',
  gross_margin_improving: 'Gross margin improving',
  asset_turnover_improving: 'Asset turnover improving',
}

const checkLabels: Record<string, string> = {
  roe_gt_15pct: 'ROE > 15%',
  net_margin_gt_10pct: 'Net margin > 10%',
  f_score_ge_7: 'F-Score ≥ 7',
}

const fieldLabels: Record<string, string> = {
  roe: 'ROE',
  net_margin: 'net margin',
  revenue: 'revenue',
  revenue_growth: 'revenue growth',
  free_cash_flow: 'free cash flow',
  pe_ratio: 'P/E ratio',
  p_fcf_ratio: 'P/FCF ratio',
  gross_profitability: 'gross profitability',
  book_to_market: 'book-to-market',
  momentum_12_1: 'momentum 12-1',
  market_cap: 'market cap',
  eps: 'EPS',
  price: 'price',
  beta: 'beta',
  fiscal_year_end: 'fiscal year end',
  piotroski_score: 'F-Score',
  fundamentals: 'fundamentals (no XBRL data found)',
  insufficient_fiscal_years: 'prior fiscal year (growth and F-Score need two years)',
}

const humanizeField = (key: string): string =>
  fieldLabels[key] ?? signalLabels[key] ?? key.replace(/_/g, ' ')

const humanizeKey = (key: string): string => key.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())

type Tri = boolean | null

/** ✓ pass / ✗ fail / – no data. `null` means the input data was missing. */
function TriState({ value, label, failClass }: { value: Tri; label: string; failClass: string }) {
  const glyph = value === true ? '✓' : value === false ? '✗' : '–'
  const cls = value === true ? 'text-ok' : value === false ? failClass : 'text-ink-faint'
  const state = value === true ? 'pass' : value === false ? 'fail' : 'no data'
  return (
    <li className="flex gap-2">
      <span className={`${cls} w-3 shrink-0 text-center`} aria-hidden="true">
        {glyph}
      </span>
      <span>
        {label}
        <span className="sr-only">: {state}</span>
        {value === null && <span className="text-ink-faint"> · no data</span>}
      </span>
    </li>
  )
}

function FScoreMeter({ signals }: { signals: [string, Tri][] }) {
  const passed = signals.filter(([, v]) => v === true).length
  const noData = signals.filter(([, v]) => v === null).length
  const label = `${passed} of ${signals.length} signals passed${noData ? `, ${noData} with no data` : ''}`
  return (
    <div role="img" aria-label={label} className="flex gap-[2px] mt-3 max-w-[14rem]">
      {signals.map(([key, v]) => {
        const state = v === true ? 'passed' : v === false ? 'failed' : 'no data'
        const cls =
          v === true ? 'bg-ink' : v === false ? 'bg-line' : 'bg-transparent border border-dashed border-ink-faint'
        return <span key={key} title={`${signalLabels[key] ?? humanizeKey(key)}: ${state}`} className={`flex-1 h-1.5 ${cls}`} />
      })}
    </div>
  )
}

interface Row {
  label: string
  value: string
  note: string
}

function groups(d: FactorReport): { title: string; rows: Row[] }[] {
  return [
    {
      title: 'Profitability',
      rows: [
        { label: 'ROE', value: pct(d.roe), note: 'Return on equity' },
        { label: 'Net margin', value: pct(d.net_margin), note: 'Net income / revenue' },
        { label: 'Gross profitability', value: num(d.gross_profitability), note: 'Gross profit / assets (Novy-Marx, 2013)' },
      ],
    },
    {
      title: 'Growth & cash',
      rows: [
        { label: 'Revenue', value: money(d.revenue), note: 'Latest fiscal year' },
        { label: 'Revenue growth', value: pct(d.revenue_growth), note: 'Year over year' },
        { label: 'Free cash flow', value: money(d.free_cash_flow), note: 'Operating cash flow − capex' },
      ],
    },
    {
      title: 'Valuation',
      rows: [
        { label: 'Price', value: dollars(d.price), note: 'Latest share price' },
        { label: 'EPS', value: dollars(d.eps), note: 'Diluted earnings per share' },
        { label: 'P/E ratio', value: num(d.pe_ratio), note: 'Price / earnings' },
        { label: 'P/FCF ratio', value: num(d.p_fcf_ratio), note: 'Price / free cash flow' },
        { label: 'Book-to-market', value: num(d.book_to_market), note: 'Book equity / market cap' },
        { label: 'Market cap', value: money(d.market_cap), note: 'Price × shares outstanding' },
      ],
    },
    {
      title: 'Market',
      rows: [
        { label: 'Momentum 12-1', value: pct(d.momentum_12_1), note: '12-month return, skipping the last month' },
        { label: 'Beta', value: num(d.beta), note: 'Volatility against the market' },
      ],
    },
  ]
}

function MetricTable({ title, rows }: { title: string; rows: Row[] }) {
  return (
    <table className="table-fixed border-t border-line">
      <caption className="kicker text-left pt-6 pb-3">{title}</caption>
      <colgroup>
        <col className="w-[62%] sm:w-[30%]" />
        <col className="w-[38%] sm:w-[22%]" />
        <col className="sm:w-[48%]" />
      </colgroup>
      <tbody className="text-sm">
        {rows.map((row) => (
          <tr key={row.label} className="hover:bg-surface transition-colors align-top">
            <th scope="row" className="bg-transparent border-b border-line px-0 py-3 font-medium text-ink">
              {row.label}
              <span className="block sm:hidden text-xs font-normal text-ink-faint mt-0.5">{row.note}</span>
            </th>
            <td className="pl-3 pr-0 sm:pr-3 py-3 text-right font-mono tabular-nums text-lg text-ink">{row.value}</td>
            <td className="hidden sm:table-cell px-3 py-3 text-ink-faint">{row.note}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Skeleton() {
  return (
    <div aria-hidden="true" className="border-t border-line">
      <div className="h-4 w-48 bg-surface mt-6" />
      <div className="grid gap-4 py-6 sm:grid-cols-3">
        <div className="border border-line p-4 space-y-3">
          <div className="h-3 w-28 bg-surface" />
          <div className="h-8 w-16 bg-surface" />
          <div className="h-1.5 w-full max-w-[14rem] bg-surface" />
        </div>
        <div className="sm:col-span-2 border border-line p-4 space-y-3">
          <div className="h-3 w-32 bg-surface" />
          <div className="h-3 w-40 bg-surface" />
          <div className="h-3 w-36 bg-surface" />
          <div className="h-3 w-28 bg-surface" />
        </div>
      </div>
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex justify-between gap-4 py-3 border-b border-line">
          <div className="h-4 w-32 bg-surface" />
          <div className="h-4 w-20 bg-surface" />
        </div>
      ))}
    </div>
  )
}

export default function Factors({ ticker, onTickerChange }: PageProps) {
  const [data, setData] = useState<FactorReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = async () => {
    if (!ticker.trim() || loading) return
    setLoading(true)
    setError('')
    setData(null)
    try {
      setData(await getFactors(ticker))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The factor report could not be loaded. Try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleFetch = (e: FormEvent) => {
    e.preventDefault()
    load()
  }

  const signals = data ? (Object.entries(data.piotroski_signals) as [string, Tri][]) : []

  return (
    <div className="flex flex-col gap-8">
      <form onSubmit={handleFetch} className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-x-4 gap-y-3 items-end">
          <TickerField id="factors-ticker" value={ticker} onChange={onTickerChange} />
          <button type="submit" disabled={loading || !ticker.trim()} className="btn-primary">
            {loading ? 'Loading…' : 'Get factors'}
          </button>
        </div>
        <p className="text-xs text-ink-faint">Computed from SEC XBRL data. No ingest needed.</p>
      </form>

      {error && <Notice action={{ label: 'Retry', onClick: load }}>{error}</Notice>}

      {loading && (
        <div role="status" aria-label={`Loading factor report for ${ticker}`}>
          <Skeleton />
        </div>
      )}

      {data && (
        <div className="border-t border-line">
          <h2 className="pt-6 text-sm font-medium tracking-normal text-ink-dim">
            <span className="font-mono text-ink">{data.ticker}</span>
            <span className="text-ink-faint">
              {' '}
              · FY ending <span className="font-mono tabular-nums">{data.fiscal_year_end ?? 'unknown'}</span>
            </span>
          </h2>

          <div className="grid gap-4 py-6 sm:grid-cols-3">
            <div className="border border-line p-4">
              <p className="kicker mb-2">Piotroski F-Score</p>
              <p className="font-mono tabular-nums text-3xl text-ink">
                {data.piotroski_score ?? '—'}
                <span className="text-ink-faint text-lg">/9</span>
              </p>
              {signals.length > 0 && <FScoreMeter signals={signals} />}
              <p className="text-xs text-ink-faint mt-3">9 accounting signals (Piotroski, 2000)</p>
            </div>
            <div className="sm:col-span-2 border border-line p-4">
              <p className="kicker mb-3">Flowchart checks</p>
              <ul className="space-y-1.5 text-sm text-ink-dim">
                {Object.entries(data.checks).map(([key, passed]) => (
                  <TriState key={key} value={passed} label={checkLabels[key] ?? humanizeKey(key)} failClass="text-err" />
                ))}
              </ul>
            </div>
          </div>

          <div className="pb-2">
            <p className="kicker mb-3">F-Score signals</p>
            <ul className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2 lg:grid-cols-3 text-xs text-ink-dim">
              {signals.map(([key, passed]) => (
                <TriState
                  key={key}
                  value={passed}
                  label={signalLabels[key] ?? humanizeKey(key)}
                  failClass="text-ink-faint"
                />
              ))}
            </ul>
          </div>

          {groups(data).map((g) => (
            <MetricTable key={g.title} title={g.title} rows={g.rows} />
          ))}

          {data.missing.length > 0 && (
            <p className="py-4 text-xs text-ink-faint">
              <span className="uppercase tracking-kicker">Missing data:</span>{' '}
              {data.missing.map(humanizeField).join(', ')}
            </p>
          )}
        </div>
      )}

      {!data && !error && !loading && (
        <p className="text-sm text-ink-dim py-6 max-w-[72ch]">
          Enter a ticker and select Get factors to see profitability, growth, valuation and the Piotroski F-Score,
          computed from SEC XBRL data.
        </p>
      )}
    </div>
  )
}
