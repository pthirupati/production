/**
 * IDE API Client bottom panel — request builder + response viewer over the
 * in-process mock send endpoint (never real sockets).
 */
import { useEffect, useState } from 'react'
import { Loader2, Send } from 'lucide-react'
import { labApi } from '../../api/labs'
import { runApiClientScripts } from '../../utils/ide/jsRunner'

export const API_CLIENT_STORAGE_PREFIX = 'fixitlab:api-client:'
export const HISTORY_LIMIT = 20

export const SEEDED_COLLECTION = [
  { method: 'GET', path: '/health', label: 'GET /health' },
  { method: 'GET', path: '/api/v1/pods', label: 'GET /api/v1/pods' },
  { method: 'POST', path: '/api/v1/echo', label: 'POST /api/v1/echo' },
]

export function apiClientStorageKey(sessionId) {
  return `${API_CLIENT_STORAGE_PREFIX}${sessionId || 'anon'}`
}

export function loadApiClientDraft(sessionId, storage = typeof localStorage !== 'undefined' ? localStorage : null) {
  try {
    const raw = storage?.getItem?.(apiClientStorageKey(sessionId))
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return null
    return parsed
  } catch {
    return null
  }
}

export function saveApiClientDraft(sessionId, draft, storage = typeof localStorage !== 'undefined' ? localStorage : null) {
  try {
    storage?.setItem?.(apiClientStorageKey(sessionId), JSON.stringify({
      ...draft,
      ts: Date.now(),
    }))
  } catch { /* private mode */ }
}

/** Prefer the newer of local vs server draft (by ts). */
export function mergeApiClientDrafts(local, server) {
  if (!server || typeof server !== 'object') return local || null
  if (!local || typeof local !== 'object') return server
  const lt = Number(local.ts) || 0
  const st = Number(server.ts) || 0
  return st >= lt ? { ...local, ...server } : { ...server, ...local }
}

export function pushHistory(history, entry, limit = HISTORY_LIMIT) {
  const next = [{ ...entry, ts: Date.now() }, ...(history || [])]
  return next.slice(0, limit)
}

/** Inject Authorization / API-key header from Auth tab settings (does not clobber an explicit header). */
export function applyAuthHeaders(headers = {}, auth = { type: 'none' }) {
  const out = { ...(headers || {}) }
  const hasAuth = Object.keys(out).some((k) => k.toLowerCase() === 'authorization')
  const type = auth?.type || 'none'
  if (type === 'bearer' && auth.token && !hasAuth) {
    out.Authorization = `Bearer ${auth.token}`
  } else if (type === 'basic' && (auth.username || auth.password) && !hasAuth) {
    const raw = `${auth.username || ''}:${auth.password || ''}`
    const b64 = typeof btoa === 'function'
      ? btoa(unescape(encodeURIComponent(raw)))
      : (typeof globalThis !== 'undefined' && globalThis.Buffer
        ? globalThis.Buffer.from(raw, 'utf8').toString('base64')
        : btoa(raw))
    out.Authorization = `Basic ${b64}`
  } else if (type === 'apikey' && auth.key && auth.value) {
    const hk = auth.key
    const exists = Object.keys(out).some((k) => k.toLowerCase() === hk.toLowerCase())
    if (!exists) out[hk] = auth.value
  }
  return out
}

/** Collapsible JSON tree for the Pretty response tab. */
export function JsonTreeNode({ name, value, depth = 0 }) {
  const isObj = value !== null && typeof value === 'object'
  const isArr = Array.isArray(value)
  if (!isObj) {
    const shown = typeof value === 'string' ? JSON.stringify(value) : String(value)
    return (
      <div className="font-mono text-[10px] leading-snug" style={{ paddingLeft: depth * 10 }}>
        {name != null && <span className="text-sky-300">{name}: </span>}
        <span className={typeof value === 'string' ? 'text-amber-200' : 'text-emerald-300'}>{shown}</span>
      </div>
    )
  }
  const keys = isArr ? value.map((_, i) => i) : Object.keys(value)
  const label = name != null
    ? `${name}: ${isArr ? `[${keys.length}]` : `{${keys.length}}`}`
    : (isArr ? `Array(${keys.length})` : `Object(${keys.length})`)
  return (
    <details open={depth < 2} className="font-mono text-[10px]" style={{ paddingLeft: depth ? 10 : 0 }}>
      <summary className="cursor-pointer text-violet-300 select-none">{label}</summary>
      {keys.length === 0 ? (
        <div style={{ paddingLeft: 10 }} className="text-[var(--vsc-muted)]">{isArr ? '[]' : '{}'}</div>
      ) : keys.map((k) => (
        <JsonTreeNode
          key={`${name}-${k}`}
          name={isArr ? String(k) : k}
          value={isArr ? value[k] : value[k]}
          depth={depth + 1}
        />
      ))}
    </details>
  )
}

