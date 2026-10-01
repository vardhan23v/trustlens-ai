import type { AnalysisMode } from '../types/report'

interface Props {
  analysisMode: AnalysisMode
  geminiError: string | null
}

export default function ModeBanner({ analysisMode, geminiError }: Props) {
  const cached = analysisMode === 'demo_cached'
  if (!cached && !geminiError) return null
  return (
    <div className="flex flex-wrap gap-2">
      {cached && (
        <span className="inline-flex items-center rounded-full border border-accent-soft bg-accent/10 px-3 py-1 text-xs font-semibold tracking-wide text-accent">
          CACHED DEMO — Gemini output pre-recorded
        </span>
      )}
      {geminiError && (
        <span
          title={geminiError}
          className="inline-flex items-center rounded-full border border-risk-med/50 bg-risk-med/10 px-3 py-1 text-xs font-semibold text-risk-med"
        >
          Gemini unavailable — rule-based results only
        </span>
      )}
    </div>
  )
}
