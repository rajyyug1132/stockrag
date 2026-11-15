import { useCallback, useEffect, useState } from 'react'
import { getMetrics, type MetricsEntry } from '../lib/api'
import { Notice } from '../components/Notice'

const PAGE = 20

/** 850 -> "850 ms", 12400 -> "12.4 s", 143000 -> "2m 23s". */
function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`
  const s = ms / 1000
  if (s < 60) return `${s.toFixed(1)} s`
  const total = Math.round(s)
  return `${Math.floor(total / 60)}m ${(total % 60).toString().padStart(2, '0')}s`
}

const median = (xs: number[]): number => {
  const sorted = [...xs].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

const pad = (n: number) => n.toString().padStart(2, '0')

const clock = (d: Date) => `${pad(d.getHours())}:${pad(d.getMinutes())}`

/** "14 Nov, 09:32" in local time. */
const shortStamp = (iso: string): string => {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return `${d.getDate()} ${d.toLocaleString('en-GB', { month: 'short' })}, ${clock(d)}`
}

type Status = 'ok' | 'refused' | 'error'

const STATUS: Record<Status, { glyph: string; cls: string }> = {
  ok: { glyph: '✓', cls: 'text-ok' },
  refused: { glyph: '!', cls: 'text-warn' },
  error: { glyph: '✗', cls: 'text-err' },
}

const TH = 'text-xs uppercase tracking-kicker text-ink-faint font-medium px-2 sm:px-3 py-3 bg-transparent whitespace-nowrap'

export default function Metrics({ active }: { active: boolean }) {
  const [entries, setEntries] = useState<MetricsEntry[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [shown, setShown] = useState(PAGE)
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getMetrics()
      setEntries(Array.isArray(data) ? data : [])
      setUpdatedAt(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Metrics could not be loaded. Try again.')
    } finally {
      setLoading(false)
    }
  }, [])

  // Fetch whenever the view is opened (not on app load), so a question just
  // asked on the Ask tab is already in the list.
  useEffect(() => {
    if (active) load()
  }, [active, load])

  const list = entries ?? []
  const hasData = list.length > 0
  const latencies = list.filter((e) => e.total_ms != null).map((e) => e.total_ms as number)
  const failures = list.filter((e) => e.error || e.refused).length

  const stats = [
    { label: 'Total queries', value: hasData ? list.length.toLocaleString() : '—' },
    { label: 'Success rate', value: hasData ? `${(((list.length - failures) / list.length) * 100).toFixed(1)}%` : '—' },
    { label: 'Median latency', value: latencies.length ? formatDuration(median(latencies)) : '—' },
    { label: 'Unique tickers', value: hasData ? new Set(list.map((e) => e.ticker)).size.toLocaleString() : '—' },
  ]

  const visible = list.slice(0, shown)
  const slowest = Math.max(1, ...visible.map((e) => e.total_ms ?? 0))

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <p className="text-xs text-ink-faint">
          Every Ask request the server has recorded, newest first.
        </p>
        <div className="flex items-center gap-3">
          {updatedAt && (
            <span className="text-xs text-ink-faint">
              Updated <span className="font-mono tabular-nums">{clock(updatedAt)}</span>
            </span>
          )}
          <button type="button" onClick={load} disabled={loading} className="btn-secondary py-1 px-3 text-xs">
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>

      <dl className="grid grid-cols-2 md:grid-cols-4 gap-px bg-line border border-line">
        {stats.map((stat) => (
          <div key={stat.label} className="bg-bg p-4 min-w-0">
            <dt className="kicker mb-2">{stat.label}</dt>
            <dd className="text-2xl font-semibold tracking-tightest text-ink font-mono tabular-nums truncate">
              {loading && !entries ? '—' : stat.value}
            </dd>
          </div>
        ))}
      </dl>

      {error && <Notice action={{ label: 'Retry', onClick: load }}>{error}</Notice>}

      {loading && !entries ? (
        <p role="status" className="text-sm text-ink-faint py-6">
          Loading metrics…
        </p>
      ) : entries && !hasData ? (
        <p className="text-sm text-ink-dim py-6">No queries recorded yet. Ask a question and it will show up here.</p>
      ) : hasData ? (
        <div className="flex flex-col gap-4">
          <div className="overflow-x-auto">
            <table className="sm:min-w-[680px] text-sm">
              <thead>
                <tr>
                  <th className={`${TH} pl-0 text-left`}>Time</th>
                  <th className={`${TH} text-left`}>Ticker</th>
                  <th className={`${TH} text-left hidden sm:table-cell`}>Model</th>
                  <th className={`${TH} text-left`}>Latency</th>
                  <th className={`${TH} text-right hidden sm:table-cell`}>Coverage</th>
                  <th className={`${TH} text-left`}>Status</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((entry, i) => {
                  const status: Status = entry.error ? 'error' : entry.refused ? 'refused' : 'ok'
                  const split =
                    entry.retrieval_ms != null && entry.llm_ms != null
                      ? `Retrieval ${formatDuration(entry.retrieval_ms)} · LLM ${formatDuration(entry.llm_ms)}`
                      : undefined
                  const width = entry.total_ms != null ? Math.max(1, (entry.total_ms / slowest) * 100) : 0
                  return (
                    <tr key={`${entry.timestamp}-${i}`} className="hover:bg-surface transition-colors">
                      <td className="pl-0 pr-2 sm:pr-3 py-3 text-xs font-mono tabular-nums text-ink-dim whitespace-nowrap" title={entry.timestamp}>
                        {shortStamp(entry.timestamp)}
                      </td>
                      <td className="px-2 sm:px-3 py-3 font-mono font-semibold text-ink" title={entry.model}>{entry.ticker}</td>
                      <td className="hidden sm:table-cell px-3 py-3 text-xs font-mono text-ink-dim" title={entry.model}>
                        <span className="block max-w-[11rem] truncate">{entry.model ?? '—'}</span>
                      </td>
                      <td className="px-2 sm:px-3 py-3 w-20 sm:w-48" title={split}>
                        {entry.total_ms != null ? (
                          <div className="flex flex-col gap-1">
                            <span className="font-mono tabular-nums text-ink whitespace-nowrap">
                              {formatDuration(entry.total_ms)}
                            </span>
                            <span aria-hidden="true" className="block h-1 w-full">
                              <span className="block h-1 bg-ink-dim" style={{ width: `${width}%` }} />
                            </span>
                          </div>
                        ) : (
                          <span className="font-mono text-ink-faint">—</span>
                        )}
                      </td>
                      <td className="hidden sm:table-cell px-3 py-3 text-right font-mono tabular-nums text-ink">
                        {entry.citation_coverage != null ? `${(entry.citation_coverage * 100).toFixed(0)}%` : '—'}
                      </td>
                      <td
                        className="pl-2 pr-0 sm:px-3 py-3 text-xs font-mono whitespace-nowrap"
                        title={entry.error || undefined}
                      >
                        <span className={STATUS[status].cls}>
                          <span aria-hidden="true">{STATUS[status].glyph} </span>
                          {status}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <span className="text-xs text-ink-faint">
              Showing <span className="font-mono tabular-nums">{visible.length}</span> of{' '}
              <span className="font-mono tabular-nums">{list.length}</span>
            </span>
            {list.length > shown && (
              <button type="button" onClick={() => setShown((n) => n + PAGE)} className="btn-secondary py-1 px-3 text-xs">
                Show {Math.min(PAGE, list.length - shown)} more
              </button>
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}
