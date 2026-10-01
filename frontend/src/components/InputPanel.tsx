import type { Demo, Health, InputType } from '../types/report'
import AnalyzeButton from './AnalyzeButton'
import DemoChips from './DemoChips'
import DropZone from './DropZone'
import TextArea from './TextArea'

interface Props {
  mode: InputType
  onModeChange: (mode: InputType) => void
  onSubmit: () => void
  busy: boolean
  canSubmit: boolean
  text: string
  onTextChange: (value: string) => void
  file: File | null
  previewUrl: string | null
  onFile: (file: File | null) => void
  demos: Demo[]
  activeDemoId: string | null
  onPickDemo: (demo: Demo) => void
  health: Health | null
}

const TABS: { id: InputType; label: string }[] = [
  { id: 'image', label: 'Screenshot / Image' },
  { id: 'text', label: 'Message / Text' },
  { id: 'claim', label: 'News Claim' },
]

const PLACEHOLDER: Record<'text' | 'claim', string> = {
  text: 'Paste SMS / WhatsApp / email…',
  claim: 'Paste the viral claim or forwarded message…',
}

export default function InputPanel(props: Props) {
  const { mode, onModeChange, busy, health } = props

  return (
    <section aria-label="Content to analyze" className="card p-4 sm:p-6">
      <div
        role="tablist"
        aria-label="Input type"
        className="grid grid-cols-3 gap-1 rounded-xl border border-border bg-bg/60 p-1 sm:inline-grid"
      >
        {TABS.map((t) => {
          const selected = t.id === mode
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              id={`tab-${t.id}`}
              aria-selected={selected}
              aria-controls="input-tabpanel"
              disabled={busy}
              onClick={() => onModeChange(t.id)}
              className={`rounded-lg px-2 py-2 text-xs font-medium transition-colors disabled:cursor-not-allowed sm:px-4 sm:text-sm ${
                selected ? 'bg-surface-2 text-accent shadow-[inset_0_0_0_1px_var(--color-border)]' : 'text-muted hover:text-text'
              }`}
            >
              {t.label}
            </button>
          )
        })}
      </div>

      <div id="input-tabpanel" role="tabpanel" aria-labelledby={`tab-${mode}`} className="mt-4">
        {mode === 'image' ? (
          <DropZone file={props.file} previewUrl={props.previewUrl} onFile={props.onFile} disabled={busy} />
        ) : (
          <TextArea
            value={props.text}
            onChange={props.onTextChange}
            placeholder={PLACEHOLDER[mode]}
            label={mode === 'claim' ? 'News claim to check' : 'Message text to analyze'}
            disabled={busy}
          />
        )}
      </div>

      <div className="mt-4">
        <DemoChips demos={props.demos} activeId={props.activeDemoId} onPick={props.onPickDemo} disabled={busy} />
      </div>

      <div className="mt-5 flex flex-wrap items-end justify-between gap-4">
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
              <span>Gemini key not configured — rule-based results only</span>
            )}
          </p>
        )}
      </div>
    </section>
  )
}
