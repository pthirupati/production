import { useEffect, useId, useRef, useState } from 'react'

/** Render Mermaid diagrams client-side (offline after bundle load). */
export default function TutorialMermaid({ chart }) {
  const id = useId().replace(/:/g, '')
  const hostRef = useRef(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      if (!chart?.trim() || !hostRef.current) return
      try {
        const mermaid = (await import('mermaid')).default
        mermaid.initialize({
          startOnLoad: false,
          theme: 'dark',
          securityLevel: 'strict',
          fontFamily: 'ui-sans-serif, system-ui, sans-serif',
        })
        const { svg } = await mermaid.render(`mmd-${id}`, chart.trim())
        if (!cancelled && hostRef.current) {
          hostRef.current.innerHTML = svg
          setError('')
        }
      } catch (e) {
        if (!cancelled) setError(e?.message || 'Could not render diagram')
      }
    }
    run()
    return () => { cancelled = true }
  }, [chart, id])

  if (error) {
    return (
      <figure className="tutorial-diagram tutorial-diagram-fallback">
        <pre className="tutorial-code-pre text-xs">{chart}</pre>
        <figcaption className="tutorial-code-caption">Diagram (source)</figcaption>
      </figure>
    )
  }

  return (
    <figure className="tutorial-diagram">
      <div ref={hostRef} className="tutorial-mermaid-host overflow-x-auto" role="img" aria-label="Architecture diagram" />
    </figure>
  )
}
