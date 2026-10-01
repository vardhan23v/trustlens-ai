import type { Source } from '../types/report'

interface Props {
  source: Source
}

const STYLE: Record<Source, string> = {
  RULE: 'border-rule bg-rule/25',
  GEMINI: 'border-gemini bg-gemini/20',
}

const TITLE: Record<Source, string> = {
  RULE: 'Detected by a deterministic rule',
  GEMINI: 'Identified by Gemini reasoning',
}

export default function SourceBadge({ source }: Props) {
  return (
    <span
      title={TITLE[source]}
      className={`inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold tracking-wider text-text ${
        STYLE[source] ?? 'border-border bg-surface-2'
      }`}
    >
      {source}
    </span>
  )
}
