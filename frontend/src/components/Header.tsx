type View = 'ask' | 'thesis' | 'factors' | 'metrics'

interface HeaderProps {
  activeView: View
  onViewChange: (view: View) => void
}

export default function Header({ activeView, onViewChange }: HeaderProps) {
  const tabs: { id: View; label: string }[] = [
    { id: 'ask', label: 'Ask' },
    { id: 'thesis', label: 'Thesis' },
    { id: 'factors', label: 'Factors' },
    { id: 'metrics', label: 'Metrics' },
  ]

  return (
    <header className="border-b border-line bg-bg">
      <div className="max-w-6xl mx-auto px-4 pt-6 pb-0 md:px-6">
        <div className="flex items-baseline justify-between mb-5">
          <span className="font-mono text-xl font-semibold text-ink">
            StockRAG<span className="text-accent">.ai</span>
          </span>
          <p className="text-xs uppercase tracking-kicker text-ink-faint font-mono">
            SEC filings · factors · citations
          </p>
        </div>
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
