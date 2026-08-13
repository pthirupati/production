import { promises as fs } from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'
import { describe, expect, it, beforeAll } from 'vitest'

/**
 * Audit L2303: every route declared in AppRouter must have at least one inbound
 * navigation, or be explicitly allowlisted as deep-link-only. This is the check
 * that would have caught §H4 (/simulators advertised only to anonymous users who
 * could not reach it) and §H5 (/aws-sim/* whose only producer was never imported).
 *
 * Two failure modes the audit called out, and how they are avoided:
 *
 *  1. False PASS from grepping the raw source. A bare substring search finds
 *     '/aws-sim' inside a CSS class name, a comment, or the dead helper itself,
 *     so the dead route looks alive. Targets are therefore only collected from
 *     navigational positions — `to=`, `href=`, `path:`, `navigate(`, `window.open(`.
 *
 *  2. False FAIL from template literals. `/jira/${key}` and
 *     `/auth/callback/${provider}` are built by interpolation, so an exact-string
 *     match reports them unreachable. Matching is done on the longest leading
 *     STATIC prefix of the route ('/jira', '/auth/callback'), and a target counts
 *     if it equals that prefix or continues with /, ? or #.
 *
 * The allowlist is deliberately tiny and every entry names its external producer.
 * It is the one place a genuinely dead route could hide, so additions should be
 * treated as a code-review question, not a formality.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SRC = path.resolve(HERE, '..')

/**
 * Routes with no in-app link, on purpose. Each is entered from OUTSIDE the SPA,
 * so "0 inbound links" is the correct state rather than evidence of rot.
 */
const DEEP_LINK_ONLY = {
  '/reset-password':
    'Emailed link. Producer: backend accounts/views.py:863 builds FRONTEND_URL/reset-password?token=.',
  '/unsubscribe':
    'Emailed link. Producer: backend notifications/unsubscribe.py:29 marketing_unsubscribe_url(). '
    + 'Required for CAN-SPAM / RFC 8058 compliance — deleting it fails no frontend test.',
  '/interviews/invite/:token':
    'Emailed invitation. Producer: backend interviews/services/invitations.py:26.',
  '/auth/callback/:provider':
    'OAuth redirect target handed to the provider by utils/oauth.js:17; the provider navigates here.',
  '/support':
    'Legacy inbound URL kept as a <Navigate> alias to /contact so old links and printed '
    + 'material do not 404. Intentionally unlinked — new links should point at /contact.',
  '/simulators':
    'Retired Lab Consoles page kept for bookmarks and printed links; public + auth nav '
    + 'no longer advertise it (every card redirected to /technologies/:slug). '
    + 'Intentionally unlinked — new entry is Technologies.',
}

/** Longest leading static prefix: '/interviews/round/:id/report' -> '/interviews/round'. */
function staticPrefix(route) {
  const kept = []
  for (const seg of route.split('/').filter(Boolean)) {
    if (seg.startsWith(':') || seg === '*') break
    kept.push(seg)
  }
  return `/${kept.join('/')}`
}

/**
 * Navigational positions only. `m[1]` covers attribute/property forms
 * (to=, href=, path:, and *Href props like vmwareHref/demoHref); `m[2]` covers
 * imperative calls. Both accept ', " and backtick so template literals are read
 * up to their first `${`.
 */
const NAV_TARGET =
  /(?:\bto|\bhref|\bpath|[A-Za-z]*[Hh]ref)\s*[=:]\s*\{?\s*['`"]([^'`"]*)|(?:navigate|window\.open|redirect)\(\s*['`"]([^'`"]*)/g

async function walk(dir, acc = []) {
  for (const entry of await fs.readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === 'dist') continue
      await walk(full, acc)
    } else if (/\.jsx?$/.test(entry.name) && !/\.test\.jsx?$/.test(entry.name)) {
      acc.push(full)
    }
  }
  return acc
}

let routes = []
let targets = []