/** Build sandboxed srcDoc for the response Preview tab (HTML bodies or JSON pretty-wrap). */
export function responsePreviewSrcDoc(response) {
  if (!response) return ''
  const headers = response.headers || {}
  const ct = String(
    headers['content-type'] || headers['Content-Type'] || '',
  ).toLowerCase()
  let text = response.body_text
  if (text == null) {
    if (typeof response.body === 'string') text = response.body
    else if (response.body != null) {
      try { text = JSON.stringify(response.body, null, 2) } catch { text = String(response.body) }
    } else text = ''
  }
  text = String(text)
  if (ct.includes('html') || /^\s*</.test(text)) {
    return text
  }
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  return `<!doctype html><meta charset="utf-8"><pre style="margin:0;padding:12px;font:12px/1.4 ui-monospace,monospace;white-space:pre-wrap">${escaped}</pre>`
}

const DEFAULT_HEADERS = '{\n  "Accept": "application/json"\n}'
const DEFAULT_BODY = '{\n  "ping": true\n}'
const DEFAULT_VARS = '{\n  "host": "api.local"\n}'
const DEFAULT_PRE = '// pm.environment.set("token", "demo")\n// pm.request.headers.add({ key: "X-Demo", value: "1" })\n'
const DEFAULT_TESTS = 'pm.test("status 2xx", () => {\n  pm.expect(pm.response.code).to.eql(200)\n})\n'

