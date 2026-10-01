import { useEffect, useState } from 'react'

export default function Header() {
  const [scrolled, setScrolled] = useState(false)
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])
  return (
    <header
      className={`sticky top-0 z-30 -mx-4 flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b px-4 py-3 transition-[background-color,border-color] duration-300 ${
        scrolled ? 'border-border bg-bg/85 backdrop-blur-md shadow-[0_1px_0_0_var(--mode-a)]' : 'border-transparent'
      }`}
    >
      <div className="logo flex items-center gap-3">
        <span className="grid size-10 place-items-center rounded-xl border border-accent/30 bg-accent/10">
          <svg viewBox="0 0 32 32" fill="none" className="logo-lid size-7 text-accent" aria-hidden="true">
            <path
              d="M3 16c3.200-5.800 7.700-9 13-9s9.800 3.200 13 9c-3.200 5.800-7.700 9-13 9S6.200 21.800 3 16Z"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinejoin="round"
            />
            <circle cx="16" cy="16" r="4.750" stroke="currentColor" strokeWidth="2" />
            <circle className="logo-eye" cx="16" cy="16" r="1.600" fill="currentColor" />
          </svg>
        </span>
        <div>
          <h1 className="text-xl font-bold leading-tight tracking-tight text-text">
            TrustLens <span className="mode-gradient-text">AI</span>
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
