import { motion } from 'motion/react'

interface TickerFormProps {
  ticker: string
  onTickerChange: (ticker: string) => void
  onSubmit: () => void
  loading: boolean
  submitLabel: string
  loadingLabel: string
  hint?: string
}

export default function TickerForm({
  ticker,
  onTickerChange,
  onSubmit,
  loading,
  submitLabel,
  loadingLabel,
  hint,
}: TickerFormProps) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (ticker.trim()) onSubmit()
      }}
      className="flex flex-col gap-2"
    >
      <label htmlFor="ticker" className="text-xs uppercase tracking-kicker text-ink-faint">
        Company Ticker
      </label>
      <div className="flex gap-3">
        <input
          id="ticker"
          type="text"
          value={ticker}
          onChange={(e) => onTickerChange(e.target.value.toUpperCase())}
          placeholder="AAPL, MSFT, TSLA, ..."
          maxLength={5}
          className="border border-line px-3 py-2 text-sm font-mono w-48"
        />
        <motion.button
          type="submit"
          whileTap={{ scale: 0.97 }}
          disabled={loading || !ticker.trim()}
          className="bg-ink text-bg px-5 py-2 text-sm font-semibold hover:bg-ink-dim disabled:bg-surface disabled:text-ink-faint disabled:cursor-not-allowed"
        >
          {loading ? loadingLabel : submitLabel}
        </motion.button>
      </div>
      {hint && <p className="text-xs text-ink-faint">{hint}</p>}
    </form>
  )
}
