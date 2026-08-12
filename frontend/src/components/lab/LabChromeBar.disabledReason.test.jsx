// @vitest-environment jsdom
//
// Audit L2306. Disabled Check / +30m buttons gave no reason — the learner saw a
// greyed button and no way to find out why. A `disabled` button swallows its own
// pointer events, so the explanation has to live on a hovering wrapper; these
// tests pin that placement, not just the string.
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { LabChromeControls } from './LabChromeBar'

const noop = () => {}

afterEach(cleanup)

/** The element a browser actually hovers to surface the tooltip. */
function tooltipTitleFor(name) {
  const btn = screen.getByRole('button', { name })
  return btn.closest('[title]')?.getAttribute('title') ?? null
}

describe('LabChromeControls disabled explanations', () => {
  it('explains a disabled Check on the hoverable wrapper, not the dead button', () => {
    render(
      <LabChromeControls
        onCheck={noop}
        checkDisabled
        checkDisabledReason="Already solved — this lab is complete."
        showTimer={false}
      />,
    )
    const btn = screen.getByRole('button', { name: /Check/ })
    expect(btn.disabled).toBe(true)
    // A title on the disabled button itself never renders a tooltip, so the
    // reason has to sit on an enclosing element.
    expect(btn.getAttribute('title')).toBeNull()
    expect(tooltipTitleFor(/Check/)).toBe('Already solved — this lab is complete.')
    // ...and reachable to a screen reader, which never sees `title` reliably.
    expect(btn.getAttribute('aria-label')).toMatch(/Already solved/)
  })

  it('explains a disabled +30m', () => {
    render(
      <LabChromeControls
        onExtend={noop}
        extendDisabled
        extendDisabledReason="No extensions left today (limit 2 per day)."
        showTimer={false}
      />,
    )
    expect(screen.getByRole('button', { name: /30 minutes/ }).disabled).toBe(true)
    expect(tooltipTitleFor(/30 minutes/)).toBe('No extensions left today (limit 2 per day).')
  })

  it('falls back to a true generic reason for simulators passing bare booleans', () => {
    // ~14 consoles pass checkDisabled/extendDisabled with no reason string. They
    // must not render an empty tooltip.
    render(<LabChromeControls onCheck={noop} onExtend={noop} checkDisabled extendDisabled showTimer={false} />)
    expect(tooltipTitleFor(/Check/)).toMatch(/already running|already solved/i)
    expect(tooltipTitleFor(/30 minutes/)).toMatch(/in flight|extensions/i)
  })

  it('describes the action, not a disabled reason, when enabled', () => {
    render(<LabChromeControls onCheck={noop} onExtend={noop} showTimer={false} />)
    const check = screen.getByRole('button', { name: 'Check' })
    expect(check.disabled).toBe(false)
    expect(tooltipTitleFor('Check')).toBe("Grade your work against this lab's checks")
    expect(tooltipTitleFor(/30 minutes/)).toBe('Add 30 minutes to this lab')
  })

  it('keeps the buttons disabled rather than enabled-with-a-toast', () => {
    // Relaxing `disabled` would let a learner spam the rate-limited grader.
    render(<LabChromeControls onCheck={noop} checkDisabled showTimer={false} />)
    expect(screen.getByRole('button', { name: /Check/ }).disabled).toBe(true)
  })
})
