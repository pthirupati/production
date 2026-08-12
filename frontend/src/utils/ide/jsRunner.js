/**
 * Client-side JavaScript execution in a sandboxed Web Worker (free, native).
 *
 * Why a Worker: user code runs off the main thread, so an infinite loop can be
 * terminated with worker.terminate() without freezing the UI, and the user's
 * code has no access to the page DOM, cookies, or app globals.
 *
 * Like the Python runner, this is for the Run button and VISIBLE tests only —
 * the authoritative verdict (with hidden tests) is computed on the backend.
 */

// The worker program, embedded as a string and instantiated from a Blob URL so
// we need no extra bundler/worker-file configuration.
const WORKER_SRC = `
self.onmessage = (e) => {
  const { source, tests } = e.data || {};
  const assert = (c, m) => { if (!c) throw new Error(m || 'assertion failed'); };
  const logs = [];
  const realLog = (...a) => logs.push(a.map(x => {
    try { return typeof x === 'string' ? x : JSON.stringify(x); } catch { return String(x); }
  }).join(' '));
  self.console = { log: realLog, info: realLog, warn: realLog, error: realLog };

  let compileError = null;
  try { new Function('assert', source); }
  catch (err) { compileError = String(err && err.stack ? err.stack : err); }

  const results = [];
  for (const t of (tests || [])) {
    if (compileError !== null) {
      results.push({ name: t.name, passed: false, message: 'solution failed to load' });
      continue;
    }
    try {
      const fn = new Function('assert', 'console', source + '\\n;(function(){\\n' + t.code + '\\n})();');
      fn(assert, self.console);
      results.push({ name: t.name, passed: true, message: '' });
    } catch (err) {
      results.push({ name: t.name, passed: false, message: String(err && err.message ? err.message : err) });
    }
  }
  self.postMessage({ compileError, results, stdout: logs.join('\\n') });
};
`

/** Sync pm shim — shared by Worker path and vitest (no Worker in Node). */
export function executePmScriptsSync({
  preRequest = '',
  tests = '',
  environment = {},
  request = {},
  response = null,
} = {}) {
  const env = { ...(environment || {}) }
  const headers = { ...((request && request.headers) || {}) }
  const logs = []
  const realLog = (...a) => logs.push(a.map((x) => {
    try { return typeof x === 'string' ? x : JSON.stringify(x) } catch { return String(x) }
  }).join(' '))
  const cons = { log: realLog, info: realLog, warn: realLog, error: realLog }
  const results = []
  const headerGet = (k) => {
    const key = String(k || '').toLowerCase()
    const src = (response && response.headers) || {}
    for (const [hk, hv] of Object.entries(src)) {
      if (String(hk).toLowerCase() === key) return String(hv)
    }
    return undefined
  }
  const pm = {
    environment: {
      get: (k) => env[k],
      set: (k, v) => { env[k] = v },
    },
    request: {
      headers: {
        add: (h) => {
          if (!h) return
          if (typeof h === 'object' && h.key != null) headers[h.key] = h.value
          else if (typeof h === 'object') Object.assign(headers, h)
        },
        get: (k) => headers[k],
      },
    },
    response: {
      code: response && response.status,
      responseTime: response && response.elapsed_ms,
      headers: { get: headerGet },
      json: () => (response && response.body != null ? response.body : null),
      text: () => {
        if (!response) return ''
        if (response.body_text != null) return String(response.body_text)
        try { return JSON.stringify(response.body) } catch { return String(response.body) }
      },
    },
    test: (name, fn) => {
      try {
        fn()
        results.push({ name: String(name || 'test'), passed: true, message: '' })
      } catch (err) {
        results.push({ name: String(name || 'test'), passed: false, message: String(err && err.message ? err.message : err) })
      }
    },
    expect: (actual) => ({
      to: {
        eql: (expected) => {
          if (actual !== expected) throw new Error(`expected ${JSON.stringify(expected)} got ${JSON.stringify(actual)}`)
        },
        equal: (expected) => {
          if (actual !== expected) throw new Error(`expected ${JSON.stringify(expected)} got ${JSON.stringify(actual)}`)
        },
        include: (expected) => {
          const s = String(actual == null ? '' : actual)
          if (!s.includes(String(expected))) throw new Error(`expected include ${expected}`)
        },
      },
    }),
  }

  let compileError = ''
  try {
    if (preRequest) {
      // eslint-disable-next-line no-new-func
      const pre = new Function('pm', 'console', preRequest)
      pre(pm, cons)
    }
    if (tests) {
      // eslint-disable-next-line no-new-func
      const post = new Function('pm', 'console', tests)
      post(pm, cons)
    }
  } catch (err) {
    compileError = String(err && err.message ? err.message : err)
  }
  const allPass = !compileError && results.every((r) => r.passed)
  return {
    ok: allPass && !compileError,
    results,
    environment: env,
    headers,
    stdout: logs.join('\n'),
    error: compileError,
    timedOut: false,
  }
}

