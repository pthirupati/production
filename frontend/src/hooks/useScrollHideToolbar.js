import { useEffect, useRef, useState } from 'react'

/** Hide a sticky toolbar after scrolling down; reveal on scroll up. */
export function useScrollHideToolbar(threshold = 80) {
  const [hidden, setHidden] = useState(false)
  const lastY = useRef(0)
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
      return window
    }

    const scrollTarget = findScrollParent(anchorRef.current)
    const getY = () => (scrollTarget === window ? window.scrollY : scrollTarget.scrollTop)

    const onScroll = () => {
      const y = getY()
      if (y < threshold) {
        setHidden(false)
      } else if (y > lastY.current + 8) {
        setHidden(true)
      } else if (y < lastY.current - 8) {
        setHidden(false)
      }
      lastY.current = y
    }

    scrollTarget.addEventListener('scroll', onScroll, { passive: true })
    return () => scrollTarget.removeEventListener('scroll', onScroll)
  }, [threshold])

  return { hidden, anchorRef }
}
