import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { getThesis, type ThesisResponse, type ThesisSection } from '../lib/api'
import { Markdown, linkCitations } from '../components/Markdown'
import { Chevron } from '../components/Chevron'
import { ModelSelect } from '../components/ModelSelect'
import { Notice } from '../components/Notice'
import { SourceList } from '../components/SourceList'
import { TickerField } from '../components/TickerField'
import { formatElapsed, useElapsed } from '../hooks/useElapsed'

interface PageProps {
  ticker: string
  onTickerChange: (ticker: string) => void
}

/** capital_allocation -> "Capital allocation". */
const topicLabel = (topic: string): string => topic.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())

/** One evidence answer with its [n] markers linked to its own source rows. */
function Evidence({ section, idPrefix }: { section: ThesisSection; idPrefix: string }) {
  const { text, cited } = useMemo(
    () => linkCitations(section.answer, new Set(section.sources.map((s) => s.index)), idPrefix),
    [section.answer, section.sources, idPrefix],
  )
  return (
    <>
      <Markdown text={text} dim />
      {section.sources.length > 0 && (
        <div className="mt-3">
          <SourceList sources={section.sources} cited={cited} idPrefix={idPrefix} />
        </div>
      )}
    </>
  )
}

function GroundingMeter({ value, topic }: { value: number; topic: string }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100)
  return (
    <span className="flex items-center gap-2 text-xs text-ink-faint whitespace-nowrap">
      <span
        role="meter"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${topic} grounding`}
        className="relative inline-block w-16 h-1 bg-line"
      >
        <span className="absolute inset-y-0 left-0 bg-ink-dim" style={{ width: `${pct}%` }} />
      </span>
      <span className="font-mono tabular-nums">{pct}% grounded</span>
      {pct < 50 && (
        <span className="text-warn">
          <span aria-hidden="true">! </span>low
        </span>
      )}
    </span>
  )
}

export default function Thesis({ ticker, onTickerChange }: PageProps) {
  const [data, setData] = useState<ThesisResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [llm, setLlm] = useState('')
  const [open, setOpen] = useState<Set<string>>(new Set())
  const elapsed = useElapsed(loading)

  const build = async () => {
    if (!ticker.trim() || loading) return

    setLoading(true)
    setError('')

    try {
      const result = await getThesis(ticker, llm || undefined)
      setData(result)
      setOpen(new Set())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The briefing could not be built. Try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleFetch = (e: FormEvent) => {
    e.preventDefault()
    build()
  }

  const toggle = (topic: string, isOpen: boolean) =>
    setOpen((prev) => {
      if (prev.has(topic) === isOpen) return prev
      const next = new Set(prev)
      if (isOpen) next.add(topic)
      else next.delete(topic)
      return next
    })

  const allOpen = data !== null && data.sections.length > 0 && data.sections.every((s) => open.has(s.topic))

  return (
    <div className="flex flex-col gap-8">
      <form onSubmit={handleFetch} className="flex flex-col gap-3">
        <fieldset disabled={loading} className="min-w-0 flex flex-wrap gap-x-4 gap-y-3 items-end">
          <TickerField id="thesis-ticker" value={ticker} onChange={onTickerChange} />
          <ModelSelect id="thesis-model" value={llm} onChange={setLlm} />
          <button type="submit" disabled={loading || !ticker.trim()} className="btn-primary">
            {loading ? 'Building…' : 'Build briefing'}
          </button>
        </fieldset>
        <p className="text-xs text-ink-faint max-w-[72ch]">
          Combines the factor report with evidence from the filings into one briefing. Ingest the ticker on the Ask tab
          first.
        </p>
      </form>

      {loading && (
        <div role="status" className="border border-line p-4 max-w-[72ch]">
          <p className="text-sm text-ink flex flex-wrap justify-between gap-x-4">
            <span>Building the briefing for <span className="font-mono">{ticker}</span>…</span>
            <span className="font-mono tabular-nums text-ink-dim">{formatElapsed(elapsed)}</span>
          </p>
          <p className="text-xs text-ink-faint mt-2">
            Building the factor report, asking the filings one question per topic, then writing the briefing. This
            usually takes a few minutes.
          </p>
        </div>
      )}

      {error && (
        <Notice action={{ label: 'Retry', onClick: build }}>
          {error}
        </Notice>
      )}

      {data && (
        <div
          aria-busy={loading}
          className={`flex flex-col gap-10 transition-opacity ${loading ? 'opacity-40' : ''}`}
        >
          <article className="border-t border-line pt-6">
            <h2 className="kicker font-normal tracking-kicker mb-4">
              Briefing · <span className="font-mono">{data.ticker}</span>
            </h2>
            <Markdown text={data.synthesis} />
          </article>

          {data.sections.length > 0 && (
            <div className="border-t border-line pt-6">
              <div className="flex items-center justify-between gap-4 mb-5">
                <h2 className="kicker font-normal tracking-kicker">Underlying evidence</h2>
                <button
                  type="button"
                  className="btn-text"
                  onClick={() => setOpen(allOpen ? new Set() : new Set(data.sections.map((s) => s.topic)))}
                >
                  {allOpen ? 'Collapse all' : 'Expand all'}
                </button>
              </div>
              <div className="flex flex-col gap-6">
                {data.sections.map((section, i) => {
                  const topic = topicLabel(section.topic)
                  return (
                    <details
                      key={section.topic}
                      open={open.has(section.topic)}
                      onToggle={(e) => toggle(section.topic, e.currentTarget.open)}
                      className="group border-l border-line pl-4"
                    >
                      <summary className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm font-medium text-ink hover:text-ink-dim">
                        <span className="flex items-center gap-2">
                          <Chevron />
                          {topic}
                        </span>
                        <GroundingMeter value={section.grounding} topic={topic} />
                      </summary>
                      <div className="mt-3 pl-5">
                        <p className="text-xs text-ink-faint mb-2">{section.question}</p>
                        <Evidence section={section} idPrefix={`src-thesis-${i}`} />
                      </div>
                    </details>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {!data && !error && !loading && (
        <div className="py-6 max-w-[72ch] text-sm text-ink-dim space-y-2">
          <p>
            A briefing pulls together the factor report and what the filings say about each topic (risks,
            competition and capital allocation), with how well each answer is grounded in its sources.
          </p>
          <p className="text-ink-faint">
            The ticker must be ingested first. Do that on the{' '}
            <a href="#ask" className="underline underline-offset-2 hover:text-ink">
              Ask
            </a>{' '}
            tab.
          </p>
        </div>
      )}
    </div>
  )
}
