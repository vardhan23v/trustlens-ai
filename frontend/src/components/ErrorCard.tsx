interface Props {
  message: string
}

export default function ErrorCard({ message }: Props) {
  return (
    <div
      role="alert"
      className="animate-fade-up flex items-start gap-3 rounded-xl border border-risk-high/60 bg-risk-high/10 p-4"
    >
      <svg viewBox="0 0 20 20" fill="none" className="mt-0.5 size-5 shrink-0 text-risk-high" aria-hidden="true">
        <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.600" />
        <path d="M10 6v4.500M10 13.500v.500" stroke="currentColor" strokeWidth="1.800" strokeLinecap="round" />
      </svg>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-[#FCA5A5]">Analysis could not be completed</p>
        <p className="mt-0.5 text-sm break-words text-text/90">{message}</p>
      </div>
    </div>
  )
}
