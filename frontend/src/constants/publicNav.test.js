import { promises as fs } from 'fs'
import { describe, expect, it } from 'vitest'
import { PUBLIC_NAV_LINKS, PUBLIC_NAV_PRIMARY, PUBLIC_NAV_SECONDARY } from './publicNav'

/**
 * Regression guard for "/simulators is reachable by nobody": the route sits
 * inside the authenticated MainLayout, but its only inbound link was in the
 * public nav, so anonymous visitors bounced to /login and authenticated users
 * had no link at all. Both halves are asserted here.
 */
const readSrc = (rel) =>
  fs.readFile(new URL(rel, import.meta.url), 'utf8')

describe('public nav does not advertise authenticated routes', () => {
  it('no public nav link points at /simulators', () => {
    const all = [...PUBLIC_NAV_PRIMARY, ...PUBLIC_NAV_SECONDARY, ...PUBLIC_NAV_LINKS]
    expect(all.filter((l) => l.to === '/simulators')).toHaveLength(0)
  })

  it('every public nav destination is a route outside the authenticated MainLayout', async () => {
    const router = await readSrc('../router/AppRouter.jsx')
    // The protected block starts at `<Route element={<ProtectedRoute><MainLayout />`
    // and runs to the end of that element. Grab the paths declared inside it.
    const start = router.indexOf('<ProtectedRoute><MainLayout />')
    expect(start).toBeGreaterThan(-1)
    const protectedBlock = router.slice(start)
    const protectedPaths = new Set(
      [...protectedBlock.matchAll(/<Route path="([^"]+)"/g)].map((m) => m[1]),
    )
    expect(protectedPaths.has('/dashboard')).toBe(true) // sanity: block was found

    const offenders = PUBLIC_NAV_LINKS
      .map((l) => l.to)
      .filter((to) => protectedPaths.has(to))
    expect(offenders).toEqual([])
  })
})

describe('authenticated sidebar exposes /simulators', () => {
  it('MainLayout navItems contains a /simulators entry', async () => {
    const src = await readSrc('../components/layout/MainLayout.jsx')
    const navBlock = src.slice(src.indexOf('const navItems = ['))
    const items = navBlock.slice(0, navBlock.indexOf(']'))
    expect(items).toMatch(/path: '\/simulators'/)
  })
})
