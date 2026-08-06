// @vitest-environment jsdom
//
// This page is where an employer following a shared link lands, so a withdrawn
// certificate has to *say* it was withdrawn. Every `valid: false` used to render
// under one heading — "Certificate Not Found" — which reads as a typo or a bug
// and hides the fact that we deliberately revoked the credential. The verify
// endpoint now distinguishes revoked / expired / genuinely-unknown; these pin
// that the page keeps that distinction instead of flattening it back.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import CertificateVerify from './CertificateVerify'

// Page chrome only — PublicLayout pulls in the support-bot widget and friends,
// which need browser globals this test has no stake in. The subject here is the
// invalid-result panel.
vi.mock('../components/layout/PublicLayout', () => ({
  default: ({ children }) => <div>{children}</div>,
}))
vi.mock('../components/MarketingPageShell', () => ({
  default: ({ children }) => <div>{children}</div>,
}))

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const renderWithResponse = async (payload) => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve({ json: () => Promise.resolve(payload) })),
  )
  render(
    <MemoryRouter initialEntries={['/verify-certificate?certificate_id=FIXIT-SHR-QRS456']}>
      <CertificateVerify />
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByRole('heading', { level: 2 })).toBeTruthy())
  return screen.getByRole('heading', { level: 2 }).textContent
}

describe('CertificateVerify invalid states', () => {
  it('names revocation rather than claiming the certificate is missing', async () => {
    const heading = await renderWithResponse({
      valid: false,
      revoked: true,
      certificate_id: 'FIXIT-SHR-QRS456',
      error: 'Certificate has been revoked: grader defect; re-take the exam',
    })
    expect(heading).toBe('Certificate Revoked')
    expect(screen.getByText(/grader defect/)).toBeTruthy()
  })

  it('names expiry separately from revocation', async () => {
    const heading = await renderWithResponse({
      valid: false,
      is_expired: true,
      error: 'Certificate is out of date. Please renew your certification.',
    })
    expect(heading).toBe('Certificate Expired')
  })

  it('still says not-found for an id that matches nothing', async () => {
    const heading = await renderWithResponse({
      valid: false,
      error: 'Certificate not found. Check the ID and try again.',
    })
    expect(heading).toBe('Certificate Not Found')
  })

  it('does not render the verified-certificate card for a revoked cert', async () => {
    await renderWithResponse({
      valid: false,
      revoked: true,
      holder_name: 'Share Holder',
      total_score: 88,
      error: 'Certificate has been revoked',
    })
    expect(screen.queryByText(/Verified Certificate/)).toBeNull()
    expect(screen.queryByText(/Share Holder/)).toBeNull()
  })
})
