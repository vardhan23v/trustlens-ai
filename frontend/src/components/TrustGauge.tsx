import { useEffect, useState } from 'react'
import type { RiskLevel } from '../types/report'
import { useTilt } from '../hooks/useTilt'
import { prefersReducedMotion } from '../utils/format'

interface Props {
  score: number
  risk: RiskLevel
}

const SIZE = 180
const STROKE = 12
const R = (SIZE - STROKE) / 2
const C = 2 * Math.PI * R
const DURATION = 900

const RISK_COLOR: Record<RiskLevel, string> = {
  LOW: 'var(--color-risk-low)',
  MEDIUM: 'var(--color-risk-med)',
  HIGH: 'var(--color-risk-high)',
}

export default function TrustGauge({ score, risk }: Props) {
  const target = Math.max(0, Math.min(100, Math.round(score)))
  const [value, setValue] = useState(() => (prefersReducedMotion() ? target : 0))

  useEffect(() => {
    if (prefersReducedMotion()) {
      setValue(target)
      return
    }
    let raf = 0
    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / DURATION)
      const eased = 1 - Math.pow(1 - t, 3)
      setValue(target * eased)
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target])

  const color = RISK_COLOR[risk] ?? 'var(--color-accent)'
  const tilt = useTilt<HTMLDivElement>(10)

  return (
    <div
      role="img"
      aria-label={`Trust score ${target} out of 100`}
      ref={tilt}
      className="tilt relative shrink-0 rounded-full"
      style={{ width: SIZE, height: SIZE, ['--gauge-color' as string]: color }}
    >
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} className="gauge-glow -rotate-90" aria-hidden="true">
        <circle cx={SIZE / 2} cy={SIZE / 2} r={R} fill="none" stroke="var(--color-surface-2)" strokeWidth={STROKE} />
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={R}
          fill="none"
          stroke={color}
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={C}
          strokeDashoffset={C * (1 - value / 100)}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center" aria-hidden="true">
        <div className="flex items-baseline gap-1 font-mono">
          <span className="text-5xl font-bold tabular-nums" style={{ color }}>
            {Math.round(value)}
          </span>
          <span className="text-sm text-muted">/100</span>
        </div>
        <span className="mt-1 text-[11px] font-medium uppercase tracking-widest text-muted">Trust Score</span>
      </div>
    </div>
  )
}
