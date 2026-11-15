import { motion } from 'motion/react'

export type View = 'ask' | 'thesis' | 'factors' | 'metrics'

interface HeaderProps {
  activeView: View
  onViewChange: (view: View) => void
}

const TABS: { id: View; label: string }[] = [
  { id: 'ask', label: 'Ask' },
  { id: 'thesis', label: 'Thesis' },
  { id: 'factors', label: 'Factors' },
  { id: 'metrics', label: 'Metrics' },
]

export default function Header({ activeView, onViewChange }: HeaderProps) {
  return (
    <header className="border-b border-line bg-bg">
      <div className="max-w-6xl mx-auto px-4 pt-6 pb-0 md:px-6">
        <div className="flex items-baseline justify-between mb-5 gap-4">
          <h1 className="text-4xl font-bold tracking-tightest text-ink">StockRAG</h1>
          <p className="text-xs uppercase tracking-kicker text-ink-faint text-right">
            SEC filings · factors · citations
          </p>
        </div>
        <nav className="flex gap-7">
          {TABS.map((tab) => {
            const active = activeView === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => onViewChange(tab.id)}
                aria-current={active ? 'page' : undefined}
                className={`relative pb-3 text-sm font-medium uppercase tracking-kicker transition-colors ${
                  active ? 'text-ink' : 'text-ink-faint hover:text-ink-dim'
                }`}
              >
                {tab.label}
                {active && (
                  <motion.span
                    layoutId="tab-underline"
                    className="absolute left-0 right-0 -bottom-px h-0.5 bg-ink"
                    transition={{ type: 'spring', stiffness: 500, damping: 40 }}
                  />
                )}
              </button>
            )
          })}
        </nav>
      </div>
    </header>
  )
}
