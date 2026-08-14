import { promises as fs } from 'fs'
import { describe, expect, it } from 'vitest'
import { PUBLIC_NAV_LINKS, PUBLIC_NAV_PRIMARY, PUBLIC_NAV_SECONDARY } from './publicNav'

/**
 * Lab Consoles (/simulators) is retired from both public and authenticated nav —
 * Technologies already covers the same destinations.
 */
const readSrc = (rel) =>
  fs.readFile(new URL(rel, import.meta.url), 'utf8')

describe('public nav does not advertise authenticated routes', () => {
  it('no public nav link points at /simulators', () => {
    const all = [...PUBLIC_NAV_PRIMARY, ...PUBLIC_NAV_SECONDARY, ...PUBLIC_NAV_LINKS]
    expect(all.filter((l) => l.to === '/simulators')).toHaveLength(0)
  })

  it('Technologies is in secondary/footer, not the primary header row', () => {
    expect(PUBLIC_NAV_PRIMARY.some((l) => l.to === '/#tech')).toBe(false)
    expect(PUBLIC_NAV_SECONDARY.some((l) => l.to === '/#tech')).toBe(true)
  })

  it('Pricing is on the primary header row', () => {
    expect(PUBLIC_NAV_PRIMARY.some((l) => l.to === '/pricing')).toBe(true)
  })

  it('AI Interviews is on the primary header row', () => {
    expect(PUBLIC_NAV_PRIMARY.some((l) => l.to === '/mock-interviews')).toBe(true)
  })

  it('Verify uses Certificate Verify label', () => {
    const verify = PUBLIC_NAV_PRIMARY.find((l) => l.to === '/verify-certificate')
    expect(verify?.label).toBe('Certificate Verify')
  })

  it('Journeys route is labeled Roadmap on the primary nav', () => {
    const journeys = PUBLIC_NAV_PRIMARY.find((l) => l.to === '/journeys')
    expect(journeys?.label).toBe('Roadmap')
  })

  it('every public nav destination is a route outside the authenticated MainLayout', async () => {
    const router = await readSrc('../router/AppRouter.jsx')
    const start = router.indexOf('<ProtectedRoute><MainLayout />')
    expect(start).toBeGreaterThan(-1)
    const protectedBlock = router.slice(start)
    const protectedPaths = new Set(
      [...protectedBlock.matchAll(/<Route path="([^"]+)"/g)].map((m) => m[1]),
    )
    expect(protectedPaths.has('/dashboard')).toBe(true)

    const offenders = PUBLIC_NAV_LINKS
      .map((l) => l.to)
      .filter((to) => protectedPaths.has(to))
    expect(offenders).toEqual([])
  })
})

describe('authenticated sidebar does not duplicate Lab Consoles / Journeys', () => {
  it('MainLayout navItems has no /simulators or /journeys entry', async () => {
    const src = await readSrc('../components/layout/MainLayout.jsx')
    const navBlock = src.slice(src.indexOf('const navItems = ['))
    const items = navBlock.slice(0, navBlock.indexOf(']'))
    expect(items).not.toMatch(/path: '\/simulators'/)
    expect(items).not.toMatch(/path: '\/journeys'/)
    expect(items).toMatch(/path: '\/technologies'/)
  })
})
