import { promises as fs } from 'fs'
import path from 'path'
import { describe, expect, it } from 'vitest'

/**
 * Regression guard for W12 "dead code": seven modules had accumulated with zero
 * external importers (an unshipped transcript feature, two demo widgets that the
 * home page stopped rendering, and a provisioning hook superseded by
 * useLabSession). They were deleted; this test fails if they come back, and more
 * usefully it fails if *any* new module under src/ ends up orphaned the same way.
 *
 * Entry points are excluded because nothing imports them by design — the HTML
 * and the router pull them in. Pages are excluded because they are referenced
 * lazily by string path in AppRouter, which a static import scan cannot see.
 */
const SRC = new URL('./', import.meta.url).pathname

const MODULE_EXT = new Set(['.js', '.jsx'])

// Nothing imports these by design.
const ENTRY_POINTS = new Set(['main.jsx', 'App.jsx'])

const IGNORED_DIRS = new Set(['node_modules', '__mocks__'])

async function walk(dir, out = []) {
  for (const entry of await fs.readdir(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.')) continue
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (IGNORED_DIRS.has(entry.name)) continue
      await walk(full, out)
    } else {
      out.push(full)
    }
  }
  return out
}

const isTest = (p) => /\.(test|spec)\.(js|jsx)$/.test(p)

describe('W12: no orphaned modules under src/', () => {
  it('the seven modules deleted in W12 stay deleted', async () => {
    const deleted = [
      'components/CompactPageHeader.jsx',
      'components/InterviewDemoWidget.jsx',
      'components/VMwareDemoWidget.jsx',
      'components/interviews/LiveTranscriptPanel.jsx',
      'components/interviews/MediaPermissionDialog.jsx',
      'components/interviews/TranscriptPlayer.jsx',
      'hooks/useLabProvisioning.js',
    ]
    const stillPresent = []
    for (const rel of deleted) {
      try {
        await fs.access(path.join(SRC, rel))
        stillPresent.push(rel)
      } catch {
        // absent, as intended
      }
    }
    expect(stillPresent).toEqual([])
  })

  it('every non-entry module under src/ is imported by something', async () => {
    const files = await walk(SRC)
    const modules = files.filter(
      (f) => MODULE_EXT.has(path.extname(f)) && !isTest(f),
    )

    // Union of every import/require/lazy specifier across the whole tree.
    const specifiers = new Set()
    const sources = files.filter((f) => MODULE_EXT.has(path.extname(f)))
    for (const file of sources) {
      const text = await fs.readFile(file, 'utf8')
      const patterns = [
        /(?:from|import)\s+['"]([^'"]+)['"]/g,
        // Dynamic import — how every simulator is code-split
        // (labSimLoader.js: `lazyWithRetry(() => import('../gcp/GcpConsole'))`)
        // and how some tests pull a module in. Missing this pattern makes the
        // whole lazily-loaded half of the app look orphaned.
        /import\(\s*['"]([^'"]+)['"]\s*\)/g,
        /require\(\s*['"]([^'"]+)['"]\s*\)/g,
      ]
      for (const re of patterns) {
        for (const m of text.matchAll(re)) {
          if (!m[1].startsWith('.')) continue // package import, not a local module
          specifiers.add(path.resolve(path.dirname(file), m[1]))
        }
      }
    }

    const orphans = modules.filter((file) => {
      const rel = path.relative(SRC, file)
      if (ENTRY_POINTS.has(rel)) return false
      // Router lazy-loads pages; treat the pages tree as externally reachable.
      if (rel.startsWith('pages/')) return false

      const noExt = file.replace(/\.(js|jsx)$/, '')
      // An importer may name the file directly, or name its directory when the
      // file is that directory's index.
      const aliases = [noExt]
      if (path.basename(noExt) === 'index') aliases.push(path.dirname(noExt))
      return !aliases.some((a) => specifiers.has(a))
    })

    expect(orphans.map((f) => path.relative(SRC, f)).sort()).toEqual([])
  })
})
