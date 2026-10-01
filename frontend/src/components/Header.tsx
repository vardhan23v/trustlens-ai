export default function Header() {
  return (
    <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 py-6">
      <div className="flex items-center gap-3">
        <span className="grid size-10 place-items-center rounded-xl border border-accent/30 bg-accent/10">
          <svg viewBox="0 0 32 32" fill="none" className="size-7 text-accent" aria-hidden="true">
            <path
              d="M3 16c3.200-5.800 7.700-9 13-9s9.800 3.200 13 9c-3.200 5.800-7.700 9-13 9S6.200 21.800 3 16Z"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinejoin="round"
            />
            <circle cx="16" cy="16" r="4.750" stroke="currentColor" strokeWidth="2" />
            <circle cx="16" cy="16" r="1.600" fill="currentColor" />
          </svg>
        </span>
        <div>
          <h1 className="text-xl font-bold leading-tight tracking-tight text-text">
            TrustLens <span className="text-accent">AI</span>
          </h1>
          <p className="text-sm text-muted">See Beyond the Digital Surface.</p>
        </div>
      </div>
      <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium text-muted">
        <span className="size-1.5 rounded-full bg-accent" aria-hidden="true" />
        Powered by Gemini · CrewAI
      </span>
    </header>
  )
}
