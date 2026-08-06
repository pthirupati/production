// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, cleanup, act } from '@testing-library/react'
import { useRazorpaySdk } from './PaymentPage'

/**
 * Audit L1309 (docs/AUDIT_2026_08_TODO.md:1309): the Razorpay SDK effect
 * attached `load`/`error` listeners to an already-present <script> and returned
 * a bare `return`, so the listeners outlived the component and fired setState
 * on an unmounted tree. The same hazard existed on the freshly-created-script
 * path via `script.onload` / `script.onerror`.
 */
function Harness({ onReady, onFailed }) {
  useRazorpaySdk(onReady, onFailed)
  return null
}

function renderHarness() {
  const onReady = vi.fn()
  const onFailed = vi.fn()
  const view = render(<Harness onReady={onReady} onFailed={onFailed} />)
  return { onReady, onFailed, view }
}

afterEach(() => {
  cleanup()
  document.getElementById('razorpay-sdk')?.remove()
  delete window.Razorpay
  vi.restoreAllMocks()
})

describe('useRazorpaySdk', () => {
  it('does not report readiness after unmount when the SDK script finally loads', () => {
    const { onReady, view } = renderHarness()
    const script = document.getElementById('razorpay-sdk')
    expect(script).toBeTruthy()

    view.unmount()
    // The download was already in flight when the user navigated away.
    act(() => { script.dispatchEvent(new Event('load')) })

    expect(onReady).not.toHaveBeenCalled()
  })

  it('does not report failure after unmount when the SDK script errors', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const { onFailed, view } = renderHarness()
    const script = document.getElementById('razorpay-sdk')

    view.unmount()
    act(() => { script.dispatchEvent(new Event('error')) })

    expect(onFailed).not.toHaveBeenCalled()
  })

  it('does not report readiness after unmount when reusing an existing script tag', () => {
    // Simulates a second visit to /payment: the tag is already in the document,
    // so the hook takes the `existing` branch the audit called out.
    const existing = document.createElement('script')
    existing.id = 'razorpay-sdk'
    document.body.appendChild(existing)

    const { onReady, view } = renderHarness()
    view.unmount()
    act(() => { existing.dispatchEvent(new Event('load')) })

    expect(onReady).not.toHaveBeenCalled()
  })

  it('detaches its listeners from a reused script tag on unmount', () => {
    const existing = document.createElement('script')
    existing.id = 'razorpay-sdk'
    const removeSpy = vi.spyOn(existing, 'removeEventListener')
    document.body.appendChild(existing)

    const { view } = renderHarness()
    view.unmount()

    // Identity matters: re-creating an inline arrow in the cleanup would detach
    // nothing. Assert both events were actually unsubscribed.
    const events = removeSpy.mock.calls.map(([event]) => event)
    expect(events).toContain('load')
    expect(events).toContain('error')
  })

  it('still reports readiness while mounted', () => {
    const { onReady } = renderHarness()
    const script = document.getElementById('razorpay-sdk')

    act(() => { script.dispatchEvent(new Event('load')) })

    // Guards the risk noted in the audit: an over-eager cleanup that resets
    // state would leave checkout permanently disabled.
    expect(onReady).toHaveBeenCalledWith(true)
  })

  it('reports readiness immediately when the SDK is already on window', () => {
    window.Razorpay = function Razorpay() {}
    const { onReady } = renderHarness()

    expect(onReady).toHaveBeenCalledWith(true)
    // No duplicate tag should be injected in this case.
    expect(document.getElementById('razorpay-sdk')).toBeNull()
  })
})
