import { useState } from 'react'
import { getThesis, type ThesisResponse } from '../lib/api'

export default function Thesis() {
  const [ticker, setTicker] = useState('')
  const [data, setData] = useState<ThesisResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleFetch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!ticker.trim()) return

    setLoading(true)
    setError('')
    setData(null)

    try {
      const result = await getThesis(ticker)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to build thesis')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <form onSubmit={handleFetch} className="flex flex-col gap-2">
        <label className="text-xs uppercase tracking-kicker text-ink-faint">Company Ticker</label>
        <div className="flex gap-3">
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="AAPL, MSFT, TSLA, ..."
            maxLength={5}
            className="border border-line px-3 py-2 text-sm font-mono w-48"
          />
          <button
            type="submit"
            disabled={loading || !ticker.trim()}
            className="bg-ink text-bg px-5 py-2 text-sm font-semibold hover:bg-ink-dim disabled:bg-surface disabled:text-ink-faint disabled:cursor-not-allowed"
          >
            {loading ? 'Building… (takes a few minutes)' : 'Build Thesis'}
          </button>
        </div>
        <p className="text-xs text-ink-faint">
          Factor report + filing evidence, synthesized into an evidence briefing.
          Not investment advice. Ingest the ticker first.
        </p>
      </form>

      {error && (
        <div className="px-3 py-2 border border-err text-err text-sm">
          {error}
        </div>
      )}

      {data && (
        <div className="flex flex-col gap-10">
          <article className="border-t border-line pt-6">
            <p className="text-xs uppercase tracking-kicker text-ink-faint mb-4">
              Briefing — {data.ticker}
            </p>
            <div className="text-sm leading-relaxed whitespace-pre-wrap text-ink max-w-[72ch]">
              {data.synthesis}
            </div>
          </article>

          <div className="border-t border-line pt-6">
            <p className="text-xs uppercase tracking-kicker text-ink-faint mb-5">
              Underlying evidence
            </p>
            <div className="flex flex-col gap-8">
              {data.sections.map((section) => (
                <details key={section.topic} className="border-l border-line pl-4">
                  <summary className="cursor-pointer text-sm font-medium text-ink hover:text-ink-dim">
                    {section.topic.replace(/_/g, ' ')}{' '}
                    <span className="font-mono text-xs text-ink-faint">
                      · {(section.grounding * 100).toFixed(0)}% grounded
                    </span>
                  </summary>
                  <div className="mt-3">
                    <p className="text-xs text-ink-faint mb-2">{section.question}</p>
                    <p className="text-sm leading-relaxed whitespace-pre-wrap text-ink-dim max-w-[72ch]">
                      {section.answer}
                    </p>
                    {section.sources.length > 0 && (
                      <ul className="mt-3 space-y-1">
                        {section.sources.map((src) => (
                          <li key={src.index} className="text-xs text-ink-faint">
                            <span className="font-mono">[{src.index}] {src.form}</span>{' '}
                            {src.section} — {src.filing_date}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </details>
              ))}
            </div>
          </div>
        </div>
      )}

      {!data && !error && !loading && (
        <p className="text-sm text-ink-faint py-10">
          Enter a ticker to build an evidence briefing from its filings and factors.
        </p>
      )}
    </div>
  )
}
