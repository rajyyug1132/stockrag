import { useEffect, useRef } from 'react'
import { animate, motion, useMotionValue, useTransform, type Variants } from 'motion/react'

// Shared motion vocabulary. Keep everything short (<= ~250ms per element) and
// transform/opacity-only; MotionConfig reducedMotion="user" in App disables
// the movement for people who ask for less.

export const ease = [0.22, 1, 0.36, 1] as const

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.22, ease } },
}

export const fade: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.2, ease } },
}

// Stagger children, capping the whole cascade at roughly `total` seconds so a
// long table doesn't take forever to settle.
export const stagger = (count = 8, total = 0.35): Variants => ({
  hidden: {},
  visible: { transition: { staggerChildren: Math.min(0.05, total / Math.max(count, 1)) } },
})

export function CountUp({
  value,
  format = (n) => n.toFixed(0),
  className,
}: {
  value: number
  format?: (n: number) => string
  className?: string
}) {
  const mv = useMotionValue(0)
  const text = useTransform(mv, format)
  useEffect(() => {
    const controls = animate(mv, value, { duration: 0.6, ease })
    return () => controls.stop()
  }, [mv, value])
  return <motion.span className={className}>{text}</motion.span>
}

export function ScoreRing({ score, max = 9 }: { score: number | null; max?: number }) {
  const r = 26
  const progress = score == null ? 0 : Math.max(0, Math.min(1, score / max))
  return (
    <div className="relative w-16 h-16 shrink-0">
      <svg viewBox="0 0 64 64" className="w-16 h-16 -rotate-90" aria-hidden="true">
        <circle cx="32" cy="32" r={r} fill="none" strokeWidth="4" className="stroke-line" />
        <motion.circle
          cx="32"
          cy="32"
          r={r}
          fill="none"
          strokeWidth="4"
          strokeLinecap="round"
          className={progress >= 7 / 9 ? 'stroke-ok' : progress >= 4 / 9 ? 'stroke-warn' : 'stroke-err'}
          initial={{ pathLength: 0 }}
          animate={{ pathLength: progress }}
          transition={{ duration: 0.6, ease }}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center font-mono text-xl text-ink">
        {score ?? '—'}
      </span>
    </div>
  )
}

// Thin 0..1 fill. Scales a full-width bar from the left (transform only).
export function Bar({ value, className = 'w-16' }: { value: number; className?: string }) {
  const v = Math.max(0, Math.min(1, value))
  const tone = v >= 0.8 ? 'bg-ok' : v >= 0.5 ? 'bg-warn' : 'bg-err'
  return (
    <span className={`inline-block h-1 bg-line overflow-hidden align-middle ${className}`} aria-hidden="true">
      <motion.span
        className={`block h-full ${tone} origin-left`}
        initial={{ scaleX: 0 }}
        animate={{ scaleX: v }}
        transition={{ duration: 0.5, ease }}
      />
    </span>
  )
}

// Indeterminate hairline progress + message for long requests (thesis takes
// minutes, ingest about one).
export function Pending({ message }: { message: string }) {
  const start = useRef(Date.now())
  const elapsed = useMotionValue(0)
  const label = useTransform(elapsed, (s) => `${Math.floor(s)}s`)
  useEffect(() => {
    const id = setInterval(() => elapsed.set((Date.now() - start.current) / 1000), 1000)
    return () => clearInterval(id)
  }, [elapsed])

  return (
    <motion.div variants={fade} initial="hidden" animate="visible" exit="hidden" role="status" className="flex flex-col gap-2">
      <div className="relative h-px w-full max-w-[72ch] bg-line overflow-hidden">
        <motion.div
          className="absolute inset-y-0 left-0 w-1/3 bg-ink-dim"
          animate={{ x: ['-100%', '300%'] }}
          transition={{ duration: 1.4, ease: 'easeInOut', repeat: Infinity }}
        />
      </div>
      <p className="text-xs text-ink-faint flex gap-2">
        <span>{message}</span>
        <motion.span className="font-mono">{label}</motion.span>
      </p>
    </motion.div>
  )
}
