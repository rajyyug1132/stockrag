import { useState } from 'react'
import Header from './components/Header'
import Ask from './pages/Ask'
import Factors from './pages/Factors'
import Metrics from './pages/Metrics'

type View = 'ask' | 'factors' | 'metrics'

export default function App() {
  const [view, setView] = useState<View>('ask')

  return (
    <div className="min-h-screen flex flex-col bg-white">
      <Header activeView={view} onViewChange={setView} />
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-6 md:px-6 md:py-8">
        {view === 'ask' && <Ask />}
        {view === 'factors' && <Factors />}
        {view === 'metrics' && <Metrics />}
      </main>
      <footer className="border-t border-gray-300 text-center py-3 px-4 text-xs text-gray-600">
        <p>StockRAG © 2025 | <a href="https://github.com/rajyyug1132/stockrag" className="text-accent hover:underline">GitHub</a></p>
      </footer>
    </div>
  )
}
