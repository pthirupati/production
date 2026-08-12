/**
 * Client-side Python execution via Pyodide (free, MIT, WASM).
 *
 * Loads the Pyodide runtime on first use and caches it for the page lifetime.
 * All execution happens in the browser — no servers, no paid APIs. If the
 * runtime can't be reached (offline, blocked), every call rejects with a
 * friendly message so the IDE can degrade gracefully instead of crashing.
 *
 * IMPORTANT: this runner is for the user-facing Run button and VISIBLE tests
 * only. It is convenience, not a source of truth — the authoritative pass/fail
 * decision (including hidden tests) is always made on the backend.
 */

// Pin the version so a runtime bump can never silently change behaviour. This
// string is asserted against the installed package by
// frontend/scripts/vendor-assets.mjs, which fails the build on a mismatch.
const PYODIDE_VERSION = 'v0.26.2'

// Pyodide is served SAME-ORIGIN. There is deliberately no CDN fallback:
//   1. it never worked in production anyway — gateway/nginx.prod.conf ships
//      `script-src 'self' 'unsafe-inline' 'unsafe-eval' https://checkout.razorpay.com`,
//      so a cdn.jsdelivr.net <script> was refused by CSP before it ever hit the
//      network, and the Run button only ever showed the offline banner;
//   2. offline / air-gapped learners can't reach a CDN at all;
//   3. allowing a public CDN to inject script into this origin is supply-chain
//      surface we don't need now that the bytes ship with the image.
// The assets come from the pinned npm package and are copied into
// public/pyodide/ at build time. VITE_PYODIDE_URL can repoint this, but it
// should stay same-origin — anything else reintroduces both problems above.
const PYODIDE_BASE =
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_PYODIDE_URL) || '/pyodide/'

/**
 * Candidate bases, most-preferred first, deduped.
 *
 * Kept as a list (rather than collapsed to a single string) because the loader
 * below iterates it, and because the offline tests assert that every entry is
 * same-origin — that assertion is what stops a CDN being quietly reintroduced.
 */
export function pyodideSources() {
  return [PYODIDE_BASE].filter((v, i, a) => v && a.indexOf(v) === i)
}

export { PYODIDE_VERSION }

let pyodidePromise = null

function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (typeof document === 'undefined') {
      reject(new Error('Pyodide requires a browser environment'))
      return
    }
    const existing = document.querySelector(`script[data-pyodide]`)
    if (existing) {
      if (window.loadPyodide) return resolve()
      existing.addEventListener('load', () => resolve())
      existing.addEventListener('error', () => reject(new Error('Failed to load Pyodide script')))
      return
    }
    const script = document.createElement('script')
    script.src = src
    script.async = true
    script.dataset.pyodide = '1'
    script.onload = () => resolve()
    script.onerror = () => reject(new Error(`Failed to load Pyodide from ${src}`))
    // A CSP refusal fires `error` but leaves the tag in the DOM; drop it so the
    // next base isn't short-circuited by the `[data-pyodide]` lookup above.
    script.addEventListener('error', () => script.remove())
    document.head.appendChild(script)
  })
}

/** Lazily load (once) and return the Pyodide instance. */
export async function getPyodide() {
  if (pyodidePromise) return pyodidePromise
  pyodidePromise = (async () => {
    let lastErr = null
    for (const base of pyodideSources()) {
      try {
        await loadScript(`${base}pyodide.js`)
        if (!window.loadPyodide) throw new Error('Pyodide loader unavailable')
        // indexURL must match the base the loader came from — Pyodide resolves
        // its .wasm and stdlib relative to it, so a mismatch would fetch the
        // runtime from somewhere other than the copy we actually shipped.
        return await window.loadPyodide({ indexURL: base })
      } catch {
        lastErr = err
      }
    }
    throw lastErr || new Error('Pyodide loader unavailable')
  })().catch((err) => {
    // Reset so a later attempt can retry after a transient failure.
    pyodidePromise = null
    throw err
  })
  return pyodidePromise
}

/**
 * Run Python source and capture stdout/stderr.
 * Returns { ok, stdout, stderr, error, runtimeMissing }.
 *
 * `runtimeMissing` distinguishes "the Pyodide runtime never loaded" from "your
 * code threw". Callers surface an explicit banner for the former — without that
 * flag a learner only saw a stderr line and had no way to tell the runtime
 * never loaded at all.
 */
export async function runPython(source) {
  let pyodide
  try {
    pyodide = await getPyodide()
  } catch {
    return {
      ok: false,
      runtimeMissing: true,
      stdout: '',
      stderr: '',
      error: 'Python runtime could not be loaded (check your connection). You can still submit — the server will run your code.',
    }
  }

  const captured = { out: '', err: '' }
  try {
    pyodide.setStdout({ batched: (s) => { captured.out += s + '\n' } })
    pyodide.setStderr({ batched: (s) => { captured.err += s + '\n' } })
    await pyodide.runPythonAsync(source)
    return { ok: true, stdout: captured.out, stderr: captured.err, error: '' }
  } catch {
    return {
      ok: false,
      stdout: captured.out,
      stderr: captured.err,
      error: String(err && err.message ? err.message : err),
    }
  }
}

/**
 * Run the user's Python plus a list of VISIBLE tests, in-browser, for instant
 * feedback. Each test is {name, code}; a test passes if its snippet runs
 * without raising. Returns { ok, results:[{name,passed,message}], stdout, error }.
 *
 * This mirrors the backend grader's contract so the visible-test panel matches
 * what the server will independently re-verify.
 */
export async function runPythonTests(source, tests) {
  let pyodide
  try {
    pyodide = await getPyodide()
  } catch {
    return { ok: false, runtimeMissing: true, results: [], stdout: '', error: 'Python runtime unavailable.' }
  }

  const payload = JSON.stringify(
    (tests || []).map((t, i) => ({ name: t.name || `test_${i}`, code: t.code || '' }))
  )

  const harness = `
import json, traceback, io, sys
_USER_SRC = ${JSON.stringify(source)}
_TESTS = json.loads(${JSON.stringify(payload)})
_g = {'__name__': '__fixitlab__'}
_out = io.StringIO()
_results = []
_compile_error = None
_old = sys.stdout
sys.stdout = _out
try:
    exec(compile(_USER_SRC, '<solution>', 'exec'), _g)
except Exception:
    _compile_error = traceback.format_exc(limit=3)
for _t in _TESTS:
    if _compile_error is not None:
        _results.append({'name': _t['name'], 'passed': False, 'message': 'solution failed to load'})
        continue
    _local = dict(_g)
    try:
        exec(compile(_t['code'], '<test>', 'exec'), _local)
        _results.append({'name': _t['name'], 'passed': True, 'message': ''})
    except AssertionError as _e:
        _results.append({'name': _t['name'], 'passed': False, 'message': str(_e) or 'assertion failed'})
    except Exception:
        _line = traceback.format_exc(limit=2).strip().splitlines()
        _results.append({'name': _t['name'], 'passed': False, 'message': _line[-1] if _line else 'error'})
sys.stdout = _old
json.dumps({'compile_error': _compile_error, 'results': _results, 'stdout': _out.getvalue()})
`
  try {
    const raw = await pyodide.runPythonAsync(harness)
    const verdict = JSON.parse(raw)
    return {
      ok: !verdict.compile_error,
      results: verdict.results || [],
      stdout: verdict.stdout || '',
      error: verdict.compile_error || '',
    }
  } catch {
    return { ok: false, results: [], stdout: '', error: String(err && err.message ? err.message : err) }
  }
}
