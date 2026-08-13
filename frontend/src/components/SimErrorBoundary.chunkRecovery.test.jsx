// @vitest-environment jsdom
/**
 * REPRODUCTION + fix guard for the "Something went wrong loading this simulator"
 * that no store reset can fix: a ChunkLoadError from the lazy sim import.
 *
 * AFTER the fix, a ChunkLoadError surfaces a "Reload for update" recovery UI
 * instead of auto-reloading the whole SPA (which flashed global CSS/fonts and
 * felt like the site crashed). Ordinary render errors still recover in place.
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
  it('ChunkLoadError: shows recovery UI without auto-reloading the SPA', async () => {
    sessionStorage.setItem('fixitlab-chunk-reload', '1')
    render(
      <SimErrorBoundary name="aws" title="Lab environment error">
        <LazyThatChunkFails />
      </SimErrorBoundary>,
    )
    await waitFor(() => expect(screen.getByText(/Reload for update/i)).toBeTruthy(), { timeout: 3000 })
    expect(screen.getByText(/outdated lab console/i)).toBeTruthy()
    expect(reloadSpy).not.toHaveBeenCalled()
  })

  it('ChunkLoadError: Reload for update is loop-guarded (only one reload per session window)', async () => {
    sessionStorage.setItem('fixitlab-chunk-reload', '1') // lazyWithRetry reload spent
    sessionStorage.setItem('fixitlab-sim-chunk-reload', String(Date.now()))
    render(
      <SimErrorBoundary name="aws" title="Lab environment error">
        <LazyThatChunkFails />
      </SimErrorBoundary>,
    )
    await waitFor(() => expect(screen.getByText(/Reload for update/i)).toBeTruthy(), { timeout: 3000 })
    expect(screen.getByText(/outdated lab console/i)).toBeTruthy()
    fireEvent.click(screen.getByText(/Reload for update/i))
    expect(reloadSpy).not.toHaveBeenCalled()
  })

  it('ordinary render error: "Try again" recovers in place and does NOT hard reload', () => {
    render(
      <SimErrorBoundary name="aws" title="Lab environment error">
        <ThrowsPlainRenderError />
      </SimErrorBoundary>,
    )
    expect(screen.queryByText(/Something went wrong/i)).not.toBeNull()
    fireEvent.click(screen.getByText(/Try again/i))
    expect(reloadSpy).not.toHaveBeenCalled()
  })
})
