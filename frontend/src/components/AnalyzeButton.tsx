import Button from './Button'

interface Props {
  busy: boolean
  disabled?: boolean
  onClick: () => void
}

export default function AnalyzeButton({ busy, disabled, onClick }: Props) {
  return (
    <div className="flex flex-col items-stretch gap-2 sm:items-start">
      <Button variant="primary" busy={busy} onClick={onClick} disabled={busy || disabled}>
        {busy ? (
          <>
            <svg viewBox="0 0 24 24" fill="none" className="size-4 animate-spin" aria-hidden="true">
              <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.250" />
              <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
            </svg>
            Analyzing…
          </>
        ) : (
          <>
            <svg viewBox="0 0 24 24" fill="none" className="btn-icon size-4" aria-hidden="true">
              <circle cx="11" cy="11" r="6.500" stroke="currentColor" strokeWidth="2" />
              <path d="m16 16 4.500 4.500" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            Analyze with Gemini
          </>
        )}
      </Button>
      <p className="text-xs text-muted">Your file or text is sent to Gemini for analysis. Files are not kept; the report may be stored.</p>
    </div>
  )
}
