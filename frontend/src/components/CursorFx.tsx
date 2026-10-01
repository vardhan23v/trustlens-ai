import { useEffect, useRef } from 'react'
import { prefersReducedMotion } from '../utils/format'

const INTERACTIVE = 'a, button, [role="button"], [role="radio"], label, summary'
const TEXTUAL = 'textarea, input[type="text"], [contenteditable="true"]'

/**
 * Custom cursor for mouse users: a dot on the pointer, a ring that trails it and reacts to what is
 * underneath, a soft spotlight on the background, a ring on click, and a glow that follows the pointer
 * across cards. Renders nothing on touch devices or with reduced motion (the native cursor stays).
 */
export default function CursorFx() {
  const dot = useRef<HTMLDivElement>(null)
  const ring = useRef<HTMLDivElement>(null)
  const spot = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (prefersReducedMotion() || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return
    const d = dot.current
    const r = ring.current
    const s = spot.current
    if (!d || !r || !s) return
    const root = document.documentElement
    root.classList.add('has-cursor')
    let x = -100
    let y = -100
    let rx = x
    let ry = y
    let sx = x
    let sy = y
    let raf = 0
    let card: HTMLElement | null = null

    const flag = (el: HTMLElement, name: string, on: boolean) => {
      if (on) el.setAttribute(name, '')
      else el.removeAttribute(name)
    }
    const frame = () => {
      rx += (x - rx) * 0.2
      ry += (y - ry) * 0.2
      sx += (x - sx) * 0.07
      sy += (y - sy) * 0.07
      d.style.transform = `translate3d(${x}px, ${y}px, 0)`
      r.style.transform = `translate3d(${rx.toFixed(1)}px, ${ry.toFixed(1)}px, 0)`
      s.style.transform = `translate3d(${sx.toFixed(1)}px, ${sy.toFixed(1)}px, 0)`
      raf = requestAnimationFrame(frame)
    }
    const move = (e: PointerEvent) => {
      if (e.pointerType !== 'mouse') return
      x = e.clientX
      y = e.clientY
      const t = e.target instanceof Element ? e.target : null
      flag(r, 'data-hidden', false)
      flag(d, 'data-hidden', false)
      flag(r, 'data-text', !!t?.closest(TEXTUAL))
      flag(r, 'data-hover', !!t?.closest(INTERACTIVE))
      const c = t?.closest<HTMLElement>('.card') ?? null
      if (card && card !== c) {
        card.style.removeProperty('--gx')
        card.style.removeProperty('--gy')
      }
      card = c
      if (c) {
        const b = c.getBoundingClientRect()
        c.style.setProperty('--gx', `${x - b.left}px`)
        c.style.setProperty('--gy', `${y - b.top}px`)
      }
    }
    const down = (e: PointerEvent) => {
      if (e.pointerType !== 'mouse') return
      flag(r, 'data-down', true)
      const ringEl = document.createElement('span')
      ringEl.className = 'click-ring'
      ringEl.style.left = `${e.clientX}px`
      ringEl.style.top = `${e.clientY}px`
      document.body.appendChild(ringEl)
      ringEl.addEventListener('animationend', () => ringEl.remove(), { once: true })
    }
    const up = () => flag(r, 'data-down', false)
    const out = () => {
      flag(r, 'data-hidden', true)
      flag(d, 'data-hidden', true)
    }
    window.addEventListener('pointermove', move, { passive: true })
    window.addEventListener('pointerdown', down, { passive: true })
    window.addEventListener('pointerup', up, { passive: true })
    document.documentElement.addEventListener('pointerleave', out)
    raf = requestAnimationFrame(frame)
    return () => {
      cancelAnimationFrame(raf)
      root.classList.remove('has-cursor')
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerdown', down)
      window.removeEventListener('pointerup', up)
      document.documentElement.removeEventListener('pointerleave', out)
    }
  }, [])

  if (typeof window !== 'undefined' && (prefersReducedMotion() || !window.matchMedia('(hover: hover) and (pointer: fine)').matches)) {
    return null
  }
  return (
    <div aria-hidden="true">
      <div ref={spot} className="cursor-spot" />
      <div ref={ring} className="cursor-ring" data-hidden="">
        <i />
      </div>
      <div ref={dot} className="cursor-dot" data-hidden="" />
    </div>
  )
}
