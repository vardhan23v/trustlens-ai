import type { Demo } from '../types/report'

interface Props {
  demos: Demo[]
  activeId: string | null
  onPick: (demo: Demo) => void
  disabled?: boolean
}

const TYPE_GLYPH: Record<string, string> = { image: '▣', claim: '❝' }

export default function DemoChips({ demos, activeId, onPick, disabled }: Props) {
  if (demos.length === 0) return null
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-medium uppercase tracking-wider text-muted">Try a demo</span>
      {demos.map((d) => {
        const active = d.id === activeId
        return (
          <button
            key={d.id}
            type="button"
            disabled={disabled}
            onClick={() => onPick(d)}
            title="Cached demo — Gemini output pre-recorded"
            aria-pressed={active}
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
              active
                ? 'border-accent bg-accent/15 text-accent'
                : 'border-border bg-surface-2 text-text hover:border-accent-soft hover:text-accent'
            }`}
          >
            <span aria-hidden="true" className="text-muted">
              {TYPE_GLYPH[d.input_type] ?? '•'}
            </span>
            {d.label}
          </button>
        )
      })}
    </div>
  )
}
