import { useState } from 'react'
import { askStream, ingest } from '../lib/api'
import type { Source } from '../lib/api'

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

    const q = question
    setQuestion('')
    // Placeholder assistant message that streaming tokens append into.
    setMessages((prev) => [...prev, { role: 'user', content: q }, { role: 'assistant', content: '' }])
    const patchLast = (patch: (last: Message) => Message) =>
      setMessages((prev) => [...prev.slice(0, -1), patch(prev[prev.length - 1])])

    try {
      const response = await askStream(q, ticker, (token) =>
        patchLast((last) => ({ ...last, content: last.content + token }))
      )
      // Server's validated answer wins over the streamed accumulation.
      patchLast(() => ({ role: 'assistant', content: response.answer, sources: response.sources }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get answer')
      // Drop the user turn + empty assistant placeholder; restore the question.
      setMessages((prev) => prev.slice(0, -2))
      setQuestion(q)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-8 max-w-3xl mx-auto w-full">
      <div className="flex flex-col gap-2 border border-line bg-surface p-5 rounded-xl hover-lift">
        <label className="text-xs uppercase tracking-kicker text-accent-dim font-mono">Ticker</label>
        <div className="flex gap-3 items-center flex-wrap">
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="AAPL, MSFT, TSLA, ..."
            maxLength={5}
            className="text-sm font-mono w-48"
          />
          <button
            type="button"
            onClick={handleIngest}
            disabled={ingesting || !ticker.trim()}
            className="border border-line text-ink-dim px-4 py-2.5 text-sm rounded-md hover:text-ink hover:border-ink-faint disabled:text-ink-faint disabled:cursor-not-allowed"
          >
            {ingesting ? 'Ingesting… (~1 min)' : 'Ingest filings'}
          </button>
          <input
            type="password"
            value={ingestToken}
            onChange={(e) => setIngestToken(e.target.value)}
            placeholder="ingest token (if required)"
            className="text-xs w-52"
          />
        </div>
        {ingestStatus && <p className="text-xs text-ink-dim">{ingestStatus}</p>}
      </div>

      <div className="border-t border-line pt-8">
        <div className="space-y-6 mb-8 max-h-[28rem] overflow-y-auto">
          {messages.length === 0 ? (
            <div className="py-10 text-center">
              <h2 className="text-3xl text-ink mb-2">Your filings, <span className="text-accent">answering for themselves.</span></h2>
              <p className="text-sm text-ink-dim">Enter a ticker and ask a question about its SEC filings.</p>
            </div>
          ) : (
            messages.map((msg, i) => (
              <div key={i} className={`animate-item ${msg.role === 'user' ? 'pl-0' : 'border border-line bg-surface p-4 rounded-xl'}`}>
                <p className="text-xs uppercase tracking-kicker text-ink-faint mb-2 font-mono">
                  {msg.role === 'user' ? 'You' : 'StockRAG'}
                </p>
                <p className="text-sm leading-relaxed whitespace-pre-wrap text-ink max-w-[72ch]">
                  {msg.content}
                </p>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-line">
                    <p className="text-xs uppercase tracking-kicker text-ink-faint mb-2 font-mono">Sources</p>
                    <ul className="flex flex-wrap gap-2">
                      {msg.sources.map((src) => (
                        <li key={src.index} className="text-xs text-ink-dim border border-line bg-sunken px-3 py-2 rounded-md">
                          <span className="font-mono text-accent">[{src.index}]</span>{' '}
                          <span className="font-mono">{src.form}</span> {src.section}
                          <span className="text-ink-faint"> — {src.filing_date}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {error && (
          <div className="mb-4 px-3 py-2 border border-err text-err text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleAsk} className="flex flex-col gap-3">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="What are the key risks? Tell me about debt levels..."
            rows={3}
            className="text-sm"
          />
          <button
            type="submit"
            disabled={loading || !question.trim() || !ticker.trim()}
            className="self-start bg-accent text-bg px-6 py-2.5 text-sm font-bold rounded-md transition-all hover:brightness-110 hover:-translate-y-px disabled:bg-surface disabled:text-ink-faint disabled:cursor-not-allowed disabled:translate-y-0 disabled:brightness-100"
          >
            {loading ? 'Asking…' : 'Ask'}
          </button>
        </form>
      </div>
    </div>
  )
}
