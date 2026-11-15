import { useEffect, useState } from 'react'
import { getHealth } from '../lib/api'

export type View = 'ask' | 'thesis' | 'factors' | 'metrics'

export const VIEWS: { id: View; label: string }[] = [
  { id: 'ask', label: 'Ask' },
  { id: 'thesis', label: 'Thesis' },
  { id: 'factors', label: 'Factors' },
  { id: 'metrics', label: 'Metrics' },
]

type Health = 'checking' | 'online' | 'offline'

function ApiStatus() {
  const [health, setHealth] = useState<Health>('checking')

  useEffect(() => {
    let cancelled = false
    const check = async () => {
      const ok = await getHealth()
      if (!cancelled) setHealth(ok ? 'online' : 'offline')
    }
    check()
    const id = window.setInterval(check, 30_000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [])

  const label = health === 'online' ? 'API online' : health === 'offline' ? 'API offline' : 'Checking…'
  const dot = health === 'online' ? 'bg-ok' : health === 'offline' ? 'bg-err' : 'border border-ink-faint'

  return (
    <p role="status" className="flex items-center gap-2 text-xs text-ink-dim whitespace-nowrap">
      <span aria-hidden="true" className={`inline-block w-2 h-2 rounded-full ${dot}`} />
      {label}
    </p>
  )
}

export default function Header({ activeView }: { activeView: View }) {
  return (
    <header className="border-b border-line bg-bg">
      <div className="max-w-6xl mx-auto px-4 pt-6 pb-0 md:px-6">
        <div className="flex items-baseline justify-between gap-4 mb-5">
          <h1 className="text-4xl font-bold tracking-tightest text-ink">StockRAG</h1>
          <div className="flex items-baseline gap-6">
            <p className="hidden sm:block text-xs uppercase tracking-kicker text-ink-faint">
              SEC filings · factors · citations
            </p>
            <ApiStatus />
          </div>
        </div>
        <nav aria-label="Primary">
          <ul className="flex gap-7">
            {VIEWS.map((tab) => {
              const active = activeView === tab.id
              return (
                <li key={tab.id}>
                  <a
                    href={`#${tab.id}`}
                    aria-current={active ? 'page' : undefined}
                    className={`block pb-3 text-sm font-medium uppercase tracking-kicker border-b-2 transition-colors ${
                      active ? 'border-ink text-ink' : 'border-transparent text-ink-faint hover:text-ink-dim'
                    }`}
                  >
                    {tab.label}
                  </a>
                </li>
              )
            })}
          </ul>
        </nav>
      </div>
    </header>
  )
}
