import type { Assessment, TrustReport } from '../types/report'
import { MODE_COPY } from './ModeCards'
import { STATE_TONE } from './RiskBadge'
import type { Tone } from './RiskBadge'

const TONE_TEXT: Record<Tone, string> = { low: 'text-risk-low', med: 'text-risk-med', high: 'text-[#F87171]' }
const TONE_BORDER: Record<Tone, string> = { low: 'border-l-risk-low', med: 'border-l-risk-med', high: 'border-l-risk-high' }
const TONE_MARK: Record<Tone, string> = { low: '✓', med: '⚠', high: '✗' }

function Axis({ heading, a, from }: { heading: string; a: Assessment; from: 'left' | 'right' }) {
  const tone = STATE_TONE[a.state] ?? 'med'
  const quiet = a.state === 'NOT_ASSESSED'
  return (
    <div className={`reveal reveal-${from} rounded-xl border border-border border-l-4 bg-surface-2/60 p-4 ${quiet ? 'border-l-border' : TONE_BORDER[tone]}`}>
      <p className="section-title">{heading}</p>
      <p className={`mt-1.5 flex items-center gap-2 font-semibold ${quiet ? 'text-muted' : TONE_TEXT[tone]}`}>
        <span aria-hidden="true">{quiet ? '–' : TONE_MARK[tone]}</span>
        {a.label}
      </p>
      <p className="mt-1 text-sm text-muted">{a.summary}</p>
      {a.confidence && (
        <p className="mt-2 border-t border-border/60 pt-2 text-xs text-muted">
          <span className="font-medium text-text">Confidence: {a.confidence}.</span> {a.basis}
        </p>
      )}
    </div>
  )
}

/** Report header: the selected mode, the media type, and each question answered separately. */
export default function AssessmentPanel({ report }: { report: TrustReport }) {
  const axes = report.assessment_axes ?? []
  if (axes.length === 0 || !report.mode) return null
  const news = report.mode === 'news_claim'
  return (
    <div className="card animate-fade-up p-4 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="text-lg font-semibold text-text">{MODE_COPY[report.mode].report}</h2>
        <p className="text-xs text-muted">
          Mode: <span className="font-medium text-accent">{MODE_COPY[report.mode].title}</span>
          {report.media_type && (
            <>
              {' '}
              · Media: <span className="font-medium uppercase text-text">{report.media_type}</span>
            </>
          )}
          {report.report_id && (
            <>
              {' '}
              · <span className="font-mono">{report.report_id}</span>
            </>
          )}
        </p>
      </div>
      <div className={`mt-4 grid gap-3 ${axes.length > 1 ? 'md:grid-cols-2' : ''}`}>
        {axes.map((a, i) => (
          <Axis key={a.heading} heading={a.heading} a={a} from={i % 2 === 0 ? 'left' : 'right'} />
        ))}
      </div>
      <p className="mt-3 text-xs text-muted">
        {news
          ? 'Claim, media and context are separate questions: an authentic image can carry a false claim, and an AI-generated image can accompany a true one.'
          : 'This mode examines the media itself. It does not check whether anything shown or said is true: use News / Claim for that.'}{' '}
        TrustLens reports likelihood, evidence and uncertainty. It does not prove truth.
      </p>
    </div>
  )
}
