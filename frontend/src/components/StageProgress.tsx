import type { MediaType, Mode } from '../types/report'
import { MODE_COPY } from './ModeCards'

interface Props {
  mode: Mode
  mediaType: MediaType
}

/** What this pipeline does for the chosen mode and file kind. It is a description, not a progress
 *  meter: the server reports which stages actually ran, and the report lists them afterwards. */
function plan(mode: Mode, kind: MediaType): string[] {
  if (kind === 'text') {
    return mode === 'ai_generated'
      ? ['Reading the writing for AI-generation traits', 'Evidence reconciliation']
      : ['Content rule checks', 'Claim extraction', 'Searching news and fact-check sources', 'Claim assessment']
  }
  const pre =
    kind === 'image'
      ? ['Metadata and compression checks']
      : kind === 'video'
        ? ['Container metadata', 'Keyframe sampling and audio extraction']
        : ['Container metadata']
  if (mode === 'ai_generated') {
    return [...pre, kind === 'image' ? 'Visual examination for synthetic indicators' : 'Examination of picture and sound', 'Evidence reconciliation']
  }
  return [
    ...pre,
    kind === 'image' ? 'Reading the text and the claim in the image' : 'Transcription and claim extraction',
    'Searching news and fact-check sources',
    'Claim, media and context assessed separately',
  ]
}

export default function StageProgress({ mode, mediaType }: Props) {
  return (
    <section aria-label="Analysis in progress" className="card animate-fade-up p-4 sm:p-6">
      <div className="flex items-center gap-3" role="status">
        <span aria-hidden="true" className="size-5 shrink-0 animate-spin rounded-full border-2 border-border border-t-accent" />
        <p className="text-sm font-medium text-accent">
          {MODE_COPY[mode].title}: analysing your {mediaType}…
        </p>
      </div>
      <p className="mt-2 text-xs text-muted">
        {mediaType === 'image' || mediaType === 'text' ? 'This usually takes 10–40 seconds.' : 'Video and audio can take up to two minutes.'} The
        report lists which of these stages actually ran.
      </p>
      <ol className="mt-4 grid gap-2 sm:grid-cols-2">
        {plan(mode, mediaType).map((label, i) => (
          <li key={label} className="flex items-center gap-3 rounded-lg border border-border bg-surface-2/50 px-3 py-2 text-sm text-muted">
            <span className="grid size-6 shrink-0 place-items-center rounded-full border border-border font-mono text-xs">{i + 1}</span>
            {label}
          </li>
        ))}
      </ol>
    </section>
  )
}
