import type { ReactNode } from 'react'
import { useTilt } from '../hooks/useTilt'
import type { Mode } from '../types/report'

interface Props {
  value: Mode | null
  onChange: (mode: Mode) => void
  disabled?: boolean
}

export const MODE_COPY: Record<
  Mode,
  { title: string; question: string; description: string; examples: string[]; upload: string; report: string }
> = {
  news_claim: {
    title: 'NEWS / CLAIM',
    question: 'Is the claim supported, and is the media authentic and in context?',
    description: 'Verify claims from news screenshots, videos, audio, and text.',
    examples: ['News screenshot', 'Viral forward', 'News clip', 'Voice note', 'Pasted claim or message'],
    upload: 'Upload a screenshot, video, or audio clip containing the claim you want to verify — or paste the text.',
    report: 'News / Claim Verification Report',
  },
  ai_generated: {
    title: 'AI-GENERATED',
    question: 'Is this media likely synthetic or manipulated?',
    description: 'Check whether images, videos, audio, or text show signs of synthetic generation or manipulation.',
    examples: ['AI-generated image', 'Edited photo', 'Deepfake video', 'Cloned voice', 'AI-written text'],
    upload: 'Upload an image, video, or audio clip to analyze for synthetic-media indicators — or paste text to check for AI writing.',
    report: 'AI-Generated Media Analysis',
  },
}

function Icon({ mode }: { mode: Mode }) {
  // newspaper with a check = claim verification; sparkle = generated media
  return mode === 'ai_generated' ? (
    <svg viewBox="0 0 24 24" className="size-7" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8L12 3z" strokeLinejoin="round" />
      <path d="M18.5 15.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8.8-2z" strokeLinejoin="round" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" className="size-7" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M4 5h13v14H6a2 2 0 0 1-2-2V5z" strokeLinejoin="round" />
      <path d="M17 9h3v8a2 2 0 0 1-2 2" strokeLinejoin="round" />
      <path d="M7 9h7M7 12h4" strokeLinecap="round" />
      <path d="M8.5 15.5l1.5 1.5 3-3.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function Tilt({ children }: { children: ReactNode }) {
  const ref = useTilt<HTMLDivElement>(5)
  return (
    <div ref={ref} className="tilt rounded-2xl">
      {children}
    </div>
  )
}

export default function ModeCards({ value, onChange, disabled }: Props) {
  return (
    <fieldset disabled={disabled} className="min-w-0">
      <legend className="section-title mb-3">What are you verifying?</legend>
      <div role="radiogroup" aria-label="What are you verifying?" className="grid gap-4 md:grid-cols-2">
        {(Object.keys(MODE_COPY) as Mode[]).map((id) => {
          const c = MODE_COPY[id]
          const selected = value === id
          return (
            <Tilt key={id}>
              <button
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => onChange(id)}
                className={`group relative h-full w-full rounded-2xl border p-5 text-left transition-[border-color,background-color,box-shadow] duration-200 disabled:cursor-not-allowed disabled:opacity-60 sm:p-6 ${
                  selected
                    ? 'border-accent bg-accent/10 shadow-[inset_0_0_0_1px_var(--color-accent),0_20px_44px_-24px_var(--color-accent)]'
                    : 'border-border bg-surface-2/60 hover:border-accent-soft'
                }`}
              >
                <div className="flex items-start gap-4">
                  <span
                    className={`grid size-12 shrink-0 place-items-center rounded-xl border ${
                      selected ? 'border-accent text-accent' : 'border-border text-muted group-hover:text-accent'
                    }`}
                  >
                    <Icon mode={id} />
                  </span>
                  <div className="min-w-0">
                    <p className="text-lg font-bold tracking-wide text-text">{c.title}</p>
                    <p className={`mt-0.5 text-xs font-medium ${selected ? 'text-accent' : 'text-muted'}`}>{c.question}</p>
                  </div>
                </div>
                <p className="mt-4 text-sm leading-relaxed text-muted">{c.description}</p>
                <ul className="mt-3 flex flex-wrap gap-1.5">
                  {c.examples.map((e) => (
                    <li key={e} className="rounded-full border border-border px-2 py-0.5 text-[11px] text-muted">
                      {e}
                    </li>
                  ))}
                </ul>
              </button>
            </Tilt>
          )
        })}
      </div>
    </fieldset>
  )
}
