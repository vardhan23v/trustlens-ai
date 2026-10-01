import type { Severity, Signal } from '../types/report'
import { SEVERITY_ICON, SEVERITY_LABEL, fmtNum, normSeverity } from '../utils/format'
import { useTilt } from '../hooks/useTilt'
import SourceBadge from './SourceBadge'

interface Props {
  signal: Signal
  /** Position in the list — drives the staggered fade-in. */
  index?: number
}

const BAR: Record<Severity, string> = {
  high: 'border-l-sev-high',
  medium: 'border-l-sev-med',
  low: 'border-l-sev-low',
}

const SEV_TEXT: Record<Severity, string> = {
  high: 'text-[#F87171]',
  medium: 'text-sev-med',
  low: 'text-sev-low',
}

export default function SignalCard({ signal, index = 0 }: Props) {
  const sev = normSeverity(signal.severity)
  const tilt = useTilt<HTMLElement>(4)
  return (
    <div className="reveal reveal-flip" style={{ ['--reveal-delay' as string]: `${Math.min(index, 6) * 70}ms` }}>
    <article ref={tilt} className={`card card-hover tilt h-full border-l-4 p-4 ${BAR[sev]}`}>
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <h3 className="text-[15px] font-semibold leading-snug text-text">{signal.title || signal.key}</h3>
          <p className={`mt-0.5 text-xs font-semibold uppercase tracking-wide ${SEV_TEXT[sev]}`}>
            <span aria-hidden="true">{SEVERITY_ICON[sev]}</span> {SEVERITY_LABEL[sev]} severity
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          {signal.sources.map((s) => (
            <SourceBadge key={s} source={s} />
          ))}
          {signal.penalty > 0 && (
            <span className="ml-1 font-mono text-xs text-muted" title="Points before the per-category cap">
              −{fmtNum(signal.penalty)}
            </span>
          )}
        </div>
      </div>
      {signal.explanation && <p className="mt-3 text-sm leading-relaxed text-text/90">{signal.explanation}</p>}
      {signal.evidence && (
        <blockquote className="mt-3 rounded-lg border border-border bg-bg/70 px-3 py-2 font-mono text-xs leading-relaxed break-words text-text/90">
          {signal.evidence}
        </blockquote>
      )}
      {signal.uncertainty && <p className="mt-2 text-xs text-muted">Uncertainty: {signal.uncertainty}</p>}
    </article>
    </div>
  )
}
