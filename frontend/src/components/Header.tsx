import { useEffect, useState } from 'react'
import { API_BASE, getHealth } from '../lib/api'

type View = 'ask' | 'thesis' | 'factors' | 'metrics'

interface HeaderProps {
  activeView: View
  onViewChange: (view: View) => void
}

const HEALTH_POLL_MS = 15_000

function useApiOnline(): boolean | null {
  const [online, setOnline] = useState<boolean | null>(null)
  useEffect(() => {
    let alive = true
    const check = () => getHealth().then((ok) => alive && setOnline(ok))
    check()
    const id = setInterval(check, HEALTH_POLL_MS)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [])
  return online
}

export default function Header({ activeView, onViewChange }: HeaderProps) {
  const online = useApiOnline()
  const tabs: { id: View; label: string }[] = [
    { id: 'ask', label: 'Ask' },
    { id: 'thesis', label: 'Thesis' },
    { id: 'factors', label: 'Factors' },
    { id: 'metrics', label: 'Metrics' },
  ]

  const statusColor = online === null ? 'text-ink-faint' : online ? 'text-accent' : 'text-err'
  const statusLabel = online === null ? 'API checking' : online ? 'API online' : 'API offline'

  return (
    <header className="border-b border-line bg-bg">
      <div className="max-w-6xl mx-auto px-4 pt-6 pb-0 md:px-6">
        <div className="flex items-baseline justify-between gap-4 mb-5">
          <span className="font-mono text-xl font-semibold text-ink">
            StockRAG<span className="text-accent">.ai</span>
          </span>
          <div className="flex items-baseline gap-5">
            <p className="hidden sm:block text-xs uppercase tracking-kicker text-ink-faint font-mono">
              SEC filings · factors · citations
            </p>
            <span
              title={`API: ${API_BASE}`}
              data-testid="api-status"
              className={`text-xs uppercase tracking-kicker font-mono whitespace-nowrap ${statusColor}`}
            >
              ● {statusLabel}
            </span>
          </div>
        </div>
        {online === false && (
          <p className="-mt-3 mb-4 text-xs font-mono text-ink-faint">
            Start it from the repo root:{' '}
            <code className="text-ink-dim">
              uv run uvicorn stockrag.api.main:app --app-dir src --port 8000 --env-file .env
            </code>
          </p>
        )}
        <nav className="flex gap-7">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => onViewChange(tab.id)}
              className={`pb-3 text-sm font-mono uppercase tracking-kicker border-b-2 transition-colors ${
                activeView === tab.id
                  ? 'border-accent text-accent'
                  : 'border-transparent text-ink-faint hover:text-ink-dim'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>
    </header>
  )
}
