import type { Article, ClaimStatus, TimelineEvent } from '../types/report'
import { isHttpUrl } from '../utils/format'

const STATUS: Record<ClaimStatus['status'], { label: string; cls: string }> = {
  SUPPORTED: { label: 'Supported by sources', cls: 'border-risk-low/50 bg-risk-low/10 text-risk-low' },
  CONTRADICTED: { label: 'Contradicted by sources', cls: 'border-risk-high/60 bg-risk-high/10 text-[#F87171]' },
  MIXED: { label: 'Sources disagree', cls: 'border-risk-med/50 bg-risk-med/10 text-risk-med' },
  UNVERIFIED: { label: 'Unverified', cls: 'border-border bg-surface-2 text-muted' },
}
const STANCE_DOT: Record<string, string> = { supports: 'bg-risk-low', refutes: 'bg-risk-high', mixed: 'bg-risk-med' }

interface Props {
  claims: ClaimStatus[]
  timeline: TimelineEvent[]
  article: Article | null
}

/** Claim verification: the fetched article, each decomposed claim with its status, and a dated source timeline. */
export default function ClaimBreakdown({ claims, timeline, article }: Props) {
  if (claims.length === 0 && timeline.length === 0 && !article) return null
  return (
    <section aria-label="Claim verification" className="card reveal space-y-6 p-4 sm:p-6">
      {article && (
        <div>
          <h2 className="section-title mb-2">Article checked</h2>
          <p className="font-semibold text-text">{article.headline || article.url}</p>
          <p className="mt-1 text-xs text-muted">
            {[article.publisher, article.author, article.published || 'date unknown'].filter(Boolean).join(' · ')}
          </p>
        </div>
      )}
      {claims.length > 0 && (
        <div>
          <h2 className="section-title mb-1">Claims identified</h2>
          <p className="mb-3 text-xs text-muted">
            Each part is checked on its own. A part no source addressed stays unverified; that is not evidence it is
            false.
          </p>
          <ol className="space-y-2">
            {claims.map((c, i) => (
              <li key={i} className="flex flex-wrap items-start gap-x-3 gap-y-2 rounded-lg border border-border bg-bg/50 p-3">
                <span className="font-mono text-xs text-muted">{i + 1}</span>
                <p className="min-w-0 flex-1 text-sm text-text">{c.text}</p>
                <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${STATUS[c.status].cls}`}>
                  {STATUS[c.status].label}
                </span>
                <span className="w-full pl-5 text-xs text-muted">
                  {c.dimension} · independent sources: {c.supporting} supporting, {c.contradicting} contradicting
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
      {timeline.length > 0 && (
        <div>
          <h2 className="section-title mb-1">Source timeline</h2>
          <p className="mb-3 text-xs text-muted">Dates come from the publishers’ feeds; unknown dates are marked.</p>
          <ol className="relative space-y-3 border-l border-border pl-5">
            {timeline.map((t, i) => (
              <li key={i} className="relative">
                <span
                  aria-hidden="true"
                  className={`absolute top-1.5 -left-[25px] size-2.5 rounded-full ${STANCE_DOT[t.stance] ?? 'bg-border'}`}
                />
                <p className="font-mono text-xs text-accent">{t.date}</p>
                <p className="text-sm text-text">
                  <span className="font-semibold">{t.source}</span>
                  <span className="text-muted"> — {t.stance}</span>
                </p>
                {isHttpUrl(t.url) ? (
                  <a href={t.url} target="_blank" rel="noopener noreferrer" className="text-sm text-muted underline-offset-2 hover:text-accent hover:underline">
                    {t.title}
                  </a>
                ) : (
                  <p className="text-sm text-muted">{t.title}</p>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  )
}
