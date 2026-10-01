import { useState } from 'react'
import { downloadPdfReport } from '../services/api'
import Button from './Button'
import { toast } from './PageChrome'
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
      <Button variant="ghost" onClick={onClick} disabled={busy} className="!px-4 !py-2 !text-sm" style={{ ['--icon-x' as string]: '0px', ['--icon-y' as string]: '2px' }}>
        <svg viewBox="0 0 24 24" className="btn-icon size-4" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <path d="M12 4v11m0 0l-4-4m4 4l4-4M5 19h14" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {busy ? 'Preparing your TrustLens report…' : 'Generate PDF Report'}
      </Button>
      <Button
        variant="ghost"
        className="!px-4 !py-2 !text-sm"
        onClick={() => {
          const a = report.overall_assessment
          const lines = [
            `TrustLens AI — ${report.mode === 'ai_generated' ? 'AI-Generated Media Analysis' : 'News / Claim Verification'}${report.report_id ? ` (${report.report_id})` : ''}`,
            ...(report.assessment_axes ?? []).map((x) => `${x.heading}: ${x.label}${x.confidence ? ` (confidence: ${x.confidence})` : ''}`),
            a && (report.assessment_axes ?? []).length === 0 ? `Assessment: ${a.label}` : '',
            `Risk indicator: ${report.trust_score}/100`,
            report.recommendation,
            report.disclaimer,
          ].filter(Boolean)
          navigator.clipboard
            .writeText(lines.join('\n'))
            .then(() => toast('Summary copied'))
            .catch(() => toast('Could not copy — select the text instead'))
        }}
      >
        <svg viewBox="0 0 24 24" className="btn-icon size-4" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <rect x="8" y="8" width="11" height="12" rx="2" />
          <path d="M5 15V6a2 2 0 0 1 2-2h8" strokeLinecap="round" />
        </svg>
        Copy summary
      </Button>
      <p role="status" className={`text-sm ${error ? 'text-[#F87171]' : 'text-muted'}`}>
        {error ?? (busy ? '' : 'Downloads a PDF of this analysis.')}
      </p>
    </div>
  )
}
