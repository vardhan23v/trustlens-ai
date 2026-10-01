export const STAGES = [
  'Reading content',
  'Extracting information',
  'Checking metadata',
  'Running rule checks',
  'Checking suspicious signals',
  'Gemini reasoning',
  'Calculating trust score',
  'Generating Trust Report',
] as const

/** Index the timed animation holds on until the response arrives. */
export const HOLD_STAGE = STAGES.indexOf('Gemini reasoning')

interface Props {
  /** Index of the active stage; stages below it are done. `STAGES.length` = all done. */
  stage: number
}

export default function StageProgress({ stage }: Props) {
  const current = STAGES[Math.min(stage, STAGES.length - 1)]
  return (
    <section aria-label="Analysis progress" className="card animate-fade-up p-4 sm:p-6">
      <p className="sr-only" role="status">
        {stage >= STAGES.length ? 'Finishing' : `Step ${stage + 1} of ${STAGES.length}: ${current}`}
      </p>
      <ol className="grid gap-3 md:grid-cols-8 md:gap-2" aria-hidden="true">
        {STAGES.map((label, i) => {
          const done = i < stage
          const active = i === stage
          return (
            <li key={label} className="relative flex items-center gap-3 md:flex-col md:gap-2 md:text-center">
              {i > 0 && (
                <span
                  className={`absolute top-3.5 right-1/2 hidden h-px w-full -translate-y-1/2 md:block ${
                    i <= stage ? 'bg-accent-soft' : 'bg-border'
                  }`}
                />
              )}
              <span
                className={`relative z-10 grid size-7 shrink-0 place-items-center rounded-full border font-mono text-xs transition-colors duration-200 ${
                  done
                    ? 'border-accent bg-accent text-bg'
                    : active
                      ? 'animate-stage-pulse border-accent bg-surface text-accent'
                      : 'border-border bg-surface text-muted/60'
                }`}
              >
                {done ? '✓' : i + 1}
              </span>
              <span
                className={`text-sm leading-snug transition-colors duration-200 md:text-xs ${
                  done ? 'text-text' : active ? 'font-medium text-accent' : 'text-muted/60'
                }`}
              >
                {label}
              </span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
