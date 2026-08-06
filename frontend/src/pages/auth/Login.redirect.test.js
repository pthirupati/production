import { promises as fs } from 'fs'
import { describe, it, expect } from 'vitest'
import { safeNextParam } from './Login'

/**
 * Audit L2314 (docs/AUDIT_2026_08_TODO.md:2314): "deep links that survive auth —
 * bounce to login and return to the intended page."
 *
 * The router-state half already worked: ProtectedRoute/AdminRoute pass
 * `location.state.from` and finishLogin honored it. What did NOT work is the
 * second convention — three call sites redirect with `?next=` instead, and
 * Login.jsx never read the query string, so a renewal, a cert checkout and an
 * interview invitation all landed on /dashboard.
 *
 * `next` is attacker-controllable in a way `state.from` is not (anyone can mail
 * a /login?next=... link), so the open-redirect cases are asserted here too.
 */
describe('safeNextParam accepts in-app deep links (audit L2314)', () => {
  it('returns a site-root-relative path', () => {
    expect(safeNextParam('?next=%2Finterviews%2Finvite%2Fabc123')).toBe('/interviews/invite/abc123')
  })

  it('preserves the query string of the intended page', () => {
    // PaymentPage encodes pathname + search; losing the search would drop the
    // technology / renew flags and land the user on a blank checkout.
    expect(safeNextParam('?next=%2Fpayment%3Ftechnology%3Daws%26renew%3D1'))
      .toBe('/payment?technology=aws&renew=1')
  })

  it('returns null when there is no next param', () => {
    expect(safeNextParam('')).toBeNull()
    expect(safeNextParam('?foo=bar')).toBeNull()
    expect(safeNextParam(undefined)).toBeNull()
  })
})

describe('safeNextParam refuses open redirects (audit L2314 risk note)', () => {
  const hostile = [
    ['absolute http url', 'https://evil.test/phish'],
    ['protocol-relative url', '//evil.test/phish'],
    ['backslash network path', '/\\evil.test/phish'],
    ['javascript scheme', 'javascript:alert(1)'],
    ['data scheme', 'data:text/html,<script>alert(1)</script>'],
    ['bare relative path', 'dashboard'],
  ]

  for (const [name, value] of hostile) {
    it(`rejects ${name}`, () => {
      expect(safeNextParam(`?next=${encodeURIComponent(value)}`)).toBeNull()
    })
  }

  it('rejects /login so a redirect loop is impossible', () => {
    expect(safeNextParam('?next=%2Flogin')).toBeNull()
    expect(safeNextParam('?next=%2Flogin%3Fnext%3D%252Flogin')).toBeNull()
  })
})

describe('finishLogin wires both redirect conventions (audit L2314)', () => {
  const read = () => fs.readFile(new URL('./Login.jsx', import.meta.url), 'utf8')

  it('prefers router state, falls back to the validated next param', async () => {
    const src = await read()
    const fn = src.slice(src.indexOf('const finishLogin'), src.indexOf('const handleSubmit'))
    // state.from must be first: it is set by the router and cannot be forged
    // via a crafted link, so it should win any conflict.
    expect(fn).toMatch(/location\.state\?\.from\s*\|\|\s*safeNextParam\(location\.search\)/)
  })

  it('only safeNextParam reads the next param', async () => {
    const src = await read()
    // Guards the regression where someone "simplifies" the validation away and
    // navigates to the raw value. Everything after the helper is the component,
    // and it must reach `next` only through safeNextParam.
    const component = src.slice(src.indexOf('export default function Login'))
    expect(component).not.toMatch(/get\(['"]next['"]\)/)
    expect(component).toContain('safeNextParam(location.search)')
  })
})

describe('the ?next= producers still use the convention Login implements', () => {
  // If a producer switches to router state (or a third convention appears), the
  // safeNextParam path silently stops mattering. Assert the wiring end to end.
  const producers = [
    '../PaymentPage.jsx',
    '../interviews/InterviewInvite.jsx',
  ]

  for (const rel of producers) {
    it(`${rel} redirects to /login?next=`, async () => {
      const src = await fs.readFile(new URL(rel, import.meta.url), 'utf8')
      expect(src).toMatch(/\/login\?next=/)
    })
  }
})
