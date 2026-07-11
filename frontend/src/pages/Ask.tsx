import { useState } from 'react'
import { ask } from '../lib/api'

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

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim() || !ticker.trim()) return

    setLoading(true)
    setError('')

    try {
      const response = await ask(question, ticker)
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
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <label className="text-sm font-medium">Ticker</label>
        <input
          type="text"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder="AAPL, MSFT, TSLA, ..."
          maxLength={5}
          className="border border-gray-300 px-3 py-2 text-sm"
        />
      </div>

      <div className="border-t border-gray-300 pt-6">
        <div className="space-y-4 mb-6 max-h-96 overflow-y-auto">
          {messages.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-8">
              Enter a ticker and ask a question about SEC filings.
            </p>
          ) : (
            messages.map((msg, i) => (
              <div key={i} className={`p-3 rounded border ${
                msg.role === 'user'
                  ? 'bg-gray-50 border-gray-300 text-black'
                  : 'bg-white border-gray-300 text-black'
              }`}>
                <p className="text-xs font-bold mb-1">
                  {msg.role === 'user' ? 'You' : 'StockRAG'}
                </p>
                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                  {msg.content}
                </p>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-300">
                    <p className="text-xs font-bold mb-2">Sources:</p>
                    <ul className="space-y-1">
                      {msg.sources.map((src) => (
                        <li key={src.index} className="text-xs text-gray-600">
                          <span className="font-mono">[{src.index}]</span>{' '}
                          <span className="font-mono">{src.form}</span> {src.section}
                          <span> — {src.filing_date}</span>
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
          <div className="mb-4 p-3 bg-white border border-red-300 text-red-600 text-sm rounded">
            {error}
          </div>
        )}

        <form onSubmit={handleAsk} className="flex flex-col gap-2">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="What are the key risks? Tell me about debt levels..."
            rows={3}
            className="border border-gray-300 px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={loading || !question.trim() || !ticker.trim()}
            className="bg-accent text-white px-4 py-2 text-sm font-medium hover:bg-blue-600 disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {loading ? 'Asking...' : 'Ask'}
          </button>
        </form>
      </div>
    </div>
  )
}
