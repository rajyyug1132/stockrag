interface ModelSelectProps {
  id: string
  value: string
  onChange: (value: string) => void
  disabled?: boolean
}

/** '' = whatever the server has configured (LLM_PROVIDER); the API takes a
 *  per-request override, so the UI can switch providers without a restart. */
export function ModelSelect({ id, value, onChange, disabled }: ModelSelectProps) {
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="kicker">
        Model
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="border border-line bg-bg text-ink-dim px-3 py-2 text-sm"
      >
        <option value="">Server default</option>
        <option value="nvidia">NVIDIA NIM</option>
        <option value="gemini">Gemini</option>
        <option value="ollama">Ollama (local)</option>
      </select>
    </div>
  )
}
