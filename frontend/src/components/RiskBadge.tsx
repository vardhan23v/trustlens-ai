import type { RiskLevel, Verdict } from '../types/report'

interface Props {
  risk: RiskLevel
  verdict: Verdict | null
}

type Tone = 'low' | 'med' | 'high'

const TONE_CLASS: Record<Tone, string> = {
  low: 'border-risk-low/50 bg-risk-low/10 text-risk-low',
  med: 'border-risk-med/50 bg-risk-med/10 text-risk-med',
  high: 'border-risk-high/60 bg-risk-high/10 text-[#F87171]',
}

const TONE_DOT: Record<Tone, string> = { low: 'bg-risk-low', med: 'bg-risk-med', high: 'bg-risk-high' }

const RISK: Record<RiskLevel, { label: string; sub?: string; tone: Tone }> = {
  HIGH: { label: 'HIGH RISK', tone: 'high' },
  MEDIUM: { label: 'MEDIUM RISK', tone: 'med' },
  LOW: { label: 'NO RISK SIGNALS FOUND', sub: 'not verified as authentic', tone: 'low' },
}

const VERDICT: Record<Verdict, { label: string; sub?: string; tone: Tone }> = {
  VERIFIED_BY_SOURCE: { label: 'VERIFIED BY SOURCE', sub: 'based on the sources listed below', tone: 'low' },
  DEBUNKED_BY_SOURCE: { label: 'DEBUNKED BY SOURCE', sub: 'based on the sources listed below', tone: 'high' },
  UNVERIFIED: { label: 'UNVERIFIED', sub: 'no source-backed verdict available', tone: 'med' },
}

export default function RiskBadge({ risk, verdict }: Props) {
  const item = (verdict && VERDICT[verdict]) || RISK[risk] || RISK.MEDIUM
  return (
    <div>
      <span
        className={`inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-sm font-bold tracking-wide ${TONE_CLASS[item.tone]}`}
      >
        <span aria-hidden="true" className={`size-2 rounded-full ${TONE_DOT[item.tone]}`} />
        {item.label}
      </span>
      {item.sub && <p className="mt-1.5 pl-1 text-xs text-muted">{item.sub}</p>}
    </div>
  )
}
