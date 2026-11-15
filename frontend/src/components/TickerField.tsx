interface TickerFieldProps {
  id: string
  value: string
  onChange: (value: string) => void
  label?: string
  disabled?: boolean
}

/** Shared ticker input. Up to 12 characters: the API also ingests non-US
 *  tickers with an exchange suffix (e.g. RELIANCE.NS), so 5 was too short. */
export function TickerField({ id, value, onChange, label = 'Ticker', disabled }: TickerFieldProps) {
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="kicker">
        {label}
      </label>
      <input
        id={id}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value.toUpperCase())}
        placeholder="e.g. AAPL"
        maxLength={12}
        autoCapitalize="characters"
        autoComplete="off"
        spellCheck={false}
        disabled={disabled}
        className="field font-mono w-40 disabled:text-ink-faint"
      />
    </div>
  )
}
