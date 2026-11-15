import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { ApiError, ask, ingest } from '../lib/api'
import type { Source } from '../lib/api'
import { Markdown, linkCitations } from '../components/Markdown'
import { Chevron } from '../components/Chevron'
import { ModelSelect } from '../components/ModelSelect'
import { Notice } from '../components/Notice'
import { SourceList } from '../components/SourceList'
import { TickerField } from '../components/TickerField'
import { formatElapsed, useElapsed } from '../hooks/useElapsed'

interface UserMessage {
  id: number
  role: 'user'
  content: string
  ticker: string
}

interface AssistantMessage {
  id: number
  role: 'assistant'
  content: string
  sources: Source[]
}

type Message = UserMessage | AssistantMessage

interface PageProps {
  ticker: string
  onTickerChange: (ticker: string) => void
}

const EXAMPLES = [
  'What are the key risk factors?',
  'How much debt does the company carry, and when is it due?',
  'What legal proceedings are disclosed?',
  'How does the company describe its competition?',
]

const prefersReducedMotion = (): boolean => window.matchMedia('(prefers-reduced-motion: reduce)').matches

function AssistantAnswer({ msg }: { msg: AssistantMessage }) {
  const prefix = `src-${msg.id}`
  const { text, cited } = useMemo(
    () => linkCitations(msg.content, new Set(msg.sources.map((s) => s.index)), prefix),
    [msg.content, msg.sources, prefix],
  )
  return (
    <>
      <Markdown text={text} />
      {msg.sources.length > 0 && (
        <details open={msg.sources.length <= 6} className="group mt-4 pt-3 border-t border-line">
          <summary className="flex items-center gap-2 kicker w-fit">
            <Chevron />
            Sources · {cited.size} of {msg.sources.length} cited
          </summary>
          <div className="mt-2">
            <SourceList sources={msg.sources} cited={cited} idPrefix={prefix} />
          </div>
        </details>
      )}
    </>
  )
}

