import { useEffect } from 'react'

/**
 * Scroll reveal for the whole page. Any element with class `reveal` gets `data-revealed` the first
 * time it scrolls into view (CSS does the 3D entrance). One observer; new elements (a report that
 * renders later) are picked up through a MutationObserver.
 */
export function useRevealAll(): void {
  useEffect(() => {
    const show = (el: Element) => el.setAttribute('data-revealed', '')
    if (!('IntersectionObserver' in window)) {
      document.querySelectorAll('.reveal').forEach(show)
      return
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            show(e.target)
            io.unobserve(e.target)
          }
        }
      },
      { rootMargin: '0px 0px -8% 0px', threshold: 0.08 },
    )
    const watch = (root: ParentNode) =>
      root.querySelectorAll('.reveal:not([data-revealed])').forEach((el) => io.observe(el))
    watch(document)
    const mo = new MutationObserver((muts) => {
      for (const m of muts) {
        m.addedNodes.forEach((n) => {
          if (!(n instanceof Element)) return
          if (n.classList.contains('reveal') && !n.hasAttribute('data-revealed')) io.observe(n)
          watch(n)
        })
      }
    })
    mo.observe(document.body, { childList: true, subtree: true })
    return () => {
      io.disconnect()
      mo.disconnect()
    }
  }, [])
}
