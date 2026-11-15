import { useState } from 'react'
import { AnimatePresence, MotionConfig, motion } from 'motion/react'
import Header, { type View } from './components/Header'
import { ease, fadeUp, stagger } from './components/motion'
import Ask from './pages/Ask'
import Factors from './pages/Factors'
import Metrics from './pages/Metrics'
import Thesis from './pages/Thesis'

const PIPELINE = ['SEC EDGAR', 'section-aware chunking', 'BM25 + vector (RRF)', 'cross-encoder rerank', 'cited answer']

export default function App() {
  const [view, setView] = useState<View>('ask')

  return (
    // reducedMotion="user": Motion animates from JS, so the CSS
    // prefers-reduced-motion rule in index.css can't stop it on its own.
    <MotionConfig reducedMotion="user">
      <div className="min-h-screen flex flex-col bg-bg">
        <Header activeView={view} onViewChange={setView} />
        <div className="border-b border-line">
          <motion.div
            variants={stagger(PIPELINE.length, 0.4)}
            initial="hidden"
            animate="visible"
            className="max-w-6xl mx-auto px-4 py-3 md:px-6 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-faint"
          >
            {PIPELINE.map((step, i) => (
              <motion.span key={step} variants={fadeUp} className="flex items-center gap-3">
                {i > 0 && <span aria-hidden="true">→</span>}
                <span className="uppercase tracking-kicker">{step}</span>
              </motion.span>
            ))}
          </motion.div>
        </div>
        <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-8 md:px-6 md:py-10">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={view}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.18, ease }}
            >
              {view === 'ask' && <Ask />}
              {view === 'thesis' && <Thesis />}
              {view === 'factors' && <Factors />}
              {view === 'metrics' && <Metrics />}
            </motion.div>
          </AnimatePresence>
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
    </MotionConfig>
  )
}
