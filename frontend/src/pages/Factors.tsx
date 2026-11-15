import { useState } from 'react'
import { AnimatePresence, motion, type Variants } from 'motion/react'
import { getFactors, type FactorReport } from '../lib/api'
import { fadeUp, Pending, ScoreRing, stagger } from '../components/motion'
import TickerForm from '../components/TickerForm'

const mark: Variants = {
  hidden: { opacity: 0, scale: 0.4 },
  visible: { opacity: 1, scale: 1, transition: { type: 'spring', stiffness: 500, damping: 25 } },
}

export default function Factors() {
  const [ticker, setTicker] = useState('')
  const [data, setData] = useState<FactorReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleFetch = async () => {
    setLoading(true)
    setError('')
    setData(null)

    try {
      const result = await getFactors(ticker)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch factors')
    } finally {
      setLoading(false)
    }
  }

  // null-safe on purpose: the API omits any field its data source couldn't
  // supply (and lists it under `missing`), so every formatter takes undefined.
  const num = (value: number | null | undefined): string => {
    if (value == null) return '—'
    if (Math.abs(value) > 100) return value.toFixed(0)
    if (Math.abs(value) > 1) return value.toFixed(2)
    return value.toFixed(4)
  }

  const pct = (value: number | null | undefined): string =>
    value == null ? '—' : `${(value * 100).toFixed(1)}%`

  const money = (value: number | null | undefined): string => {
    if (value == null) return '—'
    const abs = Math.abs(value)
    if (abs >= 1e12) return `$${(value / 1e12).toFixed(2)}T`
    if (abs >= 1e9) return `$${(value / 1e9).toFixed(1)}B`
    if (abs >= 1e6) return `$${(value / 1e6).toFixed(1)}M`
    return `$${value.toFixed(2)}`
  }

  const rows: { label: string; value: string; note: string }[] = data
    ? [
        { label: 'ROE', value: pct(data.roe), note: 'Return on equity' },
        { label: 'Net Margin', value: pct(data.net_margin), note: 'Net profit margin' },
        { label: 'Revenue', value: money(data.revenue), note: `FY ending ${data.fiscal_year_end ?? '—'}` },
        { label: 'Revenue Growth', value: pct(data.revenue_growth), note: 'Year over year' },
        { label: 'Free Cash Flow', value: money(data.free_cash_flow), note: 'CFO − capex' },
        { label: 'P/E Ratio', value: num(data.pe_ratio), note: 'Price-to-earnings' },
        { label: 'P/FCF Ratio', value: num(data.p_fcf_ratio), note: 'Price-to-free-cash-flow' },
        { label: 'Gross Profitability', value: num(data.gross_profitability), note: 'Novy-Marx (2013): gross profit / assets' },
        { label: 'Momentum 12-1', value: pct(data.momentum_12_1), note: '12-month return, skipping last month' },
        { label: 'Beta', value: num(data.beta), note: 'Volatility vs. market' },
        { label: 'Market Cap', value: money(data.market_cap), note: 'Price × shares outstanding' },
      ]
    : []

  const signalLabels: Record<string, string> = {
    positive_roa: 'Positive ROA',
    positive_cfo: 'Positive operating cash flow',
    roa_improving: 'ROA improving',
    cfo_exceeds_net_income: 'CFO > net income',
    leverage_decreasing: 'Leverage decreasing',
    current_ratio_improving: 'Current ratio improving',
    no_dilution: 'No share dilution',
    gross_margin_improving: 'Gross margin improving',
    asset_turnover_improving: 'Asset turnover improving',
  }

  const checkLabels: Record<string, string> = {
    roe_gt_15pct: 'ROE > 15%',
    net_margin_gt_10pct: 'Net margin > 10%',
    f_score_ge_7: 'F-Score ≥ 7',
  }

  return (
    <div className="flex flex-col gap-8">
      <TickerForm
        ticker={ticker}
        onTickerChange={setTicker}
        onSubmit={handleFetch}
        loading={loading}
        submitLabel="Get Factors"
        loadingLabel="Loading…"
      />

      <AnimatePresence>
        {error && (
          <motion.div
            key="error"
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            exit="hidden"
            role="alert"
            className="px-3 py-2 border border-err text-err text-sm"
          >
            {error}
          </motion.div>
        )}
      </AnimatePresence>

      {loading && <Pending message="Pulling XBRL company facts and market data" />}

      {data && (
        <motion.div variants={stagger(4, 0.3)} initial="hidden" animate="visible" className="border-t border-line">
          <motion.div variants={fadeUp} className="grid gap-4 py-6 sm:grid-cols-3">
            <div className="border border-line p-4">
              <p className="text-xs uppercase tracking-kicker text-ink-faint mb-3">Piotroski F-Score</p>
              <div className="flex items-center gap-4">
                <ScoreRing score={data.piotroski_score} />
                <p className="text-xs text-ink-faint">
                  out of 9 accounting signals
                  <br />
                  (Piotroski, 2000)
                </p>
              </div>
            </div>
            <div className="sm:col-span-2 border border-line p-4">
              <p className="text-xs uppercase tracking-kicker text-ink-faint mb-3">Flowchart checks</p>
              <motion.ul variants={stagger(3)} className="space-y-1.5">
                {Object.entries(data.checks).map(([key, passed]) => (
                  <motion.li key={key} variants={fadeUp} className="text-sm text-ink-dim flex gap-2">
                    <motion.span variants={mark} className={passed ? 'text-ok' : 'text-err'}>{passed ? '✓' : '✗'}</motion.span>
                    {checkLabels[key] ?? key}
                  </motion.li>
                ))}
              </motion.ul>
            </div>
          </motion.div>

          <motion.div variants={fadeUp} className="pb-6">
            <p className="text-xs uppercase tracking-kicker text-ink-faint mb-3">F-Score signals</p>
            <motion.ul variants={stagger(9)} className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(data.piotroski_signals).map(([key, passed]) => (
                <motion.li key={key} variants={fadeUp} className="text-xs text-ink-dim flex gap-2">
                  <motion.span variants={mark} className={passed ? 'text-ok' : 'text-ink-faint'}>{passed ? '✓' : '✗'}</motion.span>
                  {signalLabels[key] ?? key}
                </motion.li>
              ))}
            </motion.ul>
          </motion.div>

          <motion.table variants={stagger(rows.length, 0.4)} className="w-full border-t border-line">
            <thead>
              <tr>
                <th className="text-xs uppercase tracking-kicker text-ink-faint font-medium px-0 py-3 bg-transparent">Metric</th>
                <th className="text-right text-xs uppercase tracking-kicker text-ink-faint font-medium px-3 py-3 bg-transparent">Value</th>
                <th className="text-left text-xs uppercase tracking-kicker text-ink-faint font-medium px-3 py-3 bg-transparent">Notes</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {rows.map((row) => (
                <motion.tr key={row.label} variants={fadeUp} className="hover:bg-surface transition-colors">
                  <td className="px-0 py-3 font-medium text-ink">{row.label}</td>
                  <td className="px-3 py-3 text-right font-mono text-lg text-ink">{row.value}</td>
                  <td className="px-3 py-3 text-ink-faint">{row.note}</td>
                </motion.tr>
              ))}
            </tbody>
          </motion.table>

          {data.missing.length > 0 && (
            <motion.p variants={fadeUp} className="py-3 text-xs text-ink-faint">
              <span className="uppercase tracking-kicker">Missing data:</span> {data.missing.join(', ')}
            </motion.p>
          )}
        </motion.div>
      )}

      {!data && !error && !loading && (
        <p className="text-sm text-ink-faint py-10">
          Enter a ticker to view financial factors from SEC XBRL data.
        </p>
      )}
    </div>
  )
}