beforeAll(async () => {
  const routerPath = path.join(HERE, 'AppRouter.jsx')
  const router = await fs.readFile(routerPath, 'utf8')
  routes = [...router.matchAll(/<Route path="([^"]+)"/g)]
    .map((m) => m[1])
    .filter((p) => p !== '*')

  // AppRouter itself is excluded: a route's own declaration must not count as an
  // inbound link, or every route is trivially reachable.
  const files = (await walk(SRC)).filter((f) => f !== routerPath)
  const found = new Set()
  for (const file of files) {
    // Strip <Route path="..."> declarations first. They match the `path=` arm of
    // NAV_TARGET but DECLARE a route rather than link to one — counting them would
    // let any nested router (e.g. AwsLabOverlay's MemoryRouter) vouch for a
    // top-level route that nothing actually navigates to.
    const src = (await fs.readFile(file, 'utf8')).replace(/<Route\s+path=/g, '<Route ')
    for (const m of src.matchAll(NAV_TARGET)) {
      const value = m[1] ?? m[2]
      if (value && value.startsWith('/')) found.add(value)
    }
  }
  targets = [...found]
})

const isReachable = (route) => {
  const prefix = staticPrefix(route)
  return targets.some(
    (t) => t === prefix || t.startsWith(`${prefix}/`) || t.startsWith(`${prefix}?`) || t.startsWith(`${prefix}#`),
  )
}

describe('route reachability (audit L2303)', () => {
  it('parses a plausible route table and link corpus', () => {
    // Sanity: if either extractor silently breaks, everything below passes vacuously.
    expect(routes.length).toBeGreaterThan(50)
    expect(targets.length).toBeGreaterThan(50)
    expect(routes).toContain('/dashboard')
  })

  it('every route has an inbound link or an allowlist entry', () => {
    const orphans = routes.filter((r) => !isReachable(r) && !(r in DEEP_LINK_ONLY))
    expect(orphans).toEqual([])
  })

  it('the allowlist has no stale entries', () => {
    // An allowlisted route that gained a real link, or was deleted, should be
    // removed from the list so it stops shielding future rot.
    const stale = Object.keys(DEEP_LINK_ONLY).filter((r) => !routes.includes(r))
    expect(stale).toEqual([])
  })

  it('the link extractor actually discriminates', () => {
    // Guards failure mode 1: if NAV_TARGET ever degrades into a bare substring
    // scan, a path that appears in the source only as a CSS class and a comment
    // would start counting as an inbound link. '/aws-sim' is exactly that case —
    // styles/aws-sim.css and the removed-helper comment mention it, but nothing
    // navigates there anymore.
    expect(targets).not.toContain('/aws-sim')
    expect(isReachable('/aws-sim/*')).toBe(false)
  })

  it('resolves template-literal link targets', () => {
    // Guards failure mode 2: these are only ever built by interpolation.
    expect(isReachable('/jira/:issueKey')).toBe(true)
    expect(isReachable('/lab/:sessionId')).toBe(true)
    expect(isReachable('/vmware/:sessionId')).toBe(true)
  })
})

describe('dead routes stay deleted (audit L2303 / §H5)', () => {
  it('AppRouter declares no standalone /aws-sim route', async () => {
    const router = await fs.readFile(path.join(HERE, 'AppRouter.jsx'), 'utf8')
    expect(router).not.toMatch(/<Route path="\/aws-sim/)
  })

  it('the embedded AWS console keeps its own /aws-sim route', async () => {
    // The overlay mounts AwsConsole under a MemoryRouter, which is what
    // serviceFromPath() matches on. Deleting the standalone route must not
    // disturb this one.
    const overlay = await fs.readFile(path.join(SRC, 'components/aws/AwsLabOverlay.jsx'), 'utf8')
    expect(overlay).toMatch(/<Route path="\/aws-sim\/\*"/)
  })

  it('awsConsoleUrlForResource is gone', async () => {
    const bridge = await fs.readFile(path.join(SRC, 'utils/terraformAwsBridge.js'), 'utf8')
    expect(bridge).not.toMatch(/export function awsConsoleUrlForResource/)
  })
})
