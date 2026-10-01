import { useEffect, useRef } from 'react'
import { prefersReducedMotion } from '../utils/format'

/** The element leans a few pixels toward the pointer (writes --mx/--my; `.btn` turns them into a transform). */
export function useMagnetic<T extends HTMLElement>(strength = 0.25, enabled = true) {
  const ref = useRef<T>(null)
  useEffect(() => {
    const el = ref.current
    if (!el || !enabled || prefersReducedMotion() || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return
    const move = (e: PointerEvent) => {
      const r = el.getBoundingClientRect()
      el.style.setProperty('--mx', `${((e.clientX - r.left - r.width / 2) * strength).toFixed(1)}px`)
      el.style.setProperty('--my', `${((e.clientY - r.top - r.height / 2) * strength).toFixed(1)}px`)
    }
    const leave = () => {
      el.style.setProperty('--mx', '0px')
      el.style.setProperty('--my', '0px')
    }
    el.addEventListener('pointermove', move)
    el.addEventListener('pointerleave', leave)
    return () => {
      el.removeEventListener('pointermove', move)
      el.removeEventListener('pointerleave', leave)
    }
  }, [strength, enabled])
  return ref
}
