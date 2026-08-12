/**
 * Audit L1877 — the sticky 2D flag must EXPIRE.
 *
 * Three of the four properties the audit asked for already existed (schema
 * version, a clear-UI toggle, and no crash path writing the flag). Expiry did
 * not: the flag was written as a bare '1' with no timestamp, so a browser that
 * ever chose 2D stayed pinned until the next key version bump — which only
 * releases it once, at deploy time.
 *
 * These assert the pure helpers rather than the DOM, because the expiry
 * contract is the whole mechanism and it should fail loudly if reverted.
 */
import { describe, expect, it } from 'vitest'
import { encodePrefer2d, isPrefer2dActive } from './DatacenterSimulator'

const DAY = 24 * 60 * 60 * 1000
const NOW = 1_770_000_000_000 // fixed epoch so the suite never depends on wall clock

describe('L1877 — prefer-2d expiry', () => {
  it('honours a freshly written preference', () => {
    expect(isPrefer2dActive(encodePrefer2d(NOW), NOW)).toBe(true)
  })

  it('still honours it just inside the 30-day window', () => {
    const written = encodePrefer2d(NOW - 29 * DAY)
    expect(isPrefer2dActive(written, NOW)).toBe(true)
  })

  it('releases the browser once the window has passed', () => {
    // The actual bug: without a TTL this stayed '2d' forever.
    const written = encodePrefer2d(NOW - 31 * DAY)
    expect(isPrefer2dActive(written, NOW)).toBe(false)
  })

  it('treats the legacy bare "1" payload as expired, not permanent', () => {
    // Browsers pinned by the pre-timestamp build are exactly the population the
    // expiry exists to release, so '1' (epoch 1970) must read as stale.
    expect(isPrefer2dActive('1', NOW)).toBe(false)
  })

  it('fails open to 3D on absent, malformed or future-dated values', () => {
    // Failing open costs one click to undo; failing closed is the original trap.
    expect(isPrefer2dActive(null, NOW)).toBe(false)
    expect(isPrefer2dActive('', NOW)).toBe(false)
    expect(isPrefer2dActive('not-a-number', NOW)).toBe(false)
    expect(isPrefer2dActive('-5', NOW)).toBe(false)
    expect(isPrefer2dActive(String(NOW + 10 * DAY), NOW)).toBe(false)
  })

  it('writes a parseable timestamp, not a bare flag', () => {
    // Regression guard: reverting to setItem(KEY, '1') makes this fail.
    const encoded = encodePrefer2d(NOW)
    expect(encoded).not.toBe('1')
    expect(Number(encoded)).toBe(NOW)
  })
})
