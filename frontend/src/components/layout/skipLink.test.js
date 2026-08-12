import { promises as fs } from 'fs'
import { describe, expect, it } from 'vitest'

/**
 * Source-level contract: every layout that wraps a routed page must ship a
 * skip link AND the matching #main-content landmark. Rendering these layouts
 * needs the whole router/auth/theme stack mocked, so we assert on source text —
 * the failure mode we care about (a layout silently missing the pair) is a
 * static property of the file.
 */
const LAYOUTS = ['MainLayout.jsx', 'PublicLayout.jsx', 'AdminLayout.jsx']

const read = (name) =>
  fs.readFile(new URL(`./${name}`, import.meta.url), 'utf8')

describe('skip-to-content landmarks', () => {
  it.each(LAYOUTS)('%s has a skip link pointing at #main-content', async (name) => {
    const src = await read(name)
    expect(src).toMatch(/href="#main-content"/)
    expect(src).toMatch(/Skip to main content/)
  })

  it.each(LAYOUTS)('%s has exactly one #main-content target', async (name) => {
    const src = await read(name)
    const targets = src.match(/id="main-content"/g) || []
    expect(targets).toHaveLength(1)
  })

  it.each(LAYOUTS)('%s puts the landmark on the <main> element', async (name) => {
    const src = await read(name)
    // id must appear inside the <main ...> opening tag, not on some wrapper div.
    const mainTag = src.match(/<main\b[^>]*>/g) || []
    expect(mainTag.some((t) => t.includes('id="main-content"'))).toBe(true)
  })

  it.each(LAYOUTS)('%s keeps the skip link hidden until focused', async (name) => {
    const src = await read(name)
    // An always-visible skip link is a visible regression on marketing pages.
    const link = src.match(/<a\s+[^>]*href="#main-content"[\s\S]*?>/)
    expect(link).not.toBeNull()
    expect(link[0]).toMatch(/\bsr-only\b/)
    expect(link[0]).toMatch(/focus:not-sr-only/)
  })
})
