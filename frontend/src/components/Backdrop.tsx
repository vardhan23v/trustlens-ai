import { useEffect } from 'react'
import { prefersReducedMotion } from '../utils/format'

/** Fixed background: a perspective grid floor and two glow orbs that drift with scroll (parallax). */
export default function Backdrop() {
  useEffect(() => {
    if (prefersReducedMotion()) return
    let raf = 0
    const onScroll = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() =>
        document.documentElement.style.setProperty('--scroll', String(Math.min(window.scrollY, 4000))),
      )
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('scroll', onScroll)
    }
  }, [])
  return (
    <div aria-hidden="true" className="backdrop">
      <div className="backdrop-orb backdrop-orb-a" />
      <div className="backdrop-orb backdrop-orb-b" />
      <div className="backdrop-floor" />
    </div>
  )
}
