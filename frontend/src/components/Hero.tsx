import Button from './Button'
import { useRef } from 'react'
import { prefersReducedMotion } from '../utils/format'

const VERBS = ['Detect', 'Verify', 'Trace', 'Secure', 'Build Trust']

interface Props {
  onStart: () => void
}

/** Intro section with a CSS-only 3D "lens": stacked rings on different depths that follow the pointer. */
export default function Hero({ onStart }: Props) {
  const scene = useRef<HTMLDivElement>(null)

  const onMove = (e: React.PointerEvent<HTMLElement>) => {
    const el = scene.current
    if (!el || prefersReducedMotion() || e.pointerType !== 'mouse') return
    const r = e.currentTarget.getBoundingClientRect()
    el.style.setProperty('--px', ((e.clientX - r.left) / r.width - 0.5).toFixed(3))
    el.style.setProperty('--py', ((e.clientY - r.top) / r.height - 0.5).toFixed(3))
  }

  return (
    <section
      aria-label="Introduction"
      onPointerMove={onMove}
      className="grid items-center gap-8 pb-10 pt-6 md:grid-cols-[1.1fr_1fr] md:pb-16 md:pt-12"
    >
      <div>
        <p className="hero-in inline-flex items-center gap-2 rounded-full border border-accent-soft/60 bg-accent/5 px-3 py-1 text-xs font-medium text-accent">
          <span className="size-1.5 animate-glow-pulse rounded-full bg-accent" aria-hidden="true" />
          Gemini-powered Trust Checker
        </p>
        <h2 className="hero-in mt-5 text-4xl font-bold leading-[1.08] tracking-tight text-text [--d:80ms] sm:text-5xl lg:text-6xl">
          See Beyond the <span className="hero-gradient">Digital Surface.</span>
        </h2>
        <p className="hero-in mt-5 max-w-xl text-base leading-relaxed text-muted [--d:160ms] sm:text-lg">
          Upload an image, video or audio clip, or paste text. TrustLens returns an evidence-backed Trust Report:
          every signal shows what was found, the quoted evidence, and whether it came from a rule or from Gemini.
        </p>
        <ul className="hero-in mt-6 flex flex-wrap gap-2 [--d:240ms]" aria-label="What TrustLens does">
          {VERBS.map((v) => (
            <li key={v} className="rounded-full border border-border bg-surface/70 px-3 py-1 text-xs font-medium text-text">
              {v}
            </li>
          ))}
        </ul>
        <div className="hero-in mt-8 flex flex-wrap items-center gap-4 [--d:320ms]">
          <Button variant="primary" onClick={onStart} style={{ ['--icon-x' as string]: '0px', ['--icon-y' as string]: '3px' }}>
            Start analysis
            <span aria-hidden="true" className="btn-icon">
              ↓
            </span>
          </Button>
          <p className="text-sm text-muted">Don’t just tell users what to trust. Show them why.</p>
        </div>
      </div>

      <div ref={scene} className="lens-scene mx-auto" aria-hidden="true">
        <div className="lens">
          <span className="lens-ring lens-ring-1" />
          <span className="lens-ring lens-ring-2" />
          <span className="lens-ring lens-ring-3" />
          <span className="lens-ring lens-ring-4" />
          <span className="lens-core" />
          <span className="lens-scan" />
        </div>
        <span className="lens-chip lens-chip-a border-rule/60 text-[#A5B4FC]">RULE</span>
        <span className="lens-chip lens-chip-b border-gemini/60 text-[#5EEAD4]">GEMINI</span>
        <span className="lens-chip lens-chip-c border-risk-high/50 font-mono text-[#F87171]">22 / 100</span>
        <span className="lens-chip lens-chip-d border-border text-muted">EXIF · ELA</span>
      </div>
    </section>
  )
}
