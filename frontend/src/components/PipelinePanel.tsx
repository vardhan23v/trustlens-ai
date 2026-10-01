import type { TrustReport } from '../types/report'

const STATUS_STYLE: Record<string, string> = {
  done: 'border-risk-low/50 text-risk-low',
  skipped: 'border-border text-muted',
  failed: 'border-risk-high/60 text-[#F87171]',
  unavailable: 'border-risk-med/50 text-risk-med',
}

const MODEL_STYLE: Record<string, string> = {
  RAN: STATUS_STYLE.done,
  NOT_APPLICABLE: STATUS_STYLE.skipped,
  NOT_RUN: STATUS_STYLE.skipped,
  FAILED: STATUS_STYLE.failed,
}

const META_LABEL: Record<string, string> = {
  duration_s: 'Duration (s)',
  container: 'Container',
  video_codec: 'Video codec',
  width: 'Width',
  height: 'Height',
  fps: 'Frame rate',
  audio_codec: 'Audio codec',
  sample_rate: 'Sample rate (Hz)',
  creation_time: 'Creation time',
  encoder: 'Encoder tag',
  software: 'Software tag',
  handler: 'Handler',
  comment: 'Comment',
}

/** What actually ran: pipeline stages, specialist-model status, and container metadata. */
export default function PipelinePanel({ report }: { report: TrustReport }) {
  const stages = report.stages ?? []
  const models = report.specialist_models ?? []
  const meta = Object.entries(report.media_metadata ?? {})
  if (stages.length === 0 && models.length === 0 && meta.length === 0) return null
  return (
    <div className="card reveal space-y-5 p-4 sm:p-6">
      {stages.length > 0 && (
        <div>
          <h2 className="section-title mb-3">Analysis stages (as they ran)</h2>
          <ol className="grid gap-2 md:grid-cols-2">
            {stages.map((s, i) => (
              <li key={`${s.name}-${i}`} className="flex items-start gap-3 rounded-lg border border-border bg-surface-2/50 px-3 py-2">
                <span className={`mt-0.5 shrink-0 rounded-full border px-2 py-px text-[10px] font-semibold uppercase tracking-wide ${STATUS_STYLE[s.status] ?? STATUS_STYLE.skipped}`}>
                  {s.status}
                </span>
                <span className="min-w-0 text-sm text-text">
                  {s.name}
                  {s.detail && <span className="block text-xs text-muted">{s.detail}</span>}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
      {models.length > 0 && (
        <div>
          <h2 className="section-title mb-1.5">Model findings</h2>
          <p className="mb-3 text-xs text-muted">
            Pretrained specialist models and what each actually did on this file. A model that did not run contributes
            nothing — it is not counted as evidence either way. Model scores are evidence, not verdicts.
          </p>
          <ul className="grid gap-2 md:grid-cols-2">
            {models.map((m) => (
              <li key={m.slot} className="rounded-lg border border-border bg-surface-2/50 px-3 py-2">
                <p className="flex flex-wrap items-center justify-between gap-2 text-sm text-text">
                  {m.task}
                  <span className={`rounded-full border px-2 py-px font-mono text-[10px] ${MODEL_STYLE[m.status] ?? STATUS_STYLE.unavailable}`}>
                    {m.status === 'RAN' ? 'MODEL RAN' : m.status}
                  </span>
                </p>
                {m.candidate && <p className="mt-0.5 font-mono text-[11px] text-accent">{m.candidate}</p>}
                {m.detail && <p className={`mt-1 text-xs ${m.status === 'RAN' ? 'text-text' : 'text-muted'}`}>{m.detail}</p>}
                {(m.limitations ?? []).length > 0 && (
                  <details className="mt-1.5 text-xs text-muted">
                    <summary className="cursor-pointer select-none hover:text-text">Known limits of this model</summary>
                    <ul className="mt-1 list-disc space-y-0.5 pl-4">
                      {m.limitations.map((l) => (
                        <li key={l}>{l}</li>
                      ))}
                    </ul>
                  </details>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {meta.length > 0 && (
        <div>
          <h2 className="section-title mb-2">Metadata findings</h2>
          <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2 lg:grid-cols-3">
            {meta.map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3 border-b border-border/50 py-1">
                <dt className="text-muted">{META_LABEL[k] ?? k}</dt>
                <dd className="min-w-0 truncate font-mono text-text" title={String(v)}>
                  {String(v)}
                </dd>
              </div>
            ))}
          </dl>
          <p className="mt-2 text-xs text-muted">Read from the file's container. Tags can be stripped or changed, so they are facts about this copy, not proof of origin.</p>
        </div>
      )}
    </div>
  )
}
