import type { Evidence } from '../types/report'
import { isHttpUrl } from '../utils/format'

interface Props {
  evidence: Evidence[]
}

type Tone = 'green' | 'red' | 'amber'

const TONE: Record<Tone, string> = {
  green: 'border-risk-low/50 bg-risk-low/10 text-risk-low',
  red: 'border-risk-high/60 bg-risk-high/10 text-[#F87171]',
  amber: 'border-risk-med/50 bg-risk-med/10 text-risk-med',
}

function tone(e: Evidence): Tone {
  const stance = e.stance.toLowerCase()
  if (stance === 'supports') return 'green'
  if (stance === 'refutes') return 'red'
  const rating = e.rating.toLowerCase()
  if (/\b(false|incorrect|misleading|hoax|pants on fire|debunk)/.test(rating)) return 'red'
  if (/\b(true|correct|accurate)\b/.test(rating) && !/\b(not|un|partly|half|mostly)\b/.test(rating)) return 'green'
  return 'amber'
}

const STANCE_LABEL: Record<string, string> = {
  supports: 'Supports the claim',
  refutes: 'Refutes the claim',
  mixed: 'Mixed',
  unrelated: 'Not directly related',
}

function host(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

export default function EvidenceList({ evidence }: Props) {
  if (evidence.length === 0) return null
  return (
    <section aria-label="Evidence" className="card animate-fade-up p-4 sm:p-6">
      <h2 className="section-title mb-4">Evidence from sources</h2>
      <ul className="space-y-3">
        {evidence.map((e, i) => {
          const hasRating = e.rating && e.rating.toLowerCase() !== 'none'
          const stance = STANCE_LABEL[e.stance.toLowerCase()] ?? e.stance
          return (
            <li key={i} className="rounded-lg border border-border bg-bg/50 p-4">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <span className="font-semibold text-text">{e.source || host(e.url) || 'Source'}</span>
                <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold ${TONE[tone(e)]}`}>
                  {hasRating ? `Source rating: ${e.rating}` : stance}
                </span>
                {hasRating && stance && <span className="text-xs text-muted">{stance}</span>}
              </div>
              {e.quote && (
                <blockquote className="mt-2 border-l-2 border-border pl-3 text-sm leading-relaxed text-text/90">
                  “{e.quote}”
                </blockquote>
              )}
              {e.url &&
                (isHttpUrl(e.url) ? (
                  <a
                    href={e.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 inline-flex max-w-full items-center gap-1 font-mono text-xs text-accent underline-offset-2 hover:underline"
                  >
                    <span className="truncate">{host(e.url)}</span>
                    <span aria-hidden="true">↗</span>
                    <span className="sr-only">(opens in a new tab)</span>
                  </a>
                ) : (
                  <p className="mt-2 font-mono text-xs break-all text-muted">{e.url}</p>
                ))}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
