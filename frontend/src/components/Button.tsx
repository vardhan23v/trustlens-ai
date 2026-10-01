import type { ButtonHTMLAttributes, PointerEvent } from 'react'
import { useMagnetic } from '../hooks/useMagnetic'
import { prefersReducedMotion } from '../utils/format'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'ghost' | 'chip'
  /** Shows the loading style (primary only). */
  busy?: boolean
}

/** The one button: gradient + shine + magnetic pull (primary), ripple from the click point, press scale. */
export default function Button({ variant = 'ghost', busy, className = '', onPointerDown, children, ...rest }: Props) {
  const ref = useMagnetic<HTMLButtonElement>(variant === 'primary' ? 0.22 : 0.12, variant !== 'chip')

  const ripple = (e: PointerEvent<HTMLButtonElement>) => {
    onPointerDown?.(e)
    const el = e.currentTarget
    if (el.disabled || prefersReducedMotion()) return
    const r = el.getBoundingClientRect()
    const dot = document.createElement('span')
    dot.className = 'ripple'
    dot.style.left = `${e.clientX - r.left}px`
    dot.style.top = `${e.clientY - r.top}px`
    el.appendChild(dot)
    dot.addEventListener('animationend', () => dot.remove(), { once: true })
  }

  return (
    <button
      ref={ref}
      type="button"
      data-busy={busy ? '' : undefined}
      onPointerDown={ripple}
      className={`btn btn-${variant} ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
}
