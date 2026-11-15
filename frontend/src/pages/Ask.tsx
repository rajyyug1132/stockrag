import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ask, ingest } from '../lib/api'
import type { Source } from '../lib/api'
import { Markdown } from '../components/Markdown'
import { fade, fadeUp, Pending, stagger } from '../components/motion'

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
}

export default function Ask() {
  const [ticker, setTicker] = useState('')
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [ingesting, setIngesting] = useState(false)
  const [ingestStatus, setIngestStatus] = useState('')
  const [ingestToken, setIngestToken] = useState('')
  // '' = whatever the server has configured (LLM_PROVIDER); the API takes a
  // per-request override, so the UI can switch providers without a restart.
  const [llm, setLlm] = useState('')
  const threadEnd = useRef<HTMLDivElement>(null)

  // Keep the newest message (or the pending row) in view.
  useEffect(() => {
    threadEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [messages.length, loading])

  const handleIngest = async () => {
    if (!ticker.trim()) return
    setIngesting(true)
    setIngestStatus('')
    try {
      const r = await ingest(ticker, ingestToken || undefined)
      setIngestStatus(
        r.filings_ingested > 0
          ? `Ingested ${r.filings_ingested} filing(s), ${r.chunks_added} chunks.`
          : 'Already ingested.'
      )
    } catch (err) {
      setIngestStatus(err instanceof Error ? `Ingest failed — ${err.message}` : 'Ingest failed')
    } finally {
      setIngesting(false)
    }
  }

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim() || !ticker.trim()) return

    setLoading(true)
    setError('')

    try {
      const response = await ask(question, ticker, llm || undefined)
      setMessages((prev) => [
        ...prev,
        { role: 'user', content: question },
        { role: 'assistant', content: response.answer, sources: response.sources },
      ])
      setQuestion('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get answer')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-2">
        <label htmlFor="ask-ticker" className="text-xs uppercase tracking-kicker text-ink-faint">Ticker</label>
        <div className="flex gap-3 items-center flex-wrap">
          <input
            id="ask-ticker"
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="AAPL, MSFT, TSLA, ..."
            maxLength={5}
            className="border border-line px-3 py-2 text-sm font-mono w-48"
          />
          <motion.button
            type="button"
            whileTap={{ scale: 0.97 }}
            onClick={handleIngest}
            disabled={ingesting || !ticker.trim()}
            className="border border-line text-ink-dim px-4 py-2 text-sm hover:text-ink hover:border-ink-faint disabled:text-ink-faint disabled:cursor-not-allowed"
          >
            {ingesting ? 'Ingesting…' : 'Ingest filings'}
          </motion.button>
          <input
            type="password"
            value={ingestToken}
            onChange={(e) => setIngestToken(e.target.value)}
            placeholder="ingest token (if required)"
            aria-label="Ingest token"
            className="border border-line px-3 py-2 text-xs w-52"
          />
        </div>
        <AnimatePresence mode="wait">
          {ingesting ? (
            <Pending key="ingesting" message="Fetching filings from EDGAR, chunking, embedding (~1 min)" />
          ) : (
            ingestStatus && (
              <motion.p key="status" variants={fade} initial="hidden" animate="visible" exit="hidden" className="text-xs text-ink-dim">
                {ingestStatus}
              </motion.p>
            )
          )}
        </AnimatePresence>
      </div>

      <div className="border-t border-line pt-8">
        <div className="space-y-6 mb-8 max-h-[28rem] overflow-y-auto pr-1">
          {messages.length === 0 && !loading ? (
            <p className="text-sm text-ink-faint py-10">
              Enter a ticker and ask a question about its SEC filings.
            </p>
          ) : (
            messages.map((msg, i) => (
              <motion.div
                key={i}
                variants={fadeUp}
                initial="hidden"
                animate="visible"
                className={msg.role === 'user' ? 'pl-0' : 'border-l border-line pl-4'}
              >
                <p className="text-xs uppercase tracking-kicker text-ink-faint mb-2">
                  {msg.role === 'user' ? 'You' : 'StockRAG'}
                </p>
                {msg.role === 'user' ? (
                  <p className="text-sm leading-relaxed whitespace-pre-wrap text-ink max-w-[72ch]">
                    {msg.content}
                  </p>
                ) : (
                  <Markdown text={msg.content} />
                )}
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-line">
                    <p className="text-xs uppercase tracking-kicker text-ink-faint mb-2">Sources</p>
                    <motion.ul
                      variants={stagger(msg.sources.length)}
                      initial="hidden"
                      animate="visible"
                      className="space-y-1"
                    >
                      {msg.sources.map((src) => (
                        <motion.li key={src.index} variants={fadeUp} className="text-xs text-ink-dim">
                          <span className="font-mono">[{src.index}]</span>{' '}
                          <span className="font-mono">{src.form}</span> {src.section}
                          <span className="text-ink-faint"> — {src.filing_date}</span>
                        </motion.li>
                      ))}
                    </motion.ul>
                  </div>
                )}
              </motion.div>
            ))
          )}
          {loading && (
            <div className="border-l border-line pl-4">
              <p className="text-xs uppercase tracking-kicker text-ink-faint mb-2">StockRAG</p>
              <Pending message="Retrieving, reranking, generating…" />
            </div>
          )}
          <div ref={threadEnd} />
        </div>

        <AnimatePresence>
          {error && (
            <motion.div
              key="error"
              variants={fadeUp}
              initial="hidden"
              animate="visible"
              exit="hidden"
              role="alert"
              className="mb-4 px-3 py-2 border border-err text-err text-sm"
            >
              {error}
            </motion.div>
          )}
        </AnimatePresence>

        <form onSubmit={handleAsk} className="flex flex-col gap-3">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="What are the key risks? Tell me about debt levels..."
            aria-label="Question"
            rows={3}
            className="border border-line px-3 py-2 text-sm max-w-[72ch]"
          />
          <div className="flex items-center gap-3 flex-wrap">
            <motion.button
              type="submit"
              whileTap={{ scale: 0.97 }}
              disabled={loading || !question.trim() || !ticker.trim()}
              className="bg-ink text-bg px-5 py-2 text-sm font-semibold hover:bg-ink-dim disabled:bg-surface disabled:text-ink-faint disabled:cursor-not-allowed"
            >
              {loading ? 'Asking…' : 'Ask'}
            </motion.button>
            <select
              value={llm}
              onChange={(e) => setLlm(e.target.value)}
              aria-label="Generation model"
              className="border border-line bg-bg text-ink-dim px-3 py-2 text-xs"
            >
              <option value="">server default</option>
              <option value="nvidia">NVIDIA NIM</option>
              <option value="gemini">Gemini</option>
              <option value="ollama">Ollama (local)</option>
            </select>
            <span className="text-xs text-ink-faint">
              Retrieval always runs locally; only generation switches.
            </span>
          </div>
        </form>
      </div>
    </div>
  )
}
