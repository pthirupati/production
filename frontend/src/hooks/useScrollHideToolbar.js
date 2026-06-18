import { useEffect, useRef, useState } from 'react'

/**
 * Collapse page toolbar once user scrolls past it (no leftover gap).
 */
export function useScrollHideToolbar(threshold = 64) {
  const [hidden, setHidden] = useState(false)
  const toolbarRef = useRef(null)
  const anchorRef = useRef(null)

  useEffect(() => {
    const findScrollParent = (el) => {
      let node = el?.parentElement
      while (node && node !== document.body) {
        const { overflowY } = getComputedStyle(node)
        if (/(auto|scroll|overlay)/.test(overflowY) && node.scrollHeight > node.clientHeight) {
          return node
        }
        node = node.parentElement
      }
      return null
    }

    const toolbar = toolbarRef.current
    const anchor = anchorRef.current
    if (!toolbar || !anchor) return

    const root = findScrollParent(toolbar)
    const observer = new IntersectionObserver(
      ([entry]) => {
        const scrolledPast = !entry.isIntersecting && entry.boundingClientRect.top < threshold
        setHidden(scrolledPast)
      },
      {
        root,
        threshold: [0, 1],
        rootMargin: `-${threshold}px 0px 0px 0px`,
      },
    )
    observer.observe(anchor)
    return () => observer.disconnect()
  }, [threshold])

  return { hidden, toolbarRef, anchorRef }
}
