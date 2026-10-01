import { Fragment } from 'react'
import type { CategoryBreakdown, Signal } from '../types/report'
import { SEVERITY_ICON, SEVERITY_LABEL, categoryLabel, fmtNum, normSeverity, sortSignals } from '../utils/format'
import SourceBadge from './SourceBadge'

interface Props {
  signals: Signal[]
  breakdown: CategoryBreakdown[]
  score: number
}

export default function DeductionTable({ signals, breakdown, score }: Props) {
  // Fall back to uncapped per-category sums if the backend sent no breakdown.
  const cats: CategoryBreakdown[] =
    breakdown.length > 0
      ? breakdown
      : [...new Set(signals.map((s) => s.category))].map((category) => {
          const raw = signals.filter((s) => s.category === category).reduce((sum, s) => sum + s.penalty, 0)
          return { category, raw, cap: raw, applied: raw }
        })

  const total = cats.reduce((sum, c) => sum + c.applied, 0)
  const expected = Math.max(0, Math.round(100 - total))
  const matches = expected === score
  const terms = cats.filter((c) => c.applied > 0).map((c) => fmtNum(c.applied))

  return (
    <section aria-label="Score calculation" className="card reveal p-4 sm:p-6">
      <h2 className="section-title">How the score was calculated</h2>
      <p className="mt-1 mb-4 text-xs text-muted">
        The score is computed in code from the signals below — not chosen by the model.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[30rem] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted">
              <th scope="col" className="py-2 pr-3 font-medium">Signal</th>
              <th scope="col" className="px-3 py-2 font-medium">Severity</th>
              <th scope="col" className="px-3 py-2 font-medium">Source</th>
              <th scope="col" className="py-2 pl-3 text-right font-medium">Points</th>
            </tr>
          </thead>
          <tbody>
            {cats.length === 0 && (
              <tr>
                <td colSpan={4} className="py-3 text-muted">
                  No deductions were applied.
                </td>
              </tr>
            )}
            {cats.map((cat) => {
              const rows = sortSignals(signals.filter((s) => s.category === cat.category))
              const capped = cat.raw > cat.applied
              return (
                <Fragment key={cat.category}>
                  <tr>
                    <th
                      scope="colgroup"
                      colSpan={4}
                      className="pt-4 pb-1 text-left text-xs font-semibold uppercase tracking-wider text-accent"
                    >
                      {categoryLabel(cat.category)}
                    </th>
                  </tr>
                  {rows.map((s, i) => {
                    const sev = normSeverity(s.severity)
                    return (
                      <tr key={`${s.key}-${i}`} className="border-b border-border/50">
                        <td className="py-2 pr-3 text-text">{s.title || s.key}</td>
                        <td className="px-3 py-2 whitespace-nowrap text-muted">
                          <span aria-hidden="true">{SEVERITY_ICON[sev]}</span> {SEVERITY_LABEL[sev]}
                        </td>
                        <td className="px-3 py-2">
                          <span className="flex gap-1">
                            {s.sources.map((src) => (
                              <SourceBadge key={src} source={src} />
                            ))}
                          </span>
                        </td>
                        <td className="py-2 pl-3 text-right font-mono tabular-nums text-text">−{fmtNum(s.penalty)}</td>
                      </tr>
                    )
                  })}
                  <tr className="bg-surface-2/60">
                    <td colSpan={3} className="rounded-l-lg py-2 pr-3 pl-3 text-muted">
                      Subtotal
                      <span className="ml-2 font-mono text-xs">
                        {capped
                          ? `${fmtNum(cat.applied)} of ${fmtNum(cat.raw)} (capped)`
                          : `${fmtNum(cat.applied)} (cap ${fmtNum(cat.cap)})`}
                      </span>
                    </td>
                    <td className="rounded-r-lg py-2 pr-3 pl-3 text-right font-mono font-semibold tabular-nums text-text">
                      −{fmtNum(cat.applied)}
                    </td>
                  </tr>
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="mt-5 flex flex-wrap items-baseline justify-between gap-2 border-t border-border pt-4">
        <span className="text-sm text-muted">Trust Score</span>
        <span className="font-mono text-base text-text">
          100{terms.length > 0 ? terms.map((t) => ` − ${t}`).join('') : ' − 0'} {matches ? '=' : '→'}{' '}
          <strong className="text-lg text-accent">{score}</strong>
        </span>
      </div>
      {!matches && (
        <p className="mt-1 text-right text-xs text-muted">Final score adjusted by the backend scoring rules.</p>
      )}
    </section>
  )
}
