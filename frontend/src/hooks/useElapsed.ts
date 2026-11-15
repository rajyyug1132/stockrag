import { useEffect, useState } from 'react'

/** Seconds elapsed since `active` last became true; resets on each start. */
export function useElapsed(active: boolean): number {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    if (!active) return
    const start = Date.now()
    setSeconds(0)
    const id = window.setInterval(() => setSeconds(Math.floor((Date.now() - start) / 1000)), 1000)
    return () => window.clearInterval(id)
  }, [active])
  return seconds
}

/** 42 -> "0:42", 125 -> "2:05". */
export function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}
