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

  const formatMetric = (value: number | null): string => {
    if (value === null) return '—'
    if (Math.abs(value) > 100) return value.toFixed(0)
    if (Math.abs(value) > 1) return value.toFixed(2)
    return value.toFixed(4)
  }

  const pct = (ratio: number | null): string =>
    ratio === null ? '—' : `${(ratio * 100).toFixed(1)}%`

  const rows: { label: string; value: string; note: string }[] = data
    ? [
        { label: 'ROE', value: pct(data.roe), note: 'Return on equity' },
        { label: 'Net Margin', value: pct(data.net_margin), note: 'Net profit margin' },
        { label: 'Revenue Growth', value: pct(data.revenue_growth), note: 'YoY revenue change' },
        { label: 'P/E Ratio', value: formatMetric(data.pe_ratio), note: 'Price-to-earnings' },
        { label: 'Piotroski F-Score', value: `${data.piotroski_score ?? '—'}/9`, note: 'Financial health score' },
        { label: 'Beta', value: formatMetric(data.beta), note: 'Volatility vs. market' },
      ]
    : []

  return (
    <div className="flex flex-col gap-8">
      <form onSubmit={handleFetch} className="flex flex-col gap-2">
        <label className="text-xs uppercase tracking-kicker text-accent-dim font-mono">Company Ticker</label>
        <div className="flex gap-3">
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="AAPL, MSFT, TSLA, ..."
            maxLength={5}
            className="text-sm font-mono w-48"
          />
          <button
            type="submit"
            disabled={loading || !ticker.trim()}
            className="bg-accent text-bg px-6 py-2.5 text-sm font-bold rounded-md transition-all hover:brightness-110 hover:-translate-y-px disabled:bg-surface disabled:text-ink-faint disabled:cursor-not-allowed disabled:translate-y-0 disabled:brightness-100"
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
          <table className="w-full">
            <thead>
              <tr>
                <th className="text-xs uppercase tracking-kicker text-ink-faint font-medium px-0 py-3 bg-transparent">Metric</th>
                <th className="text-right text-xs uppercase tracking-kicker text-ink-faint font-medium px-3 py-3 bg-transparent">Value</th>
                <th className="text-left text-xs uppercase tracking-kicker text-ink-faint font-medium px-3 py-3 bg-transparent">Notes</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {rows.map((row, i) => (
                <tr
                  key={row.label}
                  className="animate-item hover:bg-surface transition-colors"
                  style={{ animationDelay: `${i * 60}ms` }}
                >
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
