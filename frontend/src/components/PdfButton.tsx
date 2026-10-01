import { useState } from 'react'
import { downloadPdfReport } from '../services/api'
import type { TrustReport } from '../types/report'

const FALLBACK = 'PDF generation is temporarily unavailable. Your TrustLens analysis is still available.'

/** "Generate PDF Report": the backend builds the PDF from this report; the page and analysis stay as they are. */
export default function PdfButton({ report }: { report: TrustReport }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onClick = async () => {
    setBusy(true)
    setError(null)
    try {
      await downloadPdfReport(report)
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : FALLBACK)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <button
        type="button"
        onClick={onClick}
        disabled={busy}
        className="inline-flex items-center gap-2 rounded-lg border border-accent-soft bg-surface-2 px-4 py-2 text-sm font-medium text-accent transition-colors hover:border-accent disabled:cursor-wait disabled:opacity-70"
      >
        <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <path d="M12 4v11m0 0l-4-4m4 4l4-4M5 19h14" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {busy ? 'Preparing your TrustLens report…' : 'Generate PDF Report'}
      </button>
      <p role="status" className={`text-sm ${error ? 'text-[#F87171]' : 'text-muted'}`}>
        {error ?? (busy ? '' : 'Downloads a PDF of this analysis.')}
      </p>
    </div>
  )
}
