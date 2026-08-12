// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import SimulatorLauncher from './SimulatorLauncher'

/**
 * Audit H4 (docs/AUDIT_2026_08_TODO.md:466): every card here deep-links to
 * /technologies/:slug, which is a scenario picker — not a console. The page is a
 * signpost, so its copy must set that expectation instead of promising a console
 * the user can open from this grid.
 */
function renderPage() {
  return render(
    <MemoryRouter>
      <SimulatorLauncher />
    </MemoryRouter>,
  )
}

describe('SimulatorLauncher', () => {
  afterEach(() => cleanup())

  it('routes every card to a technology page rather than a lab session', () => {
    renderPage()
    const links = screen.getAllByRole('link')
    expect(links.length).toBeGreaterThan(0)
    for (const link of links) {
      expect(link.getAttribute('href')).toMatch(/^\/technologies\//)
    }
  })

  it('tells the user each card leads to that technology\'s scenarios', () => {
    renderPage()
    const links = screen.getAllByRole('link')
    // Every card must carry its own destination affordance, so the card is not
    // mistaken for a launch button.
    for (const link of links) {
      expect(link.textContent).toMatch(/Browse .* scenarios/)
    }
  })

  it('does not promise a console that opens from this page', () => {
    renderPage()
    // The old subtitle said "launch a lab from each technology", implying this
    // grid launches something. Nothing on this page starts a session.
    const body = document.body.textContent
    expect(body).not.toMatch(/launch a lab from each technology/i)
    expect(body).toMatch(/no consoles on this page/i)
  })

  it('explains where consoles actually open', () => {
    renderPage()
    expect(document.body.textContent).toMatch(/opens only inside a lab session/i)
  })
})