export default function Ask({ ticker, onTickerChange }: PageProps) {
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [pending, setPending] = useState<UserMessage | null>(null)
  const [failed, setFailed] = useState<{ msg: UserMessage; error: string } | null>(null)
  const [llm, setLlm] = useState('')

  const [ingesting, setIngesting] = useState(false)
  const [ingestStatus, setIngestStatus] = useState('')
  const [ingestError, setIngestError] = useState('')
  const [ingestToken, setIngestToken] = useState('')
  const [tokenOpen, setTokenOpen] = useState(false)

  const nextId = useRef(1)
  const questionRef = useRef<HTMLTextAreaElement>(null)
  const lastRowRef = useRef<HTMLDivElement>(null)

  const askElapsed = useElapsed(pending !== null)
  const ingestElapsed = useElapsed(ingesting)

  const hasTicker = ticker.trim() !== ''
  const canAsk = hasTicker && question.trim() !== '' && pending === null

  // Bring the newest row (question, pending row, answer or error) into view.
  useEffect(() => {
    lastRowRef.current?.scrollIntoView({
      block: 'nearest',
      behavior: prefersReducedMotion() ? 'auto' : 'smooth',
    })
  }, [messages.length, pending, failed])

  const handleIngest = async () => {
    if (!hasTicker) return
    setIngesting(true)
    setIngestStatus('')
    setIngestError('')
    try {
      const r = await ingest(ticker, ingestToken || undefined)
      setIngestStatus(
        r.filings_ingested > 0
          ? `Ingested ${r.filings_ingested} ${r.filings_ingested === 1 ? 'filing' : 'filings'} for ${r.ticker} (${r.chunks_added} chunks). Ask a question below.`
          : `Filings for ${r.ticker} are already ingested. Ask a question below.`,
      )
      questionRef.current?.focus()
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) setTokenOpen(true)
      setIngestError(err instanceof Error ? err.message : 'Ingest failed. Try again.')
    } finally {
      setIngesting(false)
    }
  }

  const send = async (msg: UserMessage) => {
    setPending(msg)
    setFailed(null)
    try {
      const response = await ask(msg.content, msg.ticker, llm || undefined)
      const answer: AssistantMessage = {
        id: nextId.current++,
        role: 'assistant',
        content: response.answer,
        sources: response.sources,
      }
      setMessages((prev) => [...prev, answer])
    } catch (err) {
      const error = err instanceof Error ? err.message : 'The answer could not be generated. Try again.'
      setFailed({ msg, error })
      setQuestion((q) => (q.trim() === '' ? msg.content : q))
    } finally {
      setPending(null)
    }
  }

  const submit = () => {
    if (!canAsk) return
    const msg: UserMessage = { id: nextId.current++, role: 'user', content: question.trim(), ticker }
    setMessages((prev) => {
      // A new question replaces a failed one rather than leaving it orphaned.
      const kept = failed ? prev.filter((m) => m.id !== failed.msg.id) : prev
      return [...kept, msg]
    })
    setQuestion('')
    send(msg)
  }

  const retry = () => {
    if (!failed || pending) return
    if (question.trim() === failed.msg.content) setQuestion('')
    send(failed.msg)
  }

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    submit()
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  const pickExample = (q: string) => {
    setQuestion(q)
    questionRef.current?.focus()
  }

  const clear = () => {
    setMessages([])
    setFailed(null)
  }

  const isEmpty = messages.length === 0 && !pending

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-3">
        <div className="flex gap-3 items-end flex-wrap">
          <TickerField id="ask-ticker" value={ticker} onChange={onTickerChange} />
          <button type="button" onClick={handleIngest} disabled={ingesting || !hasTicker} className="btn-secondary">
            {ingesting ? (
              <>
                Ingesting… <span className="font-mono tabular-nums">{formatElapsed(ingestElapsed)}</span>
              </>
            ) : (
              'Ingest filings'
            )}
          </button>
        </div>
        <p role="status" className="text-xs text-ink-dim">
          {ingesting ? 'Downloading and indexing filings from SEC EDGAR. This usually takes about a minute.' : ingestStatus}
        </p>
        {ingestError && <Notice>{ingestError}</Notice>}
        <details
          open={tokenOpen}
          onToggle={(e) => setTokenOpen(e.currentTarget.open)}
          className="group"
        >
          <summary className="flex items-center gap-2 text-xs text-ink-faint hover:text-ink-dim w-fit">
            <Chevron />
            Ingest token
          </summary>
          <div className="mt-3 flex flex-col gap-2">
            <label htmlFor="ask-ingest-token" className="kicker">
              Token
            </label>
            <input
              id="ask-ingest-token"
              type="password"
              value={ingestToken}
              onChange={(e) => setIngestToken(e.target.value)}
              autoComplete="off"
              className="field w-full max-w-xs"
            />
            <p className="text-xs text-ink-faint">Only needed if the server restricts ingestion.</p>
          </div>
        </details>
      </div>

      <div className="border-t border-line pt-8 flex flex-col gap-8">
        {!isEmpty && (
          <div className="flex items-center justify-between gap-4">
            <h2 className="kicker font-normal tracking-kicker">Conversation</h2>
            <button type="button" onClick={clear} disabled={pending !== null} className="btn-secondary py-1 px-3 text-xs">
              Clear conversation
            </button>
          </div>
        )}

        <div aria-live="polite" aria-busy={pending !== null} className="space-y-6">
          {isEmpty && !failed && (
            <div className="py-6 max-w-[72ch]">
              {hasTicker ? (
                <>
                  <p className="text-sm text-ink-dim mb-4">
                    Ask about <span className="font-mono text-ink">{ticker}</span>'s filings. Answers cite the
                    sections they come from. Try one of these:
                  </p>
                  <ul className="flex flex-col items-start gap-2">
                    {EXAMPLES.map((q) => (
                      <li key={q}>
                        <button type="button" onClick={() => pickExample(q)} className="btn-secondary text-left py-1.5 px-3">
                          {q}
                        </button>
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <p className="text-sm text-ink-dim">
                  Enter a ticker above and select Ingest filings. Once its filings are indexed, ask anything about them
                  here.
                </p>
              )}
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={msg.id}
              ref={i === messages.length - 1 && !pending && !failed ? lastRowRef : undefined}
              className={msg.role === 'user' ? '' : 'border-l border-line pl-4'}
            >
              {msg.role === 'user' ? (
                <>
                  <p className="kicker mb-2 flex items-center gap-2">
                    You
                    <span className="font-mono normal-case tracking-normal border border-line px-1.5 text-ink-dim">
                      {msg.ticker}
                    </span>
                  </p>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap break-words text-ink max-w-[72ch]">
                    {msg.content}
                  </p>
                </>
              ) : (
                <>
                  <p className="kicker mb-2">StockRAG</p>
                  <AssistantAnswer msg={msg} />
                </>
              )}
            </div>
          ))}

          {pending && (
            <div ref={lastRowRef} className="border-l border-line pl-4">
              <p className="kicker mb-2">StockRAG</p>
              <p className="text-sm text-ink-dim">
                Searching filings and writing an answer…{' '}
                <span className="font-mono tabular-nums text-ink-faint">{formatElapsed(askElapsed)}</span>
              </p>
              {askElapsed >= 20 && (
                <p className="text-xs text-ink-faint mt-1">Generation can take a few minutes on the free endpoint.</p>
              )}
            </div>
          )}

          {failed && !pending && (
            <div ref={lastRowRef}>
              <Notice action={{ label: 'Retry', onClick: retry }}>{failed.error}</Notice>
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3 max-w-[72ch]">
          <label htmlFor="ask-question" className="kicker">
            Question
          </label>
          <textarea
            id="ask-question"
            ref={questionRef}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="What are the key risks? How much debt is due next year?"
            rows={3}
            className="field w-full"
            aria-describedby="ask-hint"
          />
          <p id="ask-hint" className="text-xs text-ink-faint -mt-1">
            Enter to send · Shift+Enter for a new line
          </p>
          <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
            <ModelSelect id="ask-model" value={llm} onChange={setLlm} />
            <div className="flex items-center gap-3">
              <button type="submit" disabled={!canAsk} className="btn-primary">
                {pending ? 'Asking…' : 'Ask'}
              </button>
              {!hasTicker && <span className="text-xs text-ink-faint">Enter a ticker first</span>}
            </div>
          </div>
          <p className="text-xs text-ink-faint">Retrieval always runs locally; only generation switches.</p>
        </form>
      </div>
    </div>
  )
}
