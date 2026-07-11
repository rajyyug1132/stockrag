import { useState } from 'react'
import { getFactors, FactorReport } from '../lib/api'

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
    if (typeof value === 'number') {
      if (value > 100) return value.toFixed(0)
      if (value > 1) return value.toFixed(2)
      return value.toFixed(4)
    }
    return String(value)
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleFetch} className="flex flex-col gap-2">
        <label className="text-sm font-medium">Company Ticker</label>
        <div className="flex gap-2">
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="AAPL, MSFT, TSLA, ..."
            maxLength={5}
            className="border border-gray-300 px-3 py-2 text-sm flex-1"
          />
          <button
            type="submit"
            disabled={loading || !ticker.trim()}
            className="bg-accent text-white px-4 py-2 text-sm font-medium hover:bg-blue-600 disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {loading ? 'Loading...' : 'Get Factors'}
          </button>
        </div>
      </form>

      {error && (
        <div className="p-3 bg-white border border-red-300 text-red-600 text-sm rounded">
          {error}
        </div>
      )}

      {data && (
        <div className="border border-gray-300 overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-300 bg-gray-50">
                <th className="text-left px-3 py-2 text-sm font-bold">Metric</th>
                <th className="text-right px-3 py-2 text-sm font-bold">Value</th>
                <th className="text-left px-3 py-2 text-sm font-bold text-gray-600">Notes</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              <tr className="border-b border-gray-300 hover:bg-gray-50">
                <td className="px-3 py-2 font-medium">ROE</td>
                <td className="px-3 py-2 text-right font-mono">{formatMetric(data.roe_pct)}%</td>
                <td className="px-3 py-2 text-gray-600">Return on equity</td>
              </tr>
              <tr className="border-b border-gray-300 hover:bg-gray-50">
                <td className="px-3 py-2 font-medium">Net Margin</td>
                <td className="px-3 py-2 text-right font-mono">{formatMetric(data.net_margin_pct)}%</td>
                <td className="px-3 py-2 text-gray-600">Net profit margin</td>
              </tr>
              <tr className="border-b border-gray-300 hover:bg-gray-50">
                <td className="px-3 py-2 font-medium">P/E Ratio</td>
                <td className="px-3 py-2 text-right font-mono">{formatMetric(data.pe_ratio)}</td>
                <td className="px-3 py-2 text-gray-600">Price-to-earnings</td>
              </tr>
              <tr className="border-b border-gray-300 hover:bg-gray-50">
                <td className="px-3 py-2 font-medium">Piotroski F-Score</td>
                <td className="px-3 py-2 text-right font-mono">{formatMetric(data.piotroski_score)}/9</td>
                <td className="px-3 py-2 text-gray-600">Financial health score</td>
              </tr>
              <tr className="border-b border-gray-300 hover:bg-gray-50">
                <td className="px-3 py-2 font-medium">Beta</td>
                <td className="px-3 py-2 text-right font-mono">{formatMetric(data.beta)}</td>
                <td className="px-3 py-2 text-gray-600">Volatility vs. market</td>
              </tr>
            </tbody>
          </table>

          {data.missing.length > 0 && (
            <div className="px-3 py-2 bg-gray-50 border-t border-gray-300 text-xs text-gray-600">
              <strong>Missing data:</strong> {data.missing.join(', ')}
            </div>
          )}
        </div>
      )}

      {!data && !error && (
        <p className="text-sm text-gray-500 text-center py-8">
          Enter a ticker to view financial factors from SEC XBRL data.
        </p>
      )}
    </div>
  )
}
