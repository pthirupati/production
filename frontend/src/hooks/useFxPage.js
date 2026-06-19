import { useEffect, useRef, useState, useCallback } from 'react'

/** Scroll progress, parallax, back-to-top, nav shrink — from Claude mockup pages. */
export function useFxPage({ motion = true } = {}) {
  const progressRef = useRef(null)
  const toTopRef = useRef(null)
  const navRef = useRef(null)
  const spotRef = useRef(null)
  const [scrollY, setScrollY] = useState(0)

  useEffect(() => {
    if (!motion) return undefined

    let pending = false
    const parEls = () => Array.from(document.querySelectorAll('[data-parallax]'))

    const onScroll = () => {
      if (pending) return
      pending = true
      requestAnimationFrame(() => {
        pending = false
        const doc = document.documentElement
        const y = window.scrollY || doc.scrollTop
        const max = (doc.scrollHeight - doc.clientHeight) || 1
        setScrollY(y)

        if (progressRef.current) {
          progressRef.current.style.width = `${Math.min(100, (y / max) * 100)}%`
        }
        if (navRef.current) {
          const on = y > 24
          navRef.current.style.background = on ? 'rgba(8,10,22,.94)' : 'rgba(8,10,22,.78)'
          navRef.current.style.boxShadow = on ? '0 10px 34px -16px rgba(0,0,0,.9)' : 'none'
        }
        if (toTopRef.current) {
          const show = y > 500
          toTopRef.current.style.opacity = show ? '1' : '0'
          toTopRef.current.style.transform = show ? 'translateY(0) scale(1)' : 'translateY(16px) scale(.9)'
          toTopRef.current.style.pointerEvents = show ? 'auto' : 'none'
        }
        const vh = window.innerHeight
        for (const el of parEls()) {
          const sp = parseFloat(el.getAttribute('data-parallax')) || 0.2
          const r = el.getBoundingClientRect()
          el.style.transform = `translate3d(0,${(-((r.top + r.height / 2) - vh / 2) * sp).toFixed(1)}px,0)`
        }
      })
    }

    window.addEventListener('scroll', onScroll, { passive: true })
    onScroll()
    return () => window.removeEventListener('scroll', onScroll)
  }, [motion])

  useEffect(() => {
    if (!motion) return undefined
    const onMove = (e) => {
      if (!spotRef.current) return
      spotRef.current.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`
    }
    window.addEventListener('mousemove', onMove, { passive: true })
    return () => window.removeEventListener('mousemove', onMove)
  }, [motion])

  const initMagnetic = useCallback((root) => {
    if (!motion || !root) return
    root.querySelectorAll('[data-magnetic]').forEach(btn => {
      if (btn._mag) return
      btn._mag = true
      btn.addEventListener('mousemove', e => {
        const r = btn.getBoundingClientRect()
        btn.style.transform = `translate(${(e.clientX - r.left - r.width / 2) * 0.2}px,${(e.clientY - r.top - r.height / 2) * 0.26}px)`
      })
      btn.addEventListener('mouseleave', () => { btn.style.transform = 'translate(0,0)' })
    })
  }, [motion])

  return { progressRef, toTopRef, navRef, spotRef, scrollY, initMagnetic }
}
