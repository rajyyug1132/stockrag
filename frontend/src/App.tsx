import { useCallback, useEffect, useState } from 'react'
import Header, { VIEWS, type View } from './components/Header'
import Ask from './pages/Ask'
import Factors from './pages/Factors'
import Metrics from './pages/Metrics'
import Thesis from './pages/Thesis'

const TICKER_KEY = 'stockrag.ticker'

const viewFromHash = (hash: string): View | null => {
  const id = hash.replace(/^#/, '')
  return VIEWS.some((v) => v.id === id) ? (id as View) : null
}

const readTicker = (): string => {
  try {
    return window.localStorage.getItem(TICKER_KEY) ?? ''
  } catch {
    return ''
  }
}

const RAG_STEPS = ['SEC EDGAR', 'section-aware chunking', 'BM25 + vector (RRF)', 'cross-encoder rerank', 'cited answer']

const PIPELINE: Record<View, string[]> = {
  ask: RAG_STEPS,
  thesis: RAG_STEPS,
  factors: ['SEC XBRL companyfacts', 'ratios', 'Piotroski F-Score', 'flowchart checks'],
  metrics: ['requests.jsonl', 'latency', 'citation coverage', 'refusals'],
}

export default function App() {
  const [view, setView] = useState<View>(() => viewFromHash(window.location.hash) ?? 'ask')
  const [ticker, setTickerState] = useState<string>(readTicker)

  useEffect(() => {
    const onHash = () => {
      const next = viewFromHash(window.location.hash)
      if (next) setView(next)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const setTicker = useCallback((value: string) => {
    setTickerState(value)
    try {
      if (value) window.localStorage.setItem(TICKER_KEY, value)
      else window.localStorage.removeItem(TICKER_KEY)
    } catch {
      // storage blocked (private mode); the ticker still works for this session
    }
  }, [])

  const pageProps = { ticker, onTickerChange: setTicker }

  return (
    <div className="min-h-screen flex flex-col bg-bg">
      <Header activeView={view} />
      <div className="border-b border-line">
        <div className="max-w-6xl mx-auto px-4 md:px-6">
          <ol
            aria-label="How this view is computed"
            className="flex items-center gap-3 py-3 pr-8 overflow-x-auto whitespace-nowrap text-xs text-ink-faint [scrollbar-width:none] [mask-image:linear-gradient(to_right,black_calc(100%-2rem),transparent)]"
          >
            {PIPELINE[view].map((step, i) => (
              <li key={step} className="flex items-center gap-3 shrink-0">
                {i > 0 && <span aria-hidden="true">→</span>}
                <span className="uppercase tracking-kicker">{step}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-8 md:px-6 md:py-10">
        <section hidden={view !== 'ask'} aria-label="Ask">
          <Ask {...pageProps} />
        </section>
        <section hidden={view !== 'thesis'} aria-label="Thesis">
          <Thesis {...pageProps} />
        </section>
        <section hidden={view !== 'factors'} aria-label="Factors">
          <Factors {...pageProps} />
        </section>
        <section hidden={view !== 'metrics'} aria-label="Metrics">
          <Metrics active={view === 'metrics'} />
        </section>
      </main>
      <footer className="border-t border-line">
        <div className="max-w-6xl mx-auto px-4 py-4 md:px-6 flex flex-wrap justify-between gap-x-6 gap-y-1 text-xs text-ink-faint">
          <span>StockRAG © 2026 · Not investment advice.</span>
          <a href="https://github.com/rajyyug1132/stockrag" className="hover:text-ink-dim transition-colors">
            GitHub
          </a>
        </div>
      </footer>
    </div>
  )
}
