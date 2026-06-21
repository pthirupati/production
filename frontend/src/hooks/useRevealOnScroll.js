import { useEffect } from 'react'

/**
 * Reveal-on-scroll for elements that use the CSS `.reveal` class.
 *
 * In index.css, `.reveal` is `opacity: 0` and only becomes visible once the
 * `.visible` class is added. The public marketing pages (Pricing, Blog, About)
 * tag their cards/sections with `reveal reveal-delay-*`, but nothing in the app
 * was ever adding `.visible` to those plain-DOM elements — so the content
 * loaded into the DOM yet stayed permanently invisible, making the pages look
 * empty/broken. (The Home page is unaffected because it animates via
 * framer-motion's `whileInView` instead of the CSS class.)
 *
 * This hook installs an IntersectionObserver that adds `.visible` as each
 * `.reveal` element scrolls into view. It is defensive:
 *   - if there is no IntersectionObserver (old/SSR), it reveals everything;
 *   - elements already on screen at mount are revealed on the first callback;
 *   - it re-scans when `deps` change so late-loaded content (e.g. cards built
 *     from an async API response) also gets observed.
 *
 * @param {Array<any>} [deps=[]] values that, when changed, should trigger a
 *   re-scan for newly rendered `.reveal` elements.
 */
export function useRevealOnScroll(deps = []) {
  useEffect(() => {
    const els = Array.from(document.querySelectorAll('.reveal:not(.visible)'))
    if (!els.length) return undefined

    if (typeof IntersectionObserver === 'undefined') {
      els.forEach((el) => el.classList.add('visible'))
      return undefined
    }

    const io = new IntersectionObserver(
      (entries, obs) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible')
            obs.unobserve(entry.target)
          }
        })
      },
      { rootMargin: '0px 0px -10% 0px', threshold: 0.05 },
    )

    els.forEach((el) => io.observe(el))
    return () => io.disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
}

export default useRevealOnScroll
