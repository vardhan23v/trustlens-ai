import type { Intent } from '../types/report'

interface Props {
  value: Intent | null
  onChange: (intent: Intent) => void
  disabled?: boolean
}

export const INTENT_COPY: Record<
  Intent,
  { title: string; question: string; description: string; examples: string[]; upload: string; report: string }
> = {
  synthetic_detection: {
    title: 'AI / Synthetic Detection',
    question: 'Was this media generated or manipulated?',
    description:
      'Check whether this image or screenshot shows signs of AI generation, synthetic creation, or digital manipulation.',
    examples: ['AI-generated image', 'AI-generated screenshot', 'Heavily edited photo', 'Manipulated visual'],
    upload: 'upload the image you want to examine.',
    report: 'AI / Synthetic Detection Report',
  },
  artifact_authenticity: {
    title: 'Artifact Authenticity & Deception',
    question: 'Does this show a genuine message, transaction or document?',
    description:
      'Check whether this appears to be a genuine real-world artifact or a fabricated/deceptive screenshot.',
    examples: ['Payment / UPI screenshot', 'Email or SMS', 'Government notice', 'Invoice or receipt', 'Social post'],
    upload: 'upload the screenshot you want to verify.',
    report: 'Artifact Authenticity Report',
  },
}

function Icon({ intent }: { intent: Intent }) {
  // sparkle = generated media; document with check = real-world artifact
  return intent === 'synthetic_detection' ? (
    <svg viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8L12 3z" strokeLinejoin="round" />
      <path d="M18.5 15.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8.8-2z" strokeLinejoin="round" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M7 3h7l4 4v14H7V3z" strokeLinejoin="round" />
      <path d="M14 3v4h4" strokeLinejoin="round" />
      <path d="M9.5 14.5l2 2 3.5-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export default function IntentCards({ value, onChange, disabled }: Props) {
  return (
    <fieldset disabled={disabled} className="min-w-0">
      <legend className="section-title mb-3">What are you trying to verify?</legend>
      <div role="radiogroup" aria-label="What are you trying to verify?" className="grid gap-3 md:grid-cols-2">
        {(Object.keys(INTENT_COPY) as Intent[]).map((id) => {
          const c = INTENT_COPY[id]
          const selected = value === id
          return (
            <button
              key={id}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onChange(id)}
              className={`group relative rounded-xl border p-4 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                selected
                  ? 'border-accent bg-accent/10 shadow-[inset_0_0_0_1px_var(--color-accent)]'
                  : 'border-border bg-surface-2/60 hover:border-accent-soft'
              }`}
            >
              <div className="flex items-start gap-3">
                <span
                  className={`grid size-10 shrink-0 place-items-center rounded-lg border ${
                    selected ? 'border-accent text-accent' : 'border-border text-muted group-hover:text-accent'
                  }`}
                >
                  <Icon intent={id} />
                </span>
                <div className="min-w-0">
                  <p className="font-semibold text-text">{c.title}</p>
                  <p className={`mt-0.5 text-xs font-medium ${selected ? 'text-accent' : 'text-muted'}`}>{c.question}</p>
                </div>
                <span
                  aria-hidden="true"
                  className={`ml-auto mt-1 grid size-5 shrink-0 place-items-center rounded-full border text-[11px] ${
                    selected ? 'border-accent bg-accent text-bg' : 'border-border text-transparent'
                  }`}
                >
                  ✓
                </span>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-muted">{c.description}</p>
              <ul className="mt-3 flex flex-wrap gap-1.5">
                {c.examples.map((e) => (
                  <li key={e} className="rounded-full border border-border px-2 py-0.5 text-[11px] text-muted">
                    {e}
                  </li>
                ))}
              </ul>
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}
