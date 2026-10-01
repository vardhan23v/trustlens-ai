import { useEffect, useState } from 'react'
import Button from './Button'

/** Fired by `toast()`; shown by <Toaster />. */
const EVENT = 'trustlens:toast'

export function toast(message: string): void {
  window.dispatchEvent(new CustomEvent<string>(EVENT, { detail: message }))
}

export function Toaster() {
  const [msg, setMsg] = useState<{ id: number; text: string } | null>(null)
  useEffect(() => {
    let timer = 0
    const on = (e: Event) => {
      window.clearTimeout(timer)
      setMsg({ id: Date.now(), text: (e as CustomEvent<string>).detail })
      timer = window.setTimeout(() => setMsg(null), 2200)
    }
    window.addEventListener(EVENT, on)
    return () => {
      window.clearTimeout(timer)
      window.removeEventListener(EVENT, on)
    }
  }, [])
  return (
    <div aria-live="polite" role="status" className="pointer-events-none fixed inset-x-0 bottom-6 z-[70] flex justify-center px-4">
      {msg && (
        <p key={msg.id} className="float-in rounded-full border border-accent/60 bg-surface px-4 py-2 text-sm font-medium text-text shadow-[0_10px_40px_-12px_var(--mode-a)]">
          <span aria-hidden="true" className="mr-2 text-accent">
            ✓
          </span>
          {msg.text}
        </p>
      )}
    </div>
  )
}

/** Thin reading-progress line at the top, and a back-to-top button once the page is scrolled. */
export function ScrollChrome() {
  const [far, setFar] = useState(false)
  useEffect(() => {
    let raf = 0
    const on = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        const max = document.documentElement.scrollHeight - window.innerHeight
        document.documentElement.style.setProperty('--progress', max > 0 ? (window.scrollY / max).toFixed(4) : '0')
        setFar(window.scrollY > 700)
      })
    }
    on()
    window.addEventListener('scroll', on, { passive: true })
    window.addEventListener('resize', on)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('scroll', on)
      window.removeEventListener('resize', on)
    }
  }, [])
  return (
    <>
      <div aria-hidden="true" className="scroll-progress" />
      {far && (
        <div className="float-in fixed bottom-6 right-5 z-50">
          <Button
            variant="ghost"
            aria-label="Back to top"
            title="Back to top"
            className="!size-11 !rounded-full !p-0 text-lg"
            style={{ ['--icon-x' as string]: '0px', ['--icon-y' as string]: '-3px' }}
            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          >
            <span className="btn-icon" aria-hidden="true">
              ↑
            </span>
          </Button>
        </div>
      )}
    </>
  )
}

const SHORTCUTS: [string, string][] = [
  ['1', 'News / Claim mode'],
  ['2', 'AI-Generated mode'],
  ['Enter', 'Analyze (when a file or text is ready)'],
  ['Esc', 'Back to mode selection'],
  ['Ctrl / ⌘ + V', 'Paste a copied image'],
  ['?', 'Show or hide this list'],
]

export function ShortcutsHelp({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <div className="fixed bottom-6 left-5 z-50 hidden md:block">
      {open && (
        <div role="dialog" aria-label="Keyboard shortcuts" className="float-in card mb-3 w-72 p-4 shadow-[0_20px_60px_-20px_var(--mode-a)]">
          <p className="section-title mb-2">Keyboard shortcuts</p>
          <dl className="space-y-1.5 text-sm">
            {SHORTCUTS.map(([k, v]) => (
              <div key={k} className="flex items-center justify-between gap-3">
                <dt>
                  <kbd className="rounded-md border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-xs text-accent">{k}</kbd>
                </dt>
                <dd className="text-right text-muted">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
      <Button variant="ghost" aria-label="Keyboard shortcuts" aria-expanded={open} title="Keyboard shortcuts" className="!size-11 !rounded-full !p-0 font-mono text-base" onClick={onToggle}>
        ?
      </Button>
    </div>
  )
}

export function DropOverlay({ show }: { show: boolean }) {
  if (!show) return null
  return (
    <div className="drop-overlay" aria-hidden="true">
      <div>
        <p className="mode-gradient-text text-2xl font-bold">Drop to analyse</p>
        <p className="mt-2 text-sm text-muted">Image, video or audio</p>
      </div>
    </div>
  )
}