const PM_WORKER_SRC = `
self.onmessage = (e) => {
  const { preRequest, tests, environment, request, response } = e.data || {};
  const env = Object.assign({}, environment || {});
  const headers = Object.assign({}, (request && request.headers) || {});
  const logs = [];
  const realLog = (...a) => logs.push(a.map(x => {
    try { return typeof x === 'string' ? x : JSON.stringify(x); } catch { return String(x); }
  }).join(' '));
  self.console = { log: realLog, info: realLog, warn: realLog, error: realLog };
  const results = [];
  const headerGet = (k) => {
    const key = String(k || '').toLowerCase();
    const src = (response && response.headers) || {};
    for (const [hk, hv] of Object.entries(src)) {
      if (String(hk).toLowerCase() === key) return String(hv);
    }
    return undefined;
  };
  const pm = {
    environment: {
      get: (k) => env[k],
      set: (k, v) => { env[k] = v; },
    },
    request: {
      headers: {
        add: (h) => {
          if (!h) return;
          if (typeof h === 'object' && h.key != null) headers[h.key] = h.value;
          else if (typeof h === 'object') Object.assign(headers, h);
        },
        get: (k) => headers[k],
      },
    },
    response: {
      code: response && response.status,
      responseTime: response && response.elapsed_ms,
      headers: { get: headerGet },
      json: () => (response && response.body != null ? response.body : null),
      text: () => {
        if (!response) return '';
        if (response.body_text != null) return String(response.body_text);
        try { return JSON.stringify(response.body); } catch { return String(response.body); }
      },
    },
    test: (name, fn) => {
      try {
        fn();
        results.push({ name: String(name || 'test'), passed: true, message: '' });
      } catch (err) {
        results.push({ name: String(name || 'test'), passed: false, message: String(err && err.message ? err.message : err) });
      }
    },
    expect: (actual) => ({
      to: {
        eql: (expected) => {
          if (actual !== expected) throw new Error('expected ' + JSON.stringify(expected) + ' got ' + JSON.stringify(actual));
        },
        equal: (expected) => {
          if (actual !== expected) throw new Error('expected ' + JSON.stringify(expected) + ' got ' + JSON.stringify(actual));
        },
        include: (expected) => {
          const s = String(actual == null ? '' : actual);
          if (!s.includes(String(expected))) throw new Error('expected include ' + expected);
        },
      },
    }),
  };
  let compileError = null;
  try {
    if (preRequest) {
      const pre = new Function('pm', 'console', preRequest);
      pre(pm, self.console);
    }
    if (tests) {
      const post = new Function('pm', 'console', tests);
      post(pm, self.console);
    }
  } catch (err) {
    compileError = String(err && err.message ? err.message : err);
  }
  self.postMessage({
    compileError,
    results,
    stdout: logs.join('\\n'),
    environment: env,
    headers,
  });
};
`

function makeWorker(src) {
  const blob = new Blob([src], { type: 'application/javascript' })
  const url = URL.createObjectURL(blob)
  const worker = new Worker(url)
  URL.revokeObjectURL(url)
  return worker
}

