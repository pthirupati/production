import { promises as fs } from 'fs'
import path from 'path'
import { describe, expect, it } from 'vitest'

/**
 * Guards the fix for audit L1287: the 1.19MB AWS console chunk was being
 * modulepreloaded on first paint (332.85kB gzip) even though NOTHING statically
 * imports components/aws/ anymore — awsSimLifecycle.js made that edge dynamic.
 *
 * The preload was a manualChunks artifact, and that is the subtle part worth
 * pinning. Three modules are reachable from the entry AND imported by
 * components/aws/**: store/authStore, api/scenarios, utils/userScopedStorage.
 * With no explicit chunk of their own, Rollup filed them under `aws-console`
 * (the first rule that claimed them), which made the ENTRY chunk import
 * aws-console, which made Vite preload the whole thing.
 *
 * So this asserts the invariant that actually broke, not the symptom: every
 * module reachable from main.jsx by static imports must be assigned to some
 * chunk other than `aws-console`. Deleting the app-shared rule in
 * vite.config.js makes this fail on all three modules.
 *
 * Static-import-only traversal is deliberate: a dynamic import() is a chunk
 * boundary, so it is exactly what keeps a module off the eager path.
 */
const SRC = new URL('./', import.meta.url).pathname
const CONFIG = path.join(SRC, '..', 'vite.config.js')

const CANDIDATE_SUFFIXES = ['', '.js', '.jsx', '/index.js', '/index.jsx']

async function resolveImport(fromFile, spec) {
  // Only relative specifiers can reach src/; bare ones are node_modules.
  if (!spec.startsWith('.')) return null
  const base = path.resolve(path.dirname(fromFile), spec)
  for (const suffix of CANDIDATE_SUFFIXES) {
    const candidate = base + suffix
    try {
      if ((await fs.stat(candidate)).isFile()) return candidate
    } catch {
      /* not this extension */
    }
  }
  return null
}

// Matches static `import ... from 'x'` and bare `import 'x'` at line start.
// A dynamic import() is NOT matched, which is the whole point.
const STATIC_IMPORT_RE = /^\s*import\s+(?:[^'";]*?\s+from\s+)?['"]([^'"]+)['"]/gm

async function staticImportsOf(file) {
  const source = await fs.readFile(file, 'utf8')
  const out = []
  for (const match of source.matchAll(STATIC_IMPORT_RE)) {
    const resolved = await resolveImport(file, match[1])
    if (resolved) out.push(resolved)
  }
  return out
}

/** Every module reachable from main.jsx without crossing a dynamic import. */
async function eagerModules() {
  const entry = path.join(SRC, 'main.jsx')
  const seen = new Set([entry])
  const queue = [entry]
  while (queue.length) {
    for (const next of await staticImportsOf(queue.shift())) {
      if (!seen.has(next)) {
        seen.add(next)
        queue.push(next)
      }
    }
  }
  return seen
}

describe('eager bundle does not drag in the AWS console chunk', () => {
  it('has no static import path from the entry into components/aws/', async () => {
    const eager = [...(await eagerModules())].filter((f) => f.includes('/components/aws/'))
    expect(eager).toEqual([])
  })

  it('assigns every aws-console-adjacent eager module to its own chunk', async () => {
    const config = await fs.readFile(CONFIG, 'utf8')
    // The rule must be positioned ahead of the aws-console rule; if it lands
    // after, Rollup has already claimed these modules and the preload returns.
    const appShared = config.indexOf('"app-shared"')
    const awsConsole = config.indexOf('"aws-console"')
    expect(appShared).toBeGreaterThan(-1)
    expect(appShared).toBeLessThan(awsConsole)

    // Anything both eager AND imported by components/aws/ needs a home. These
    // are the three that exist today; the assertion is computed, so a new one
    // appearing fails here rather than silently re-inflating first paint.
    const eager = await eagerModules()
    const awsDir = path.join(SRC, 'components', 'aws')
    const awsFiles = []
    const walk = async (dir) => {
      for (const entry of await fs.readdir(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name)
        if (entry.isDirectory()) await walk(full)
        else if (/\.(js|jsx)$/.test(entry.name) && !/\.test\./.test(entry.name)) awsFiles.push(full)
      }
    }
    await walk(awsDir)

    const contested = new Set()
    for (const file of awsFiles) {
      for (const dep of await staticImportsOf(file)) {
        if (eager.has(dep) && !dep.includes('/components/aws/')) contested.add(dep)
      }
    }

    // Each contested module must match a rule that fires before aws-console.
    const beforeAws = config.slice(0, awsConsole)
    for (const file of contested) {
      const rel = file.slice(SRC.length).replace(/\.(js|jsx)$/, '')
      const claimed = beforeAws.includes(`/src/${rel}`)
      expect(claimed, `${rel} is eager and pulled into aws-console — give it a chunk before the aws-console rule`).toBe(true)
    }
  })
})
