import type { Demo, Health, Mode } from '../types/report'
import AnalyzeButton from './AnalyzeButton'
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
  demos: Demo[]
  activeDemoId: string | null
  onPickDemo: (demo: Demo) => void
  health: Health | null
}

export default function InputPanel(props: Props) {
  const { mode, busy, health } = props
  const demos = props.demos.filter((d) => d.mode === mode)

  return (
    <section aria-label="Media to analyze" className="card p-4 sm:p-6">
      {!mode ? (
        <ModeCards value={mode} onChange={props.onModeChange} disabled={busy} />
      ) : (
        <div className="animate-fade-up space-y-4">
          {/* The selected mode stays visible for the whole run and on the report. */}
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-accent/60 bg-accent/10 px-4 py-3">
            <div className="min-w-0">
              <p className="text-[11px] font-medium uppercase tracking-wider text-muted">Mode</p>
              <p className="text-base font-bold tracking-wide text-accent">{MODE_COPY[mode].title}</p>
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={() => props.onModeChange(null)}
              className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-text transition-colors hover:border-accent-soft hover:text-accent disabled:cursor-not-allowed disabled:opacity-50"
            >
              Change mode
            </button>
          </div>
          <p className="text-sm text-text">{MODE_COPY[mode].upload}</p>
          <UploadZone file={props.file} previewUrl={props.previewUrl} onFile={props.onFile} disabled={busy} />
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
