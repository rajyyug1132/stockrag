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
    <header className="border-b border-gray-300 bg-white">
      <div className="max-w-6xl mx-auto px-4 py-4 md:px-6">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-bold text-black">StockRAG</h1>
          <p className="text-xs text-gray-600">SEC filings • factors • citations</p>
        </div>
        <nav className="flex gap-6 border-t border-gray-300 pt-3">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => onViewChange(tab.id)}
              className={`pb-2 px-1 text-sm font-medium border-b-2 transition-colors ${
                activeView === tab.id
                  ? 'border-accent text-accent'
                  : 'border-transparent text-gray-600 hover:text-black'
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
