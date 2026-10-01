import { useEffect, useState } from 'react'
import { prefersReducedMotion } from '../utils/format'

export interface Section {
  id: string
  label: string
}

/** Sticky row of chips on a report: jumps to a section and highlights the one in view. */
export default function SectionNav({ sections }: { sections: Section[] }) {
  const [active, setActive] = useState(sections[0]?.id ?? '')
  useEffect(() => {
    const els = sections.map((s) => document.getElementById(s.id)).filter((e): e is HTMLElement => !!e)
    if (!('IntersectionObserver' in window) || els.length === 0) return
    const io = new IntersectionObserver(
      (entries) => {
        const seen = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        if (seen[0]) setActive(seen[0].target.id)
      },
      { rootMargin: '-25% 0px -60% 0px' },
    )
    els.forEach((e) => io.observe(e))
    return () => io.disconnect()
  }, [sections])

  return (
    <nav aria-label="Report sections" className="sticky top-[4.6rem] z-20 -mx-1 overflow-x-auto rounded-full border border-border bg-bg/85 p-1 backdrop-blur-md">
      <ul className="flex w-max gap-1">
        {sections.map((s) => (
          <li key={s.id}>
            <button
              type="button"
              data-active={active === s.id ? '' : undefined}
              aria-current={active === s.id ? 'true' : undefined}
              className="btn btn-chip !border-transparent !bg-transparent data-[active]:!border-accent data-[active]:!bg-accent/15"
              onClick={() =>
                document.getElementById(s.id)?.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' })
              }
            >
              {s.label}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )
}
