import { useEffect, useRef, useState } from 'react'
import Header from './components/Header'
import Ask from './pages/Ask'
import Factors from './pages/Factors'
import Metrics from './pages/Metrics'
import Thesis from './pages/Thesis'

type View = 'ask' | 'thesis' | 'factors' | 'metrics'

const VIEWS: { id: View; label: string; hint: string }[] = [
  { id: 'ask', label: 'Ask', hint: 'Question filings with citations' },
  { id: 'thesis', label: 'Thesis', hint: 'Generate an investment thesis' },
  { id: 'factors', label: 'Factors', hint: 'Piotroski F-score and ratios' },
  { id: 'metrics', label: 'Metrics', hint: 'Retrieval quality metrics' },
]

// ponytail: palette only switches views; ticker/filing jump needs ticker state lifted here — add when asked.
function CommandPalette({ onGo, onClose }: { onGo: (v: View) => void; onClose: () => void }) {
  const [q, setQ] = useState('')
  const [sel, setSel] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const hits = VIEWS.filter((v) => v.label.toLowerCase().includes(q.toLowerCase()))

  useEffect(() => inputRef.current?.focus(), [])

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') onClose()
    else if (e.key === 'ArrowDown') setSel((s) => Math.min(s + 1, hits.length - 1))
    else if (e.key === 'ArrowUp') setSel((s) => Math.max(s - 1, 0))
    else if (e.key === 'Enter' && hits[sel]) onGo(hits[sel].id)
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-start justify-center pt-[18vh]" onClick={onClose}>
      <div className="w-full max-w-md border border-line bg-surface shadow-xl rounded-xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => { setQ(e.target.value); setSel(0) }}
          onKeyDown={onKey}
          placeholder="Jump to…"
          className="w-full px-4 py-3 text-sm bg-sunken border-b border-line"
        />
        <ul>
          {hits.map((v, i) => (
            <li key={v.id}>
              <button
                onClick={() => onGo(v.id)}
                onMouseEnter={() => setSel(i)}
                className={`w-full text-left px-4 py-2.5 text-sm flex justify-between ${
                  i === sel ? 'bg-sunken text-accent' : 'text-ink-dim'
                }`}
              >
                <span className="uppercase tracking-kicker text-xs font-medium">{v.label}</span>
                <span className="text-xs text-ink-faint">{v.hint}</span>
              </button>
            </li>
          ))}
          {hits.length === 0 && <li className="px-4 py-3 text-xs text-ink-faint">No match</li>}
        </ul>
      </div>
    </div>
  )
}

// Fixed mint bar tracking page scroll (PageCoder-style). rAF-throttled read.
function ScrollProgress() {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    let ticking = false
    const update = () => {
      ticking = false
      const el = document.documentElement
      const max = el.scrollHeight - el.clientHeight
      const p = max > 0 ? el.scrollTop / max : 0
      if (ref.current) ref.current.style.transform = `scaleX(${p})`
    }
    const onScroll = () => {
      if (!ticking) { requestAnimationFrame(update); ticking = true }
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    update()
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
    }
  }, [])
  return (
    <div className="fixed top-0 left-0 right-0 h-0.5 z-[60] bg-transparent">
      <div ref={ref} className="h-full bg-accent origin-left" style={{ transform: 'scaleX(0)' }} />
    </div>
  )
}

export default function App() {
  const [view, setView] = useState<View>('ask')
  const [paletteOpen, setPaletteOpen] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setPaletteOpen((o) => !o)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="min-h-screen flex flex-col bg-bg">
      <ScrollProgress />
      <Header activeView={view} onViewChange={setView} />
      <main key={view} className="animate-view flex-1 max-w-6xl w-full mx-auto px-4 py-8 md:px-6 md:py-10">
        {view === 'ask' && <Ask />}
        {view === 'thesis' && <Thesis />}
        {view === 'factors' && <Factors />}
        {view === 'metrics' && <Metrics />}
      </main>
      <footer className="border-t border-line py-4 px-4 text-xs text-ink-faint font-mono">
        <div className="max-w-6xl mx-auto flex justify-between">
          <span>StockRAG © 2026 · Ctrl+K to jump</span>
          <a href="https://github.com/rajyyug1132/stockrag" className="hover:text-ink-dim transition-colors">
            GitHub
          </a>
        </div>
      </footer>
      {paletteOpen && (
        <CommandPalette
          onGo={(v) => { setView(v); setPaletteOpen(false) }}
          onClose={() => setPaletteOpen(false)}
        />
      )}
    </div>
  )
}
