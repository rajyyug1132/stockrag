type View = 'ask' | 'factors' | 'metrics'

interface HeaderProps {
  activeView: View
  onViewChange: (view: View) => void
}

export default function Header({ activeView, onViewChange }: HeaderProps) {
  const tabs: { id: View; label: string }[] = [
    { id: 'ask', label: 'Ask' },
    { id: 'factors', label: 'Factors' },
    { id: 'metrics', label: 'Metrics' },
  ]

  return (
    <header className="border-b border-line bg-bg">
      <div className="max-w-6xl mx-auto px-4 pt-6 pb-0 md:px-6">
        <div className="flex items-baseline justify-between mb-5">
          <h1 className="text-4xl font-bold tracking-tightest text-ink">StockRAG</h1>
          <p className="text-xs uppercase tracking-kicker text-ink-faint">
            SEC filings · factors · citations
          </p>
        </div>
        <nav className="flex gap-7">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => onViewChange(tab.id)}
              className={`pb-3 text-sm font-medium uppercase tracking-kicker border-b-2 transition-colors ${
                activeView === tab.id
                  ? 'border-ink text-ink'
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
