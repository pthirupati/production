import { ArrowUp } from 'lucide-react'

/** Scroll progress, cursor spotlight, back-to-top — shared across marketing pages. */
export default function FxPageChrome({ progressRef, toTopRef, spotRef, showSpotlight = true }) {
  return (
    <>
      <div aria-hidden="true" className="fx-scroll-progress">
        <div ref={progressRef} className="fx-scroll-progress-bar" />
      </div>

      {showSpotlight && (
        <div
          ref={spotRef}
          aria-hidden="true"
          className="fx-cursor-spotlight"
        />
      )}

      <a
        href="#top"
        ref={toTopRef}
        aria-label="Back to top"
        className="fx-back-to-top"
      >
        <ArrowUp size={20} strokeWidth={2.4} />
      </a>
    </>
  )
}
