import { useState } from 'react'
import { getThesis, type ThesisResponse } from '../lib/api'
import { Markdown } from '../components/Markdown'
import { Bar, Pending } from '../components/motion'
import TickerForm from '../components/TickerForm'

export default function Thesis() {
  const [ticker, setTicker] = useState('')
  const [data, setData] = useState<ThesisResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleFetch = async () => {
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
      <TickerForm
        ticker={ticker}
        onTickerChange={setTicker}
        onSubmit={handleFetch}
        loading={loading}
        submitLabel="Build Thesis"
        loadingLabel="Building…"
        hint="Factor report + filing evidence, synthesized into an evidence briefing. Not investment advice. Ingest the ticker first."
      />

      {error && (
        <div role="alert" className="px-3 py-2 border border-err text-err text-sm">
          {error}
        </div>
      )}

      {loading && (
        <div className="border-t border-line pt-6 flex flex-col gap-6">
          <Pending message="Answering each thesis question against the filings, then synthesizing (a few minutes)" />
          {/* Skeleton of the briefing so the page doesn't jump when it lands. */}
          <div className="flex flex-col gap-2 max-w-[72ch] animate-pulse" aria-hidden="true">
            {[100, 92, 96, 70].map((w) => (
              <div key={w} className="h-3 bg-surface rounded" style={{ width: `${w}%` }} />
            ))}
          </div>
        </div>
      )}

      {data && (
        <div className="flex flex-col gap-10">
          <article className="border-t border-line pt-6">
            <p className="text-xs uppercase tracking-kicker text-accent-dim font-mono mb-4">
              Briefing — {data.ticker}
            </p>
            <Markdown text={data.synthesis} />
          </article>

          <div className="border-t border-line pt-6">
            <p className="text-xs uppercase tracking-kicker text-accent-dim font-mono mb-5">
              Underlying evidence
            </p>
            <div className="flex flex-col gap-8">
              {data.sections.map((section, i) => (
                <details
                  key={section.topic}
                  className="animate-item border-l border-line pl-4"
                  style={{ animationDelay: `${i * 70}ms` }}
                >
                  <summary className="cursor-pointer text-sm font-medium text-ink hover:text-ink-dim">
                    {section.topic.replace(/_/g, ' ')}{' '}
                    <span className="font-mono text-xs text-ink-faint inline-flex items-center gap-2">
                      · <Bar value={section.grounding} className="w-12" /> {(section.grounding * 100).toFixed(0)}% grounded
                    </span>
                  </summary>
                  <div className="mt-3">
                    <p className="text-xs text-ink-faint mb-2">{section.question}</p>
                    <Markdown text={section.answer} dim />
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
