#!/usr/bin/env node
/**
 * Copy the self-hosted Pyodide and MediaPipe assets out of node_modules and into
 * public/, where Vite picks them up and emits them into dist/.
 *
 * WHY THIS EXISTS
 * ---------------
 * Both runtimes used to be loaded from cdn.jsdelivr.net. That never worked in
 * production: gateway/nginx.prod.conf ships
 *   script-src 'self' 'unsafe-inline' 'unsafe-eval' https://checkout.razorpay.com
 * and jsdelivr is on neither script-src nor connect-src, so the browser refused
 * the tag before any request went out. The Python "Run" button only ever showed
 * the "runtime could not be loaded" banner, and every user silently got the
 * no-model virtual-background path.
 *
 * Widening the CSP to allow a public CDN would be a supply-chain regression, so
 * the assets are served same-origin instead.
 *
 * WHY node_modules AND NOT COMMITTED BINARIES
 * ------------------------------------------
 * These two packages are ~25MB unpacked. Committing them would bloat every
 * clone forever and make the pinned versions invisible to dependency tooling.
 * Sourcing them from npm instead means:
 *   - the versions are pinned in package.json AND integrity-checked by
 *     package-lock.json, so the bytes are verified on every install;
 *   - `npm audit` / dependency scanning can see them;
 *   - the Docker build gets them from the `npm ci` it already runs — no extra
 *     network fetch, no curl-into-the-image step.
 * public/pyodide and public/vendor are therefore gitignored build outputs.
 *
 * Runs automatically via the `prebuild` npm lifecycle hook (and `predev`).
 */
import { existsSync, mkdirSync, copyFileSync, readFileSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const modules = join(root, 'node_modules')

/**
 * The version pin is load-bearing: it exists so a CDN-side (now registry-side)
 * major bump cannot silently change how learners' Python behaves. Assert it here
 * rather than trusting package.json, so a stray `npm install pyodide@latest`
 * fails the build instead of quietly shipping a different runtime.
 */
const PYODIDE_VERSION = '0.26.2'

/**
 * Explicit allowlist rather than a directory copy — the package also ships
 * source maps, .d.ts files and a demo console.html that would add megabytes to
 * dist/ for no runtime benefit. These five are what loadPyodide() actually
 * fetches: the loader, the compiled runtime, its WASM, the stdlib archive, and
 * the package index it resolves imports through.
 */
const PYODIDE_FILES = [
  'pyodide.js',
  'pyodide.asm.js',
  'pyodide.asm.wasm',
  'python_stdlib.zip',
  'pyodide-lock.json',
]

/**
 * MediaPipe resolves every one of these through `locateFile`, so they must all
 * sit next to selfie_segmentation.js.
 *
 * Both WASM variants are required: the loader feature-detects SIMD at runtime
 * and picks one, so dropping either breaks a whole class of browsers. The
 * landscape .tflite is the model our setOptions({modelSelection: 1}) selects.
 * The zero-byte .data file is shipped as-is by upstream and is still requested —
 * omitting it produces a 404 mid-initialisation.
 */
const MEDIAPIPE_FILES = [
  'selfie_segmentation.js',
  'selfie_segmentation.binarypb',
  'selfie_segmentation.tflite',
  'selfie_segmentation_landscape.tflite',
  'selfie_segmentation_solution_simd_wasm_bin.js',
  'selfie_segmentation_solution_simd_wasm_bin.wasm',
  'selfie_segmentation_solution_simd_wasm_bin.data',
  'selfie_segmentation_solution_wasm_bin.js',
  'selfie_segmentation_solution_wasm_bin.wasm',
]

function readVersion(pkg) {
  const manifest = join(modules, pkg, 'package.json')
  if (!existsSync(manifest)) return null
  return JSON.parse(readFileSync(manifest, 'utf8')).version
}

function fail(message) {
  console.error(`\n[vendor-assets] ${message}\n`)
  process.exit(1)
}

/** Copy only when missing or stale, so warm rebuilds don't rewrite ~25MB. */
function sync(fromDir, toDir, files, label) {
  mkdirSync(toDir, { recursive: true })
  let copied = 0
  for (const file of files) {
    const src = join(fromDir, file)
    if (!existsSync(src)) {
      fail(`${label}: expected file missing from node_modules: ${file}\nRun \`npm install\` and try again.`)
    }
    const dest = join(toDir, file)
    // Compare size and mtime rather than hashing — these are large immutable
    // release artifacts, so a cheap stat is enough to detect a version change.
    if (existsSync(dest)) {
      const a = statSync(src)
      const b = statSync(dest)
      if (a.size === b.size && b.mtimeMs >= a.mtimeMs) continue
    }
    copyFileSync(src, dest)
    copied += 1
  }
  console.log(
    `[vendor-assets] ${label}: ${copied === 0 ? 'up to date' : `copied ${copied}/${files.length} file(s)`} -> ${toDir.replace(root, '.')}`,
  )
}

const pyodideVersion = readVersion('pyodide')
if (!pyodideVersion) {
  fail('pyodide is not installed. Run `npm install`.')
}
if (pyodideVersion !== PYODIDE_VERSION) {
  fail(
    `pyodide must stay pinned at ${PYODIDE_VERSION}, found ${pyodideVersion}.\n` +
      'The pin exists so a runtime bump cannot silently change how submitted Python behaves.\n' +
      `Either reinstall ${PYODIDE_VERSION} or update PYODIDE_VERSION here AND in src/utils/ide/pyodideRunner.js after re-testing.`,
  )
}

if (!readVersion('@mediapipe/selfie_segmentation')) {
  fail('@mediapipe/selfie_segmentation is not installed. Run `npm install`.')
}

sync(
  join(modules, 'pyodide'),
  join(root, 'public', 'pyodide'),
  PYODIDE_FILES,
  `pyodide@${pyodideVersion}`,
)
sync(
  join(modules, '@mediapipe', 'selfie_segmentation'),
  join(root, 'public', 'vendor', 'selfie_segmentation'),
  MEDIAPIPE_FILES,
  'selfie_segmentation',
)
