import type { Extracted } from '../types/report'

interface Props {
  extracted: Extracted
}

interface Row {
  label: string
  value: string | string[]
  mono?: boolean
}

export default function ExtractedPanel({ extracted: x }: Props) {
  const rows: Row[] = [
    { label: 'Classification', value: x.classification },
    { label: 'Sender', value: x.sender },
    { label: 'Sender domain', value: x.sender_domain, mono: true },
    { label: 'Company', value: x.company },
    { label: 'Person', value: x.person },
    { label: 'Claim', value: x.claim },
    { label: 'Date', value: x.date },
    { label: 'URLs', value: x.urls, mono: true },
    { label: 'Phone numbers', value: x.phone_numbers, mono: true },
    { label: 'Email addresses', value: x.email_addresses, mono: true },
    { label: 'Money amounts', value: x.money_amounts, mono: true },
    { label: 'Requested action', value: x.requested_action },
    { label: 'Extracted text', value: x.extracted_text, mono: true },
  ].filter((r) => (Array.isArray(r.value) ? r.value.length > 0 : !!r.value && r.value.trim() !== ''))

  if (rows.length === 0) return null

  return (
    <details className="card group reveal">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-xl p-4 sm:px-6 [&::-webkit-details-marker]:hidden">
        <span className="section-title">Extracted information</span>
        <span className="flex items-center gap-2 text-xs text-muted">
          {rows.length} fields
          <svg
            viewBox="0 0 20 20"
            fill="none"
            className="size-4 transition-transform group-open:rotate-180"
            aria-hidden="true"
          >
            <path d="m5 7.500 5 5 5-5" stroke="currentColor" strokeWidth="1.800" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
      </summary>
      <dl className="grid gap-x-6 gap-y-3 border-t border-border p-4 sm:grid-cols-[11rem_1fr] sm:p-6">
        {rows.map((r) => (
          <div key={r.label} className="contents">
            <dt className="text-xs font-medium uppercase tracking-wider text-muted sm:pt-0.5">{r.label}</dt>
            <dd
              className={`min-w-0 text-sm break-words whitespace-pre-wrap text-text ${r.mono ? 'font-mono text-[13px]' : ''}`}
            >
              {Array.isArray(r.value) ? (
                <ul className="space-y-1">
                  {r.value.map((v, i) => (
                    <li key={i} className="break-all">
                      {v}
                    </li>
                  ))}
                </ul>
              ) : (
                r.value
              )}
            </dd>
          </div>
        ))}
      </dl>
    </details>
  )
}
