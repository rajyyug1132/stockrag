import { useState, useEffect } from 'react'
import { getMetrics, type MetricsEntry } from '../lib/api'

export default function Metrics() {
  const [entries, setEntries] = useState<MetricsEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const data = await getMetrics()
        setEntries(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load metrics')
      } finally {
        setLoading(false)
      }
    }
    fetchMetrics()
  }, [])

  const latencies = entries.filter(e => e.total_ms != null).map(e => e.total_ms as number)
  const stats = {
    totalQueries: entries.length,
    successRate: entries.length > 0
      ? (((entries.length - entries.filter(e => e.error || e.refused).length) / entries.length) * 100).toFixed(1)
      : 0,
    avgLatency: latencies.length > 0
      ? (latencies.reduce((a, b) => a + b, 0) / latencies.length).toFixed(0)
      : 0,
    uniqueTickers: new Set(entries.map(e => e.ticker)).size,
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Total Queries', value: stats.totalQueries },
          { label: 'Success Rate', value: `${stats.successRate}%` },
          { label: 'Avg Latency', value: `${stats.avgLatency}ms` },
          { label: 'Unique Tickers', value: stats.uniqueTickers },
        ].map((stat) => (
          <div key={stat.label} className="border border-gray-300 p-3 bg-gray-50">
            <p className="text-xs text-gray-600 mb-1">{stat.label}</p>
            <p className="text-lg font-bold text-black font-mono">{stat.value}</p>
          </div>
        ))}
      </div>

      {error && (
        <div className="p-3 bg-white border border-red-300 text-red-600 text-sm rounded">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-gray-500 text-center py-8">Loading metrics...</p>
      ) : entries.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-8">No queries recorded yet.</p>
      ) : (
        <div className="border border-gray-300 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-300 bg-gray-50">
                <th className="text-left px-3 py-2 font-bold">Timestamp</th>
                <th className="text-left px-3 py-2 font-bold">Ticker</th>
                <th className="text-left px-3 py-2 font-bold">Model</th>
                <th className="text-right px-3 py-2 font-bold">Latency (ms)</th>
                <th className="text-right px-3 py-2 font-bold">Coverage</th>
                <th className="text-center px-3 py-2 font-bold">Status</th>
              </tr>
            </thead>
            <tbody>
              {entries.slice(0, 20).map((entry, i) => {
                const status = entry.error ? 'error' : entry.refused ? 'refused' : 'ok'
                return (
                  <tr key={i} className="border-b border-gray-300 hover:bg-gray-50">
                    <td className="px-3 py-2 text-xs font-mono text-gray-600">
                      {new Date(entry.timestamp).toLocaleString()}
                    </td>
                    <td className="px-3 py-2 font-mono font-bold">{entry.ticker}</td>
                    <td className="px-3 py-2 text-xs font-mono text-gray-600">{entry.model ?? '—'}</td>
                    <td className="px-3 py-2 text-right font-mono">{entry.total_ms ?? '—'}</td>
                    <td className="px-3 py-2 text-right font-mono">
                      {entry.citation_coverage != null ? `${(entry.citation_coverage * 100).toFixed(0)}%` : '—'}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className={`inline-block px-2 py-1 rounded text-xs font-bold ${
                        status === 'ok' ? 'bg-green-100 text-green-700' :
                        status === 'refused' ? 'bg-yellow-100 text-yellow-700' :
                        'bg-red-100 text-red-700'
                      }`}>
                        {status}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {entries.length > 20 && (
            <div className="px-3 py-2 bg-gray-50 border-t border-gray-300 text-xs text-gray-600">
              Showing 20 of {entries.length} queries
            </div>
          )}
        </div>
      )}
    </div>
  )
}
