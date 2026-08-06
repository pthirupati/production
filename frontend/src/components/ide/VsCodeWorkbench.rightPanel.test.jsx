// @vitest-environment jsdom
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import VsCodeWorkbench from './VsCodeWorkbench'

const INSTRUCTIONS = 'Build a responsive card layout'

function renderWorkbench() {
  return render(
    <VsCodeWorkbench
      editor={<div>editor</div>}
      rightPanelLabel="Instructions"
      rightPanel={{
        header: <button type="button">Instructions</button>,
        content: <p>{INSTRUCTIONS}</p>,
      }}
    />,
  )
}

describe('VsCodeWorkbench right panel below the lg breakpoint', () => {
  beforeEach(cleanup)

  it('keeps the docked panel for large screens', () => {
    const { container } = renderWorkbench()
    const docked = container.querySelector('.vsc-right-panel:not(.vsc-right-panel-drawer)')
    expect(docked).toBeTruthy()
    // Still hidden below lg — the drawer covers that case instead.
    expect(docked.className).toContain('hidden')
    expect(docked.className).toContain('lg:flex')
  })

  it('offers a small-screen toggle so the panel is reachable at all', () => {
    // Regression: the right panel was plain `hidden lg:flex`, so on a phone or
    // tablet the lab INSTRUCTIONS and Preview had no affordance whatsoever.
    const { container } = renderWorkbench()
    const toggle = container.querySelector('.vsc-right-drawer-toggle')
    expect(toggle).toBeTruthy()
    expect(toggle.className).toContain('lg:hidden')
  })

  it('opens a drawer that actually renders the panel content', () => {
    const { container } = renderWorkbench()
    expect(container.querySelector('.vsc-right-panel-drawer')).toBeNull()

    fireEvent.click(container.querySelector('.vsc-right-drawer-toggle'))

    const drawer = container.querySelector('.vsc-right-panel-drawer')
    expect(drawer).toBeTruthy()
    expect(drawer.textContent).toContain(INSTRUCTIONS)
    expect(drawer.className).toContain('lg:hidden')
  })

  it('closes via the scrim', () => {
    const { container } = renderWorkbench()
    fireEvent.click(container.querySelector('.vsc-right-drawer-toggle'))
    expect(container.querySelector('.vsc-right-panel-drawer')).toBeTruthy()

    fireEvent.click(container.querySelector('.vsc-right-scrim'))
    expect(container.querySelector('.vsc-right-panel-drawer')).toBeNull()
  })

  it('closes via the drawer close button', () => {
    const { container } = renderWorkbench()
    fireEvent.click(container.querySelector('.vsc-right-drawer-toggle'))
    fireEvent.click(screen.getAllByLabelText('Close panel').at(-1))
    expect(container.querySelector('.vsc-right-panel-drawer')).toBeNull()
  })

  it('renders no toggle when there is no right panel', () => {
    const { container } = render(<VsCodeWorkbench editor={<div>editor</div>} />)
    expect(container.querySelector('.vsc-right-drawer-toggle')).toBeNull()
  })
})
