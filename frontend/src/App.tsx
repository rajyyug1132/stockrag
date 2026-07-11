import { useState } from 'react'
import Header from './components/Header'
import Ask from './pages/Ask'
import Factors from './pages/Factors'
import Metrics from './pages/Metrics'
import Thesis from './pages/Thesis'

type View = 'ask' | 'thesis' | 'factors' | 'metrics'

export default function App() {
  const [view, setView] = useState<View>('ask')

  return (
    <div className="min-h-screen flex flex-col bg-bg">
      <Header activeView={view} onViewChange={setView} />
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-8 md:px-6 md:py-10">
        {view === 'ask' && <Ask />}
        {view === 'thesis' && <Thesis />}
        {view === 'factors' && <Factors />}
        {view === 'metrics' && <Metrics />}
      </main>
      <footer className="border-t border-line py-4 px-4 text-xs text-ink-faint">
        <div className="max-w-6xl mx-auto flex justify-between">
          <span>StockRAG © 2026</span>
          <a href="https://github.com/rajyyug1132/stockrag" className="hover:text-ink-dim transition-colors">
            GitHub
          </a>
        </div>
      </footer>
    </div>
  )
}
