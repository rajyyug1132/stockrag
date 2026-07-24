import { useState } from 'react'
import { ask, ingest } from '../lib/api'
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
  // '' = whatever the server has configured (LLM_PROVIDER); the API takes a
  // per-request override, so the UI can switch providers without a restart.
  const [llm, setLlm] = useState('')

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
        <label className="text-xs uppercase tracking-kicker text-ink-faint">Ticker</label>
        <div className="flex gap-3 items-center flex-wrap">
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="AAPL, MSFT, TSLA, ..."
            maxLength={5}
            className="border border-line px-3 py-2 text-sm font-mono w-48"
          />
          <button
            type="button"
            onClick={handleIngest}
            disabled={ingesting || !ticker.trim()}
            className="border border-line text-ink-dim px-4 py-2 text-sm hover:text-ink hover:border-ink-faint disabled:text-ink-faint disabled:cursor-not-allowed"
          >
            {ingesting ? 'Ingesting… (~1 min)' : 'Ingest filings'}
          </button>
          <input
            type="password"
            value={ingestToken}
            onChange={(e) => setIngestToken(e.target.value)}
            placeholder="ingest token (if required)"
            className="border border-line px-3 py-2 text-xs w-52"
          />
        </div>
        {ingestStatus && <p className="text-xs text-ink-dim">{ingestStatus}</p>}
      </div>

      <div className="border-t border-line pt-8">
        <div className="space-y-6 mb-8 max-h-[28rem] overflow-y-auto">
          {messages.length === 0 ? (
            <p className="text-sm text-ink-faint py-10">
              Enter a ticker and ask a question about its SEC filings.
            </p>
          ) : (
            messages.map((msg, i) => (
              <div key={i} className={msg.role === 'user' ? 'pl-0' : 'border-l border-line pl-4'}>
                <p className="text-xs uppercase tracking-kicker text-ink-faint mb-2">
                  {msg.role === 'user' ? 'You' : 'StockRAG'}
                </p>
                <p className="text-sm leading-relaxed whitespace-pre-wrap text-ink max-w-[72ch]">
                  {msg.content}
                </p>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-line">
                    <p className="text-xs uppercase tracking-kicker text-ink-faint mb-2">Sources</p>
                    <ul className="space-y-1">
                      {msg.sources.map((src) => (
                        <li key={src.index} className="text-xs text-ink-dim">
                          <span className="font-mono">[{src.index}]</span>{' '}
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
            className="border border-line px-3 py-2 text-sm max-w-[72ch]"
          />
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={loading || !question.trim() || !ticker.trim()}
              className="bg-ink text-bg px-5 py-2 text-sm font-semibold hover:bg-ink-dim disabled:bg-surface disabled:text-ink-faint disabled:cursor-not-allowed"
            >
              {loading ? 'Asking…' : 'Ask'}
            </button>
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
