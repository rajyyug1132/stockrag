import type { ReactNode } from 'react'

interface NoticeProps {
  kind?: 'error' | 'info'
  children: ReactNode
  action?: { label: string; onClick: () => void }
}

/** Error or status box. Errors carry a glyph and the word "Error", so the
 *  state never depends on colour alone. */
export function Notice({ kind = 'error', children, action }: NoticeProps) {
  const isError = kind === 'error'
  return (
    <div
      role={isError ? 'alert' : 'status'}
      className={`flex flex-wrap items-start gap-x-4 gap-y-2 border px-3 py-2 text-sm max-w-[72ch] ${
        isError ? 'border-err text-ink' : 'border-line text-ink-dim'
      }`}
    >
      <p className="flex-1 min-w-[12rem]">
        {isError && (
          <span className="text-err font-medium mr-2">
            <span aria-hidden="true">✗ </span>Error
          </span>
        )}
        {children}
      </p>
      {action && (
        <button type="button" onClick={action.onClick} className="btn-secondary py-1 px-3 text-xs">
          {action.label}
        </button>
      )}
    </div>
  )
}
