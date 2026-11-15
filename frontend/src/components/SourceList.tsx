import type { Source } from '../lib/api'

const titleCase = (s: string): string =>
  s
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')

/** item_1a_risk_factors -> "Item 1A · Risk Factors", item_7_mda -> "Item 7 · MD&A". */
export function humanizeSection(id: string): string {
  const key = id.trim().toLowerCase()
  if (key === 'other') return 'Other'
  const m = key.match(/^item_(\d+[a-z]?)(?:_(.+))?$/)
  if (m) {
    const num = m[1].toUpperCase()
    const rest = m[2]
    if (!rest) return `Item ${num}`
    return `Item ${num} · ${rest === 'mda' ? 'MD&A' : titleCase(rest)}`
  }
  if (key === 'mda') return 'MD&A'
  return titleCase(id)
}

interface SourceListProps {
  sources: Source[]
  /** Indices the answer cited. When omitted, every source is shown as cited. */
  cited?: Set<number>
  /** Prefix for each row's id, so citation links can target it. */
  idPrefix?: string
}

export function SourceList({ sources, cited, idPrefix }: SourceListProps) {
  return (
    <ul className="space-y-1">
      {sources.map((src) => {
        const isCited = !cited || cited.has(src.index)
        return (
          <li
            key={src.index}
            id={idPrefix ? `${idPrefix}-${src.index}` : undefined}
            tabIndex={idPrefix ? -1 : undefined}
            className={`text-xs -mx-1 px-1 py-0.5 transition-colors outline-none ${
              isCited ? 'text-ink-dim' : 'text-ink-faint'
            }`}
          >
            <span className="font-mono tabular-nums">[{src.index}]</span>{' '}
            <span className="font-mono">{src.form}</span> {humanizeSection(src.section)}
            <span className="text-ink-faint">
              {" "}
              · <span className="font-mono tabular-nums">{src.filing_date}</span>
            </span>
            {!isCited && <span className="text-ink-faint"> · not cited</span>}
          </li>
        )
      })}
    </ul>
  )
}
