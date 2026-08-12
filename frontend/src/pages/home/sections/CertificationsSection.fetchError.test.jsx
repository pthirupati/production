// @vitest-environment jsdom
// Audit W5: a failed /certifications/ call used to render exactly the same as
// "no tracks exist" — an empty section — so a backend blip silently deleted a
// marketing surface with no signal to the visitor.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const list = vi.fn()
vi.mock('../../../api/certifications', () => ({ certApi: { list: () => list() } }))

// framer-motion's whileInView needs IntersectionObserver; render plain nodes.
// Strip the animation-only props so React doesn't warn about unknown DOM attrs.
vi.mock('framer-motion', () => ({
  motion: new Proxy({}, {
    get: () => ({ children, initial: _initial, whileInView: _whileInView, viewport: _viewport, variants: _variants, ...rest }) => (
      <div {...rest}>{children}</div>
    ),
  }),
}))

import CertificationsSection from './CertificationsSection'

const renderSection = () =>
  render(
    <MemoryRouter>
      <CertificationsSection isAuthenticated={false} />
    </MemoryRouter>,
  )

describe('CertificationsSection fetch failure', () => {
  beforeEach(() => { cleanup(); list.mockReset() })
  afterEach(() => cleanup())

  it('shows an explicit error state when the tracks call rejects', async () => {
    list.mockRejectedValue(new Error('502'))
    renderSection()
    await waitFor(() => expect(screen.getByTestId('certs-error')).toBeTruthy())
    // Still offers a way forward rather than a dead end.
    expect(screen.getByText('Browse all certifications')).toBeTruthy()
  })

  it('stays silent when the platform genuinely has no active tracks', async () => {
    list.mockResolvedValue({ tracks: [] })
    renderSection()
    await waitFor(() => expect(list).toHaveBeenCalled())
    expect(screen.queryByTestId('certs-error')).toBeNull()
    expect(screen.queryByText('Vendor-aligned certification labs')).toBeNull()
  })

  it('renders tracks normally on success', async () => {
    list.mockResolvedValue({ tracks: [{ slug: 'rhcsa', name: 'RHCSA', vendor: 'Red Hat', scenario_count: 12 }] })
    renderSection()
    await waitFor(() => expect(screen.getByText('RHCSA')).toBeTruthy())
    expect(screen.queryByTestId('certs-error')).toBeNull()
  })
})