export function IdeApiClientPanel({ sessionId, disabled = false }) {
  const saved = loadApiClientDraft(sessionId)
  const [method, setMethod] = useState(saved?.method || 'GET')
  const [url, setUrl] = useState(saved?.url || '/health')
  const [headersText, setHeadersText] = useState(saved?.headersText || DEFAULT_HEADERS)
  const [bodyText, setBodyText] = useState(saved?.bodyText || DEFAULT_BODY)
  const [varsText, setVarsText] = useState(saved?.varsText || DEFAULT_VARS)
  const [preRequest, setPreRequest] = useState(saved?.preRequest || DEFAULT_PRE)
  const [testScript, setTestScript] = useState(saved?.testScript || DEFAULT_TESTS)
  const [history, setHistory] = useState(() => Array.isArray(saved?.history) ? saved.history : [])
  const [authType, setAuthType] = useState(saved?.authType || 'none')
  const [authToken, setAuthToken] = useState(saved?.authToken || '')
  const [authUser, setAuthUser] = useState(saved?.authUser || '')
  const [authPass, setAuthPass] = useState(saved?.authPass || '')
  const [authKey, setAuthKey] = useState(saved?.authKey || 'X-API-Key')
  const [authValue, setAuthValue] = useState(saved?.authValue || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [response, setResponse] = useState(null)
  const [scriptResults, setScriptResults] = useState(null)
  const [bodyTab, setBodyTab] = useState('pretty')

  useEffect(() => {
    saveApiClientDraft(sessionId, {
      method, url, headersText, bodyText, varsText, preRequest, testScript, history,
      authType, authToken, authUser, authPass, authKey, authValue,
    })
  }, [
    sessionId, method, url, headersText, bodyText, varsText, preRequest, testScript, history,
    authType, authToken, authUser, authPass, authKey, authValue,
  ])

  // Server merge on mount — newer ts wins so device-switch / cleared localStorage recovers.
  useEffect(() => {
    if (!sessionId) return undefined
    let cancelled = false
    ;(async () => {
      try {
        const data = await labApi.getApiClientDraft(sessionId)
        if (cancelled) return
        const server = data?.draft
        const local = loadApiClientDraft(sessionId)
        const merged = mergeApiClientDrafts(local, server)
        if (!merged) return
        if (merged.method) setMethod(merged.method)
        if (merged.url) setUrl(merged.url)
        if (merged.headersText != null) setHeadersText(merged.headersText)
        if (merged.bodyText != null) setBodyText(merged.bodyText)
        if (merged.varsText != null) setVarsText(merged.varsText)
        if (merged.preRequest != null) setPreRequest(merged.preRequest)
        if (merged.testScript != null) setTestScript(merged.testScript)
        if (Array.isArray(merged.history)) setHistory(merged.history)
        if (merged.authType) setAuthType(merged.authType)
        if (merged.authToken != null) setAuthToken(merged.authToken)
        if (merged.authUser != null) setAuthUser(merged.authUser)
        if (merged.authPass != null) setAuthPass(merged.authPass)
        if (merged.authKey != null) setAuthKey(merged.authKey)
        if (merged.authValue != null) setAuthValue(merged.authValue)
        saveApiClientDraft(sessionId, merged)
      } catch { /* offline / 404 */ }
    })()
    return () => { cancelled = true }
  }, [sessionId])

  // Debounced durable server copy of the local draft.
  useEffect(() => {
    if (!sessionId || disabled) return undefined
    const id = setTimeout(() => {
      labApi.saveApiClientDraft(sessionId, {
        method, url, headersText, bodyText, varsText, preRequest, testScript, history,
        authType, authToken, authUser, authPass, authKey, authValue,
        ts: Date.now(),
      }).catch(() => {})
    }, 800)
    return () => clearTimeout(id)
  }, [
    sessionId, disabled, method, url, headersText, bodyText, varsText, preRequest, testScript, history,
    authType, authToken, authUser, authPass, authKey, authValue,
  ])

  const applyCollection = (item) => {
    setMethod(item.method)
    setUrl(item.path)
  }

  const send = async () => {
    if (!sessionId || disabled) return
    setBusy(true)
    setError('')
    setScriptResults(null)
    let headers = {}
    let variables = {}
    let body
    try {
      headers = headersText.trim() ? JSON.parse(headersText) : {}
      variables = varsText.trim() ? JSON.parse(varsText) : {}
      if (method !== 'GET' && method !== 'HEAD' && bodyText.trim()) {
        body = JSON.parse(bodyText)
      }
    } catch (e) {
      setBusy(false)
      setError(`JSON parse error: ${e.message}`)
      return
    }
    try {
      const pre = await runApiClientScripts({
        preRequest,
        tests: '',
        environment: variables,
        request: { headers },
      })
      if (pre.error && !pre.timedOut) {
        // soft: still send with original headers if pre failed compile-only empty
      }
      headers = { ...headers, ...(pre.headers || {}) }
      variables = { ...variables, ...(pre.environment || {}) }
      if (Object.keys(pre.environment || {}).length) {
        setVarsText(JSON.stringify(pre.environment, null, 2))
      }
      if (Object.keys(pre.headers || {}).length) {
        setHeadersText(JSON.stringify(pre.headers, null, 2))
      }

      headers = applyAuthHeaders(headers, {
        type: authType,
        token: authToken,
        username: authUser,
        password: authPass,
        key: authKey,
        value: authValue,
      })

      const data = await labApi.apiClientSend(sessionId, {
        method, url, headers, body, variables,
      })
      setResponse(data)
      setBodyTab('pretty')
      setHistory((h) => pushHistory(h, {
        method,
        url: data?.request?.url || url,
        status: data?.status,
      }))

      if (testScript.trim()) {
        const post = await runApiClientScripts({
          preRequest: '',
          tests: testScript,
          environment: variables,
          request: { headers },
          response: data,
        })
        setScriptResults(post)
      }
    } catch (e) {
      setError(e?.response?.data?.error || e.message || 'Send failed')
    } finally {
      setBusy(false)
    }
  }

  const prettyBody = (() => {
    if (!response) return ''
    if (typeof response.body === 'object') {
      try { return JSON.stringify(response.body, null, 2) } catch { /* fall */ }
    }
    return response.body_text || String(response.body ?? '')
  })()

  return (
    <div className="space-y-2 font-sans text-xs" data-testid="ide-api-client">
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label="Collection"
          className="vsc-btn py-0.5 px-1"
          defaultValue=""
          onChange={(e) => {
            const item = SEEDED_COLLECTION.find((c) => c.label === e.target.value)
            if (item) applyCollection(item)
          }}
          disabled={busy || disabled}
        >
          <option value="">Collection…</option>
          {SEEDED_COLLECTION.map((c) => (
            <option key={c.label} value={c.label}>{c.label}</option>
          ))}
        </select>
        <select
          aria-label="HTTP method"
          value={method}
          onChange={(e) => setMethod(e.target.value)}
          className="vsc-btn py-0.5 px-1"
          disabled={busy || disabled}
        >
          {['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
        <input
          aria-label="Request URL"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="/health or https://{{host}}/api/v1/pods"
          className="flex-1 min-w-[12rem] bg-surface-900 border border-surface-700 rounded px-2 py-1 font-mono text-[11px]"
          disabled={busy || disabled}
        />
        <button type="button" className="vsc-btn vsc-btn-primary" onClick={send} disabled={busy || disabled || !sessionId}>
          {busy ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
          Send
        </button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-2" data-testid="api-auth">
        <label className="block">
          <span className="text-[var(--vsc-muted)]">Auth</span>
          <select
            aria-label="Auth type"
            value={authType}
            onChange={(e) => setAuthType(e.target.value)}
            className="w-full mt-0.5 vsc-btn py-0.5 px-1"
            disabled={busy || disabled}
          >
            <option value="none">No Auth</option>
            <option value="bearer">Bearer Token</option>
            <option value="basic">Basic</option>
            <option value="apikey">API Key</option>
          </select>
        </label>
        {authType === 'bearer' && (
          <label className="block md:col-span-3">
            <span className="text-[var(--vsc-muted)]">Token</span>
            <input
              aria-label="Bearer token"
              value={authToken}
              onChange={(e) => setAuthToken(e.target.value)}
              className="w-full mt-0.5 font-mono text-[10px] bg-surface-900 border border-surface-700 rounded p-1"
              disabled={busy || disabled}
            />
          </label>
        )}
        {authType === 'basic' && (
          <>
            <label className="block">
              <span className="text-[var(--vsc-muted)]">Username</span>
              <input
                aria-label="Basic username"
                value={authUser}
                onChange={(e) => setAuthUser(e.target.value)}
                className="w-full mt-0.5 font-mono text-[10px] bg-surface-900 border border-surface-700 rounded p-1"
                disabled={busy || disabled}
              />
            </label>
            <label className="block md:col-span-2">
              <span className="text-[var(--vsc-muted)]">Password</span>
              <input
                aria-label="Basic password"
                type="password"
                value={authPass}
                onChange={(e) => setAuthPass(e.target.value)}
                className="w-full mt-0.5 font-mono text-[10px] bg-surface-900 border border-surface-700 rounded p-1"
                disabled={busy || disabled}
              />
            </label>
          </>
        )}
        {authType === 'apikey' && (
          <>
            <label className="block">
              <span className="text-[var(--vsc-muted)]">Header</span>
              <input
                aria-label="API key header"
                value={authKey}
                onChange={(e) => setAuthKey(e.target.value)}
                className="w-full mt-0.5 font-mono text-[10px] bg-surface-900 border border-surface-700 rounded p-1"
                disabled={busy || disabled}
              />
            </label>
            <label className="block md:col-span-2">
              <span className="text-[var(--vsc-muted)]">Value</span>
              <input
                aria-label="API key value"
                value={authValue}
                onChange={(e) => setAuthValue(e.target.value)}
                className="w-full mt-0.5 font-mono text-[10px] bg-surface-900 border border-surface-700 rounded p-1"
                disabled={busy || disabled}
              />
            </label>
          </>
        )}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
        <label className="block">
          <span className="text-[var(--vsc-muted)]">Headers (JSON)</span>
          <textarea
            value={headersText}
            onChange={(e) => setHeadersText(e.target.value)}
            rows={4}
            className="w-full mt-0.5 font-mono text-[10px] bg-surface-900 border border-surface-700 rounded p-1"
            disabled={busy || disabled}
          />
        </label>
        <label className="block">
          <span className="text-[var(--vsc-muted)]">Body (JSON)</span>
          <textarea
            value={bodyText}
            onChange={(e) => setBodyText(e.target.value)}
            rows={4}
            className="w-full mt-0.5 font-mono text-[10px] bg-surface-900 border border-surface-700 rounded p-1"
            disabled={busy || disabled || method === 'GET'}
          />
        </label>
        <label className="block">
          <span className="text-[var(--vsc-muted)]">Variables {'{{var}}'}</span>
          <textarea
            value={varsText}
            onChange={(e) => setVarsText(e.target.value)}
            rows={4}
            className="w-full mt-0.5 font-mono text-[10px] bg-surface-900 border border-surface-700 rounded p-1"
            disabled={busy || disabled}
          />
        </label>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <label className="block">
          <span className="text-[var(--vsc-muted)]">Pre-request (pm shim)</span>
          <textarea
            aria-label="Pre-request script"
            value={preRequest}
            onChange={(e) => setPreRequest(e.target.value)}
            rows={3}
            className="w-full mt-0.5 font-mono text-[10px] bg-surface-900 border border-surface-700 rounded p-1"
            disabled={busy || disabled}
          />
        </label>
        <label className="block">
          <span className="text-[var(--vsc-muted)]">Tests (pm.test)</span>
          <textarea
            aria-label="Test script"
            value={testScript}
            onChange={(e) => setTestScript(e.target.value)}
            rows={3}
            className="w-full mt-0.5 font-mono text-[10px] bg-surface-900 border border-surface-700 rounded p-1"
            disabled={busy || disabled}
          />
        </label>
      </div>
      {history.length > 0 && (
        <div className="flex flex-wrap gap-1" data-testid="api-history">
          {history.slice(0, 8).map((h, i) => (
            <button
              key={`${h.ts}-${i}`}
              type="button"
              className="vsc-btn py-0 px-1 text-[10px]"
              onClick={() => { setMethod(h.method); setUrl(h.url) }}
              title="Replay URL"
            >
              {h.method} {h.status ?? '—'}
            </button>
          ))}
        </div>
      )}
      {error && <p className="text-amber-300">{error}</p>}
      {scriptResults && (
        <div data-testid="api-script-results" className="text-[10px] space-y-0.5">
          {(scriptResults.results || []).map((r) => (
            <div key={r.name} className={r.passed ? 'text-emerald-300' : 'text-rose-300'}>
              {r.passed ? '✓' : '✗'} {r.name}{r.message ? ` — ${r.message}` : ''}
            </div>
          ))}
          {scriptResults.error && <div className="text-amber-300">{scriptResults.error}</div>}
        </div>
      )}
      {response && (
        <div className="border border-surface-800 rounded p-2 bg-surface-900/50 space-y-1">
          <div className="flex flex-wrap gap-2 items-center">
            <span className={`px-1.5 py-0.5 rounded font-mono ${response.ok ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'}`}>
              {response.status} {response.reason || ''}
            </span>
            <span className="text-[var(--vsc-muted)]">{response.elapsed_ms} ms · {response.bytes} B · mock</span>
          </div>
          {response.request && (
            <p className="text-[10px] text-[var(--vsc-muted)] font-mono">
              Sent {response.request.method} {response.request.url}
            </p>
          )}
          {response.assertions?.results && (
            <div data-testid="api-assertions" className="text-[10px]">
              Assertions: {response.assertions.passed ? 'pass' : 'fail'}
              {(response.assertions.results || []).filter((a) => !a.hidden).map((a) => (
                <div key={a.name} className={a.passed ? 'text-emerald-300' : 'text-rose-300'}>
                  {a.passed ? '✓' : '✗'} {a.name}
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-2">
            {['pretty', 'raw', 'headers', 'preview'].map((t) => (
              <button
                key={t}
                type="button"
                className={`vsc-btn py-0 px-1 text-[10px] ${bodyTab === t ? 'vsc-btn-primary' : ''}`}
                onClick={() => setBodyTab(t)}
              >
                {t}
              </button>
            ))}
          </div>
          {bodyTab === 'preview' ? (
            <iframe
              title="API response preview"
              data-testid="api-response-preview"
              sandbox=""
              srcDoc={responsePreviewSrcDoc(response)}
              className="w-full max-h-28 min-h-[5rem] border border-surface-700 rounded bg-white"
            />
          ) : bodyTab === 'pretty' && response.body !== null && typeof response.body === 'object' ? (
            <div
              data-testid="api-json-tree"
              className="max-h-28 overflow-auto border border-surface-800 rounded p-1 bg-surface-950/40"
            >
              <JsonTreeNode value={response.body} />
            </div>
          ) : (
            <pre className="max-h-28 overflow-auto font-mono text-[10px] whitespace-pre-wrap">
              {bodyTab === 'headers'
                ? JSON.stringify(response.headers || {}, null, 2)
                : bodyTab === 'raw'
                  ? (response.body_text || '')
                  : prettyBody}
            </pre>
          )}
        </div>
      )}
      {!response && !error && (
        <p className="text-[var(--vsc-muted)]">
          In-process mock only — graded fetch harness shares the same routes. Try GET /health.
        </p>
      )}
    </div>
  )
}

export default IdeApiClientPanel