/**
 * Run user JS + tests in a worker with a hard timeout. Each test is {name, code}
 * and passes if it runs without throwing. Returns
 * { ok, results:[{name,passed,message}], stdout, error, timedOut }.
 */
export function runJavaScriptTests(source, tests, { timeoutMs = 8000 } = {}) {
  return new Promise((resolve) => {
    let worker
    try {
      worker = makeWorker(WORKER_SRC)
    } catch {
      resolve({ ok: false, results: [], stdout: '', error: 'Web Worker unavailable in this browser.', timedOut: false })
      return
    }

    const timer = setTimeout(() => {
      try { worker.terminate() } catch { /* ignore */ }
      resolve({
        ok: false, results: [], stdout: '', timedOut: true,
        error: `Execution timed out after ${Math.round(timeoutMs / 1000)}s (possible infinite loop).`,
      })
    }, timeoutMs)

    worker.onmessage = (e) => {
      clearTimeout(timer)
      try { worker.terminate() } catch { /* ignore */ }
      const { compileError, results, stdout } = e.data || {}
      resolve({
        ok: !compileError,
        results: results || [],
        stdout: stdout || '',
        error: compileError || '',
        timedOut: false,
      })
    }

    worker.onerror = (err) => {
      clearTimeout(timer)
      try { worker.terminate() } catch { /* ignore */ }
      resolve({ ok: false, results: [], stdout: '', error: String(err.message || 'Worker error'), timedOut: false })
    }

    worker.postMessage({
      source,
      tests: (tests || []).map((t, i) => ({ name: t.name || `test_${i}`, code: t.code || '' })),
    })
  })
}

/** Run plain JS (no tests) for the Run button, capturing console output. */
export function runJavaScript(source, opts = {}) {
  return runJavaScriptTests(source, [], opts).then((r) => ({
    ok: r.ok,
    stdout: r.stdout,
    error: r.error,
    timedOut: r.timedOut,
  }))
}

/**
 * Run API-client pre-request + test scripts with a Postman-like `pm` shim.
 * Returns { ok, results, environment, headers, stdout, error, timedOut }.
 */
export function runApiClientScripts({
  preRequest = '',
  tests = '',
  environment = {},
  request = {},
  response = null,
  timeoutMs = 5000,
} = {}) {
  // Vitest/Node has no Worker — sync path keeps coverage without inventing a polyfill.
  if (typeof Worker === 'undefined' || typeof Blob === 'undefined' || typeof URL === 'undefined') {
    return Promise.resolve(executePmScriptsSync({
      preRequest, tests, environment, request, response,
    }))
  }

  return new Promise((resolve) => {
    let worker
    try {
      worker = makeWorker(PM_WORKER_SRC)
    } catch {
      resolve(executePmScriptsSync({
        preRequest, tests, environment, request, response,
      }))
      return
    }

    const timer = setTimeout(() => {
      try { worker.terminate() } catch { /* ignore */ }
      resolve({
        ok: false, results: [], environment, headers: request.headers || {},
        stdout: '', timedOut: true,
        error: `Script timed out after ${Math.round(timeoutMs / 1000)}s`,
      })
    }, timeoutMs)

    worker.onmessage = (e) => {
      clearTimeout(timer)
      try { worker.terminate() } catch { /* ignore */ }
      const data = e.data || {}
      const results = data.results || []
      const compileError = data.compileError || ''
      const allPass = !compileError && results.every((r) => r.passed)
      resolve({
        ok: allPass && !compileError,
        results,
        environment: data.environment || environment,
        headers: data.headers || {},
        stdout: data.stdout || '',
        error: compileError,
        timedOut: false,
      })
    }

    worker.onerror = () => {
      clearTimeout(timer)
      try { worker.terminate() } catch { /* ignore */ }
      resolve(executePmScriptsSync({
        preRequest, tests, environment, request, response,
      }))
    }

    worker.postMessage({ preRequest, tests, environment, request, response })
  })
}
