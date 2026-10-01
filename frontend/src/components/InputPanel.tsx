import type { Demo, Health, Mode } from '../types/report'
import AnalyzeButton from './AnalyzeButton'
import Button from './Button'
import DemoChips from './DemoChips'
import ModeCards, { MODE_COPY } from './ModeCards'
import UploadZone from './UploadZone'

interface Props {
  mode: Mode | null
  onModeChange: (mode: Mode | null) => void
  onSubmit: () => void
  busy: boolean
  canSubmit: boolean
  file: File | null
  previewUrl: string | null
  onFile: (file: File | null) => void
  text: string
  onText: (value: string) => void
  demos: Demo[]
  activeDemoId: string | null
  onPickDemo: (demo: Demo) => void
  health: Health | null
}

const TEXT_COPY: Record<Mode, { label: string; placeholder: string; hint: string }> = {
  news_claim: {
    label: 'Claim, headline or message to verify',
    placeholder: 'Paste a headline, viral claim or forwarded message…',
    hint: 'The claim is checked against news and fact-check sources.',
  },
  ai_generated: {
    label: 'Text to check for AI writing',
    placeholder: 'Paste a paragraph or more to check for signs of AI-generated writing…',
    hint: 'Needs at least about 40 words. AI-text detection is unreliable; the result is a likelihood, not proof.',
  },
}

export default function InputPanel(props: Props) {
  const { mode, busy, health } = props
  const demos = props.demos.filter((d) => d.mode === mode)

  return (
    <section aria-label="Media to analyze" className="card card-glow p-4 sm:p-6">
      {!mode ? (
        <ModeCards value={mode} onChange={props.onModeChange} disabled={busy} />
      ) : (
        <div className="animate-fade-up space-y-4">
          {/* The selected mode stays visible for the whole run and on the report. */}
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-accent/60 bg-accent/10 px-4 py-3">
            <div className="min-w-0">
              <p className="text-[11px] font-medium uppercase tracking-wider text-muted">Mode</p>
              <p className="mode-gradient-text text-lg font-bold tracking-wide">{MODE_COPY[mode].title}</p>
            </div>
            <Button variant="ghost" disabled={busy} onClick={() => props.onModeChange(null)} style={{ ['--icon-x' as string]: '-3px' }}>
              <span aria-hidden="true" className="btn-icon">
                ←
              </span>
              Change mode
            </Button>
          </div>
          <p className="text-sm text-text">{MODE_COPY[mode].upload}</p>
          <UploadZone file={props.file} previewUrl={props.previewUrl} onFile={props.onFile} disabled={busy} />
          <div>
            <div className="mb-2 flex items-center gap-3 text-[11px] font-medium uppercase tracking-wider text-muted">
              <span className="h-px flex-1 bg-border" />
              or paste text
              <span className="h-px flex-1 bg-border" />
            </div>
            <label htmlFor="text-input" className="sr-only">
              {TEXT_COPY[mode].label}
            </label>
            <textarea
              id="text-input"
              value={props.text}
              onChange={(e) => props.onText(e.target.value)}
              disabled={busy}
              rows={5}
              maxLength={8000}
              placeholder={TEXT_COPY[mode].placeholder}
              className="w-full resize-y rounded-xl border border-border bg-bg/60 p-3 text-sm text-text placeholder:text-muted/70 focus:border-accent focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
            />
            <p className="mt-1 flex justify-between gap-3 text-xs text-muted">
              <span>{TEXT_COPY[mode].hint}</span>
              <span className="shrink-0 font-mono">{props.text.length} / 8000</span>
            </p>
          </div>
          {demos.length > 0 && (
            <DemoChips demos={demos} activeId={props.activeDemoId} onPick={props.onPickDemo} disabled={busy} />
          )}
          <div className="flex flex-wrap items-end justify-between gap-4 pt-1">
            <AnalyzeButton busy={busy} disabled={!props.canSubmit} onClick={props.onSubmit} />
            {health && (
              <p className="flex items-center gap-2 text-xs text-muted">
                <span
                  aria-hidden="true"
                  className={`size-1.5 rounded-full ${health.gemini_configured ? 'bg-risk-low' : 'bg-risk-med'}`}
                />
                {health.gemini_configured ? (
                  <span className="font-mono">{health.gemini_model}</span>
                ) : (
                  <span>Gemini key not configured — deterministic checks only</span>
                )}
              </p>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
