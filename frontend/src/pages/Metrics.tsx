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

  const statusColor = (status: string) =>
    status === 'ok' ? 'text-ok' : status === 'refused' ? 'text-warn' : 'text-err'

  return (
    <div className="flex flex-col gap-8">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-line border border-line">
        {[
          { label: 'Total Queries', value: stats.totalQueries },
          { label: 'Success Rate', value: `${stats.successRate}%` },
          { label: 'Avg Latency', value: `${stats.avgLatency}ms` },
          { label: 'Unique Tickers', value: stats.uniqueTickers },
        ].map((stat, i) => (
          <div key={stat.label} className="animate-item bg-bg p-4" style={{ animationDelay: `${i * 70}ms` }}>
            <p className="text-xs uppercase tracking-kicker text-accent-dim font-mono mb-2">{stat.label}</p>
            <p className="text-2xl font-semibold tracking-tightest text-ink font-mono">{stat.value}</p>
          </div>
        ))}
      </div>

      {error && (
        <div className="px-3 py-2 border border-err text-err text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-ink-faint py-10">Loading metrics…</p>
      ) : entries.length === 0 ? (
        <p className="text-sm text-ink-faint py-10">No queries recorded yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="text-left text-xs uppercase tracking-kicker text-ink-faint font-medium px-0 py-3 bg-transparent">Timestamp</th>
                <th className="text-left text-xs uppercase tracking-kicker text-ink-faint font-medium px-3 py-3 bg-transparent">Ticker</th>
                <th className="text-left text-xs uppercase tracking-kicker text-ink-faint font-medium px-3 py-3 bg-transparent">Model</th>
                <th className="text-right text-xs uppercase tracking-kicker text-ink-faint font-medium px-3 py-3 bg-transparent">Latency (ms)</th>
                <th className="text-right text-xs uppercase tracking-kicker text-ink-faint font-medium px-3 py-3 bg-transparent">Coverage</th>
                <th className="text-left text-xs uppercase tracking-kicker text-ink-faint font-medium px-3 py-3 bg-transparent">Status</th>
              </tr>
            </thead>
            <tbody>
              {entries.slice(0, 20).map((entry, i) => {
                const status = entry.error ? 'error' : entry.refused ? 'refused' : 'ok'
                return (
                  <tr key={i} className="animate-item hover:bg-surface transition-colors" style={{ animationDelay: `${Math.min(i, 8) * 40}ms` }}>
                    <td className="px-0 py-3 text-xs font-mono text-ink-dim">
                      {new Date(entry.timestamp).toLocaleString()}
                    </td>
                    <td className="px-3 py-3 font-mono font-semibold text-ink">{entry.ticker}</td>
                    <td className="px-3 py-3 text-xs font-mono text-ink-dim">{entry.model ?? '—'}</td>
                    <td className="px-3 py-3 text-right font-mono text-ink">{entry.total_ms ?? '—'}</td>
                    <td className="px-3 py-3 text-right font-mono text-ink">
                      {entry.citation_coverage != null ? `${(entry.citation_coverage * 100).toFixed(0)}%` : '—'}
                    </td>
                    <td className={`px-3 py-3 text-xs font-mono uppercase ${statusColor(status)}`}>
                      {status}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {entries.length > 20 && (
            <p className="py-3 text-xs text-ink-faint">
              Showing 20 of {entries.length} queries
            </p>
          )}
        </div>
      )}
    </div>
  )
}
