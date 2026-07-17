// @vitest-environment jsdom
/**
 * REPRODUCTION + fix guard for the "Something went wrong loading this simulator"
 * that no store reset can fix: a ChunkLoadError from the lazy sim import.
 *
 * BEFORE the fix, the boundary's "Try again" re-rendered the SAME failed lazy
 * component (which re-throws the cached rejection) and "Reset saved state" only
 * cleared localStorage — neither can conjure a missing JS chunk, so the learner
 * was stuck on the error screen until they manually did a full reload.
 *
 * AFTER the fix, a ChunkLoadError makes the boundary do a one-shot hard reload
 * (loop-guarded) so the browser revalidates index.html and fetches the current
 * chunk — and it does NOT falsely reload for an ordinary render error.
 */
import { Suspense } from 'react'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react'
import SimErrorBoundary from './SimErrorBoundary'
import { lazyWithRetry } from '../utils/lazyWithRetry'

let reloadSpy
const realLocation = window.location

beforeEach(() => {
  sessionStorage.clear()
  reloadSpy = vi.fn()
  // jsdom's window.location.reload is a non-configurable noop; replace location.
  Object.defineProperty(window, 'location', {
    value: { ...realLocation, reload: reloadSpy },
    configurable: true,
    writable: true,
  })
})

afterEach(() => {
  cleanup()
  Object.defineProperty(window, 'location', { value: realLocation, configurable: true, writable: true })
})

function LazyThatChunkFails() {
  const Lazy = lazyWithRetry(
    () => Promise.reject(new Error('Failed to fetch dynamically imported module: /assets/AwsLabOverlay-abc123.js')),
    { retries: 0 },
  )
  return (
    <Suspense fallback={<div>loading</div>}>
      <Lazy />
    </Suspense>
  )
}

function ThrowsPlainRenderError() {
  throw new TypeError("Cannot read properties of undefined (reading 'map')")
}

describe('SimErrorBoundary chunk-load recovery', () => {
  it('ChunkLoadError: boundary auto-reloads once on catch (learner is not left stuck)', async () => {
    // lazyWithRetry's OWN one-shot reload is already spent this session, so the
    // lazy import re-throws the chunk error straight into the boundary (the real
    // "stuck on the error screen" state the learner used to see).
    sessionStorage.setItem('fixitlab-chunk-reload', '1')
    render(
      <SimErrorBoundary name="aws" title="Lab environment error">
        <LazyThatChunkFails />
      </SimErrorBoundary>,
    )
    // The boundary catches the chunk error and hard-reloads automatically.
    await waitFor(() => expect(reloadSpy).toHaveBeenCalledTimes(1), { timeout: 3000 })
  })

  it('ChunkLoadError: reload is loop-guarded (only one reload per session window)', async () => {
    sessionStorage.setItem('fixitlab-chunk-reload', '1') // lazyWithRetry reload spent
    // Simulate that the BOUNDARY reload already happened moments ago this session.
    sessionStorage.setItem('fixitlab-sim-chunk-reload', String(Date.now()))
    render(
      <SimErrorBoundary name="aws" title="Lab environment error">
        <LazyThatChunkFails />
      </SimErrorBoundary>,
    )
    // The error screen shows and NO further reload fires (guard prevents a loop).
    await waitFor(() => expect(screen.queryByText(/Something went wrong/i)).not.toBeNull(), { timeout: 3000 })
    // Clicking "Try again" also stays guarded.
    fireEvent.click(screen.getByText(/Try again/i))
    expect(reloadSpy).not.toHaveBeenCalled()
  })

  it('ordinary render error: "Try again" recovers in place and does NOT hard reload', () => {
    render(
      <SimErrorBoundary name="aws" title="Lab environment error">
        <ThrowsPlainRenderError />
      </SimErrorBoundary>,
    )
    expect(screen.queryByText(/Something went wrong/i)).not.toBeNull()
    // A plain (non-chunk) error must NOT trigger a hard reload — it recovers in
    // place via onReset / store reset, exactly as before this fix.
    fireEvent.click(screen.getByText(/Try again/i))
    expect(reloadSpy).not.toHaveBeenCalled()
  })
})
