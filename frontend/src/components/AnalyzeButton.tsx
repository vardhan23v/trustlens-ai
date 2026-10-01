interface Props {
  busy: boolean
  disabled?: boolean
  onClick: () => void
}

export default function AnalyzeButton({ busy, disabled, onClick }: Props) {
  return (
    <div className="flex flex-col items-stretch gap-2 sm:items-start">
      <button
        type="button"
        onClick={onClick}
        disabled={busy || disabled}
        className="inline-flex items-center justify-center gap-2 rounded-xl bg-accent px-6 py-3 text-sm font-semibold text-bg transition hover:brightness-110 disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-muted"
      >
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
            <svg viewBox="0 0 24 24" fill="none" className="size-4" aria-hidden="true">
              <circle cx="11" cy="11" r="6.500" stroke="currentColor" strokeWidth="2" />
              <path d="m16 16 4.500 4.500" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            Analyze with Gemini
          </>
        )}
      </button>
      <p className="text-xs text-muted">Not stored. Sent to Gemini for analysis only.</p>
    </div>
  )
}
