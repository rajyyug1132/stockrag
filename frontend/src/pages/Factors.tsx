import { useState } from 'react'
import { getFactors, type FactorReport } from '../lib/api'

export default function Factors() {
  const [ticker, setTicker] = useState('')
  const [data, setData] = useState<FactorReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleFetch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!ticker.trim()) return

    setLoading(true)
    setError('')
    setData(null)

    try {
      const result = await getFactors(ticker)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch factors')
    } finally {
      setLoading(false)
    }
  }

  // null-safe on purpose: the API omits any field its data source couldn't
  // supply (and lists it under `missing`), so every formatter takes undefined.
  const num = (value: number | null | undefined): string => {
    if (value == null) return '—'
    if (Math.abs(value) > 100) return value.toFixed(0)
    if (Math.abs(value) > 1) return value.toFixed(2)
    return value.toFixed(4)
  }

  const pct = (value: number | null | undefined): string =>
    value == null ? '—' : `${(value * 100).toFixed(1)}%`

  const money = (value: number | null | undefined): string => {
    if (value == null) return '—'
    const abs = Math.abs(value)
    if (abs >= 1e12) return `$${(value / 1e12).toFixed(2)}T`
    if (abs >= 1e9) return `$${(value / 1e9).toFixed(1)}B`
    if (abs >= 1e6) return `$${(value / 1e6).toFixed(1)}M`
    return `$${value.toFixed(2)}`
  }

  const rows: { label: string; value: string; note: string }[] = data
    ? [
        { label: 'ROE', value: pct(data.roe), note: 'Return on equity' },
        { label: 'Net Margin', value: pct(data.net_margin), note: 'Net profit margin' },
        { label: 'Revenue', value: money(data.revenue), note: `FY ending ${data.fiscal_year_end ?? '—'}` },
        { label: 'Revenue Growth', value: pct(data.revenue_growth), note: 'Year over year' },
        { label: 'Free Cash Flow', value: money(data.free_cash_flow), note: 'CFO − capex' },
        { label: 'P/E Ratio', value: num(data.pe_ratio), note: 'Price-to-earnings' },
        { label: 'P/FCF Ratio', value: num(data.p_fcf_ratio), note: 'Price-to-free-cash-flow' },
        { label: 'Gross Profitability', value: num(data.gross_profitability), note: 'Novy-Marx (2013): gross profit / assets' },
        { label: 'Momentum 12-1', value: pct(data.momentum_12_1), note: '12-month return, skipping last month' },
        { label: 'Beta', value: num(data.beta), note: 'Volatility vs. market' },
        { label: 'Market Cap', value: money(data.market_cap), note: 'Price × shares outstanding' },
      ]
    : []

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

  return (
    <div className="flex flex-col gap-8">
      <form onSubmit={handleFetch} className="flex flex-col gap-2">
        <label className="text-xs uppercase tracking-kicker text-ink-faint">Company Ticker</label>
        <div className="flex gap-3">
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="AAPL, MSFT, TSLA, ..."
            maxLength={5}
            className="border border-line px-3 py-2 text-sm font-mono w-48"
          />
          <button
            type="submit"
            disabled={loading || !ticker.trim()}
            className="bg-ink text-bg px-5 py-2 text-sm font-semibold hover:bg-ink-dim disabled:bg-surface disabled:text-ink-faint disabled:cursor-not-allowed"
          >
            {loading ? 'Loading…' : 'Get Factors'}
          </button>
        </div>
      </form>

      {error && (
        <div className="px-3 py-2 border border-err text-err text-sm">
          {error}
        </div>
      )}

      {data && (
        <div className="border-t border-line">
          <div className="grid gap-4 py-6 sm:grid-cols-3">
            <div className="border border-line p-4">
              <p className="text-xs uppercase tracking-kicker text-ink-faint mb-2">Piotroski F-Score</p>
              <p className="font-mono text-3xl text-ink">
                {data.piotroski_score ?? '—'}
                <span className="text-ink-faint text-lg">/9</span>
              </p>
              <p className="text-xs text-ink-faint mt-1">9 accounting signals (Piotroski, 2000)</p>
            </div>
            <div className="sm:col-span-2 border border-line p-4">
              <p className="text-xs uppercase tracking-kicker text-ink-faint mb-3">Flowchart checks</p>
              <ul className="space-y-1.5">
                {Object.entries(data.checks).map(([key, passed]) => (
                  <li key={key} className="text-sm text-ink-dim flex gap-2">
                    <span className={passed ? 'text-ok' : 'text-err'}>{passed ? '✓' : '✗'}</span>
                    {checkLabels[key] ?? key}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="pb-6">
            <p className="text-xs uppercase tracking-kicker text-ink-faint mb-3">F-Score signals</p>
            <ul className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(data.piotroski_signals).map(([key, passed]) => (
                <li key={key} className="text-xs text-ink-dim flex gap-2">
                  <span className={passed ? 'text-ok' : 'text-ink-faint'}>{passed ? '✓' : '✗'}</span>
                  {signalLabels[key] ?? key}
                </li>
              ))}
            </ul>
          </div>

          <table className="w-full border-t border-line">
            <thead>
              <tr>
                <th className="text-xs uppercase tracking-kicker text-ink-faint font-medium px-0 py-3 bg-transparent">Metric</th>
                <th className="text-right text-xs uppercase tracking-kicker text-ink-faint font-medium px-3 py-3 bg-transparent">Value</th>
                <th className="text-left text-xs uppercase tracking-kicker text-ink-faint font-medium px-3 py-3 bg-transparent">Notes</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {rows.map((row) => (
                <tr key={row.label} className="hover:bg-surface transition-colors">
                  <td className="px-0 py-3 font-medium text-ink">{row.label}</td>
                  <td className="px-3 py-3 text-right font-mono text-lg text-ink">{row.value}</td>
                  <td className="px-3 py-3 text-ink-faint">{row.note}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {data.missing.length > 0 && (
            <p className="py-3 text-xs text-ink-faint">
              <span className="uppercase tracking-kicker">Missing data:</span> {data.missing.join(', ')}
            </p>
          )}
        </div>
      )}

      {!data && !error && (
        <p className="text-sm text-ink-faint py-10">
          Enter a ticker to view financial factors from SEC XBRL data.
        </p>
      )}
    </div>
  )
}
