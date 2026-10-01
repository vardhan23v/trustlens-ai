import type { Assessment, TrustReport } from '../types/report'
import { INTENT_COPY } from './IntentCards'
import { STATE_TONE } from './RiskBadge'
import type { Tone } from './RiskBadge'

const TONE_TEXT: Record<Tone, string> = { low: 'text-risk-low', med: 'text-risk-med', high: 'text-[#F87171]' }
const TONE_BORDER: Record<Tone, string> = { low: 'border-l-risk-low', med: 'border-l-risk-med', high: 'border-l-risk-high' }
const TONE_MARK: Record<Tone, string> = { low: '✓', med: '⚠', high: '✗' }

function Axis({ heading, a, primary }: { heading: string; a: Assessment; primary: boolean }) {
  const tone = a.state === 'NOT_ASSESSED' && a.label !== 'No editing traces found' ? 'med' : (STATE_TONE[a.state] ?? 'med')
  const quiet = a.state === 'NOT_ASSESSED'
  return (
    <div className={`rounded-xl border border-border border-l-4 bg-surface-2/60 p-4 ${quiet ? 'border-l-border' : TONE_BORDER[tone]}`}>
      <p className="section-title flex items-center gap-2">
        {heading}
        {primary && (
          <span className="rounded-full border border-accent-soft px-1.5 py-px text-[10px] font-medium normal-case tracking-normal text-accent">
            what you asked
          </span>
        )}
      </p>
      <p className={`mt-1.5 flex items-center gap-2 font-semibold ${quiet ? 'text-muted' : TONE_TEXT[tone]}`}>
        <span aria-hidden="true">{quiet ? '–' : TONE_MARK[tone]}</span>
        {a.label}
      </p>
      <p className="mt-1 text-sm text-muted">{a.summary}</p>
    </div>
  )
}

/** Image reports: the selected intent, and media authenticity vs artifact authenticity as separate answers. */
export default function AssessmentPanel({ report }: { report: TrustReport }) {
  const intent = report.analysis_intent
  if (!intent || !report.media_assessment || !report.artifact_assessment) return null
  return (
    <div className="card animate-fade-up p-4 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="text-lg font-semibold text-text">{INTENT_COPY[intent].report}</h2>
        <p className="text-xs text-muted">
          Analysis intent: <span className="font-medium text-accent">{INTENT_COPY[intent].title}</span>
        </p>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <Axis heading="Media authenticity" a={report.media_assessment} primary={intent === 'synthetic_detection'} />
        <Axis
          heading="Claim / artifact authenticity"
          a={report.artifact_assessment}
          primary={intent === 'artifact_authenticity'}
        />
      </div>
      <p className="mt-3 text-xs text-muted">
        These are separate questions: “not AI-generated” does not mean “true”, and a genuine-looking screenshot can
        still be fraudulent.
      </p>
    </div>
  )
}
