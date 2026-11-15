import type { MouseEvent } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'

const prefersReducedMotion = (): boolean =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** Scroll to a source row, open its <details>, focus it and flash it. The
 *  click never touches location.hash, which drives view routing. */
export function revealSource(id: string) {
  const el = document.getElementById(id)
  if (!el) return
  const details = el.closest('details')
  if (details && !details.open) details.open = true
  el.scrollIntoView({ block: 'center', behavior: prefersReducedMotion() ? 'auto' : 'smooth' })
  el.focus({ preventScroll: true })
  el.classList.add('bg-surface')
  window.setTimeout(() => el.classList.remove('bg-surface'), 1500)
}

const components: Components = {
  a({ href, children }) {
    if (href?.startsWith('#src-')) {
      const target = href.slice(1)
      return (
        <a
          href={href}
          onClick={(e: MouseEvent<HTMLAnchorElement>) => {
            e.preventDefault()
            revealSource(target)
          }}
          className="font-mono text-xs tabular-nums text-ink-dim no-underline hover:underline underline-offset-2"
        >
          {children}
        </a>
      )
    }
    if (href?.startsWith('#')) return <a href={href}>{children}</a>
    return (
      <a href={href} target="_blank" rel="noreferrer" className="underline underline-offset-2 hover:text-ink-dim">
        {children}
      </a>
    )
  },
}

/** LLM answers come back as markdown (headings, bold, lists). Rendering them
 *  as plain text showed literal ## and ** on the Thesis briefing. */
export function Markdown({ text, dim = false }: { text: string; dim?: boolean }) {
  return (
    <div
      className={`text-sm leading-relaxed max-w-[72ch] space-y-3 break-words ${dim ? 'text-ink-dim' : 'text-ink'}
        [&_h2]:text-xs [&_h2]:uppercase [&_h2]:tracking-kicker [&_h2]:text-ink-faint [&_h2]:mt-5
        [&_h3]:text-sm [&_h3]:font-medium [&_h3]:text-ink [&_h3]:mt-4
        [&_strong]:font-medium [&_strong]:text-ink
        [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1.5
        [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:space-y-1.5`}
    >
      <ReactMarkdown components={components}>{text}</ReactMarkdown>
    </div>
  )
}

/** Turn [n] / [n, m] markers that match a returned source into links to that
 *  source's row. Returns the rewritten text and the set of cited indices. */
export function linkCitations(
  text: string,
  sourceIndices: Set<number>,
  idPrefix: string,
): { text: string; cited: Set<number> } {
  const cited = new Set<number>()
  const out = text.replace(/\[(\d+(?:\s*,\s*\d+)*)\](?!\()/g, (match, group: string) => {
    const nums = group.split(',').map((n) => Number(n.trim()))
    if (!nums.every((n) => sourceIndices.has(n))) return match
    nums.forEach((n) => cited.add(n))
    return nums.map((n) => `[\\[${n}\\]](#${idPrefix}-${n})`).join(' ')
  })
  return { text: out, cited }
}
