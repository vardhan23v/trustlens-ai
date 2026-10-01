import { useEffect, useRef } from 'react'
import { prefersReducedMotion } from '../utils/format'

/**
 * Pointer-driven 3D tilt. Writes --rx/--ry (degrees) and --gx/--gy (glare position) on the element;
 * the `.tilt` CSS class turns them into a transform. Off on touch devices and with reduced motion.
 */
export function useTilt<T extends HTMLElement>(max = 6) {
  const ref = useRef<T>(null)
  useEffect(() => {
    const el = ref.current
    if (!el || prefersReducedMotion() || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return
    let raf = 0
    const move = (e: PointerEvent) => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        const r = el.getBoundingClientRect()
        const x = (e.clientX - r.left) / r.width
        const y = (e.clientY - r.top) / r.height
        el.style.setProperty('--ry', `${((x - 0.5) * 2 * max).toFixed(2)}deg`)
        el.style.setProperty('--rx', `${((0.5 - y) * 2 * max).toFixed(2)}deg`)
        el.style.setProperty('--gx', `${(x * 100).toFixed(1)}%`)
        el.style.setProperty('--gy', `${(y * 100).toFixed(1)}%`)
      })
    }
    const leave = () => {
      cancelAnimationFrame(raf)
      el.style.setProperty('--rx', '0deg')
      el.style.setProperty('--ry', '0deg')
    }
    el.addEventListener('pointermove', move)
    el.addEventListener('pointerleave', leave)
    return () => {
      cancelAnimationFrame(raf)
      el.removeEventListener('pointermove', move)
      el.removeEventListener('pointerleave', leave)
    }
  }, [max])
  return ref
}
