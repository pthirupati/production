import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import {
  Play, CheckCircle2, XCircle, FileCode, Loader2, Terminal as TerminalIcon,
  ListChecks, FileText, Lightbulb, Lock, EyeOff, AlertTriangle, Trophy, Timer,
} from 'lucide-react'
import toast from 'react-hot-toast'
import CodeEditor from './CodeEditor'
import { runPython, runPythonTests } from '../../utils/ide/pyodideRunner'
import { runJavaScript, runJavaScriptTests } from '../../utils/ide/jsRunner'
import { labApi } from '../../api/labs'

const LANG_LABEL = { python: 'Python', javascript: 'JavaScript', js: 'JavaScript', bash: 'Bash' }

function fileName(path) {
  const parts = (path || '').split('/')
  return parts[parts.length - 1] || path
}

/** Small status pill for a single test row. */
function TestRow({ name, passed, message, hidden }) {
  return (
    <div className="flex items-start gap-2 py-1.5 px-2 rounded border border-surface-800 bg-surface-900/60">
      {passed ? (
        <CheckCircle2 size={14} className="text-accent-green mt-0.5 shrink-0" />
      ) : (
        <XCircle size={14} className="text-accent-red mt-0.5 shrink-0" />
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          {hidden && <EyeOff size={11} className="text-surface-500 shrink-0" />}
          <span className={`text-xs font-medium truncate ${passed ? 'text-surface-200' : 'text-accent-red'}`}>{name}</span>
        </div>
        {message && !passed && (
          <p className="text-[11px] text-surface-500 mt-0.5 font-mono break-words">{message}</p>
        )}
      </div>
    </div>
  )
}

/**
 * Browser coding IDE for coding_mode scenarios.
 *
 * Layout: file explorer (left) · editor+tabs (center) · instructions (right) ·
 * Output/Tests/Console (bottom). Python runs via Pyodide, JavaScript via a Web
 * Worker — both purely client-side for instant feedback. "Check Solution"
 * ALWAYS submits to the backend, which re-runs every visible + hidden test in a
 * sandbox; only the backend can mark the scenario solved.
 *
 * Props:
 *   sessionId   lab session UUID
 *   scenario    scenario summary (title, description, objectives)
 *   onSolved    (result) => void  — called once the backend confirms a pass
 *   solved      boolean — externally controlled solved state (locks the editor)
 */
export default function CodingIDE({ sessionId, scenario, onSolved, solved: solvedProp = false }) {
  const [spec, setSpec] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const [files, setFiles] = useState({})        // { path: content }
  const [readonlyPaths, setReadonlyPaths] = useState(new Set())
  const [activePath, setActivePath] = useState('')

  const [bottomTab, setBottomTab] = useState('output') // output | tests | console
  const [output, setOutput] = useState('')
  const [consoleText, setConsoleText] = useState('')
  const [testResults, setTestResults] = useState(null)  // { tests, passed_count, total_count, hidden_total }
  const [running, setRunning] = useState(false)
  const [checking, setChecking] = useState(false)
  const [pyLoading, setPyLoading] = useState(false)
  const [solved, setSolved] = useState(solvedProp)

  const mountedRef = useRef(true)
  useEffect(() => () => { mountedRef.current = false }, [])
  useEffect(() => { if (solvedProp) setSolved(true) }, [solvedProp])

  const language = spec?.language || 'python'

  // ── Load the coding spec (hidden tests stripped server-side) ──
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    labApi.getCodingSpec(sessionId)
      .then((data) => {
        if (cancelled) return
        const s = data.spec || {}
        setSpec(s)
        const fileMap = {}
        const ro = new Set()
        ;(s.files || []).forEach((f) => {
          fileMap[f.path] = f.content || ''
          if (f.readonly) ro.add(f.path)
        })
        setFiles(fileMap)
        setReadonlyPaths(ro)
        const entry = s.entrypoint && fileMap[s.entrypoint] !== undefined
          ? s.entrypoint
          : Object.keys(fileMap)[0] || ''
        setActivePath(entry)
        if (data.validation_passed) setSolved(true)
      })
      .catch((err) => {
        if (cancelled) return
        setLoadError(err?.response?.data?.error || 'Could not load the coding environment.')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [sessionId])

  const entrypoint = useMemo(() => {
    if (spec?.entrypoint && files[spec.entrypoint] !== undefined) return spec.entrypoint
    return Object.keys(files)[0] || ''
  }, [spec, files])

  // Build a single source string from all files for execution (non-entry files
  // first so their definitions are in scope, entrypoint last).
  const composedSource = useCallback(() => {
    const paths = Object.keys(files)
    const ordered = [...paths.filter((p) => p !== entrypoint), entrypoint].filter(Boolean)
    return ordered.map((p) => files[p]).join('\n\n')
  }, [files, entrypoint])

  const handleEditorChange = useCallback((text) => {
    if (!activePath) return
    setFiles((prev) => (prev[activePath] === text ? prev : { ...prev, [activePath]: text }))
  }, [activePath])

  const isJs = ['javascript', 'js', 'node', 'nodejs'].includes((language || '').toLowerCase())
  const isPython = (language || '').toLowerCase() === 'python'
  const canRunInBrowser = isJs || isPython

  // ── Run (client-side, instant) ──
  const handleRun = useCallback(async () => {
    if (running || checking) return
    setRunning(true)
    setBottomTab('output')
    setOutput('')
    setConsoleText('')
    const source = composedSource()
    try {
      if (isPython) {
        setPyLoading(true)
        const res = await runPython(source)
        setPyLoading(false)
        if (!mountedRef.current) return
        setOutput(res.stdout || (res.ok ? '(no output)' : ''))
        if (res.stderr) setConsoleText(res.stderr)
        if (res.error) {
          setConsoleText((prev) => (prev ? prev + '\n' : '') + res.error)
          setBottomTab('console')
        }
      } else if (isJs) {
        const res = await runJavaScript(source, { timeoutMs: 8000 })
        if (!mountedRef.current) return
        setOutput(res.stdout || (res.ok ? '(no output)' : ''))
        if (res.error) {
          setConsoleText(res.error)
          setBottomTab('console')
        }
      } else {
        setOutput(`Running ${LANG_LABEL[language] || language} in the browser is not supported.\nUse "Check Solution" — the server will run and grade your code.`)
      }
    } catch (err) {
      setConsoleText(String(err?.message || err))
      setBottomTab('console')
    } finally {
      if (mountedRef.current) { setRunning(false); setPyLoading(false) }
    }
  }, [running, checking, composedSource, isPython, isJs, language])

  // ── Run visible tests in-browser for fast feedback (no completion here) ──
  const runVisibleTests = useCallback(async () => {
    const tests = spec?.visible_tests || []
    if (!tests.length) return null
    const source = composedSource()
    if (isPython) {
      setPyLoading(true)
      const r = await runPythonTests(source, tests)
      setPyLoading(false)
      return r
    }
    if (isJs) {
      return runJavaScriptTests(source, tests, { timeoutMs: 8000 })
    }
    return null
  }, [spec, composedSource, isPython, isJs])

  // ── Check Solution: authoritative backend grade (visible + HIDDEN tests) ──
  const handleCheck = useCallback(async () => {
    if (checking || running || solved) return
    setChecking(true)
    setBottomTab('tests')
    setTestResults(null)

    // Optional fast local preview of visible tests while the server grades.
    let localPreview = null
    if (canRunInBrowser) {
      try { localPreview = await runVisibleTests() } catch { /* non-fatal */ }
      if (localPreview && mountedRef.current) {
        setTestResults({
          tests: (localPreview.results || []).map((r) => ({ ...r, hidden: false })),
          passed_count: (localPreview.results || []).filter((r) => r.passed).length,
          total_count: (localPreview.results || []).length,
          hidden_total: spec?.hidden_test_count || 0,
          preview: true,
        })
      }
    }

    try {
      const result = await labApi.codeValidate(sessionId, {
        language,
        files,
        entrypoint,
      })
      if (!mountedRef.current) return

      setTestResults({
        tests: result.tests || [],
        passed_count: result.passed_count ?? 0,
        total_count: result.total_count ?? 0,
        hidden_total: spec?.hidden_test_count || 0,
        preview: false,
      })
      if (result.stdout) setOutput(result.stdout)

      if (result.needs_review) {
        toast(result.message || 'Submission needs manual review.', { icon: '🔎' })
        return
      }
      if (result.passed) {
        setSolved(true)
        toast.success(result.message || 'All tests passed! Challenge solved.', { duration: 6000 })
        onSolved?.(result)
      } else {
        if (result.error) {
          setConsoleText(result.error)
        }
        toast(result.message || 'Some tests failed. Keep trying!', { icon: '🔍' })
      }
    } catch (err) {
      toast.error(err?.response?.data?.error || 'Validation error')
    } finally {
      if (mountedRef.current) setChecking(false)
    }
  }, [checking, running, solved, canRunInBrowser, runVisibleTests, sessionId, language, files, entrypoint, spec, onSolved])

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-surface-950">
        <div className="flex flex-col items-center gap-3 text-surface-400">
          <Loader2 size={28} className="animate-spin text-accent-cyan" />
          <span className="text-sm">Loading coding environment…</span>
        </div>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="flex-1 flex items-center justify-center bg-surface-950 p-6">
        <div className="max-w-md text-center glass-card p-8 space-y-3">
          <AlertTriangle size={32} className="text-accent-amber mx-auto" />
          <h2 className="text-lg font-bold text-white">Coding environment unavailable</h2>
          <p className="text-sm text-surface-400">{loadError}</p>
        </div>
      </div>
    )
  }

  const paths = Object.keys(files)
  const visibleTests = spec?.visible_tests || []
  const hiddenCount = spec?.hidden_test_count || 0
  const objectives = scenario?.objectives || []
  const langLabel = LANG_LABEL[(language || '').toLowerCase()] || language

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-surface-950">
      {/* Action bar */}
      <div className="shrink-0 flex items-center gap-2 px-3 py-2 bg-surface-900 border-b border-surface-800">
        <span className="flex items-center gap-1.5 text-xs font-medium text-surface-300">
          <FileCode size={14} className="text-accent-cyan" /> {langLabel} IDE
        </span>
        <div className="w-px h-5 bg-surface-700 mx-1" />
        <button
          onClick={handleRun}
          disabled={running || checking || solved}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-surface-700 text-surface-200 hover:border-accent-cyan hover:text-accent-cyan disabled:opacity-50 transition-colors"
          title="Run your code (Ctrl/Cmd+Enter)"
        >
          {running ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
          {pyLoading && running ? 'Loading Python…' : 'Run'}
        </button>
        <button
          onClick={handleCheck}
          disabled={checking || running || solved}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border disabled:opacity-50 transition-colors ${
            solved
              ? 'border-accent-green/30 text-accent-green bg-accent-green/10'
              : 'border-accent-cyan/40 text-accent-cyan bg-accent-cyan/10 hover:bg-accent-cyan/20'
          }`}
          title="Grade against all tests (server-side)"
        >
          {checking ? <Loader2 size={13} className="animate-spin" /> : solved ? <Trophy size={13} /> : <ListChecks size={13} />}
          {solved ? 'Solved' : 'Check Solution'}
        </button>
        <span className="ml-auto text-[11px] text-surface-500 hidden sm:flex items-center gap-1">
          <EyeOff size={11} /> {hiddenCount} hidden test{hiddenCount === 1 ? '' : 's'} run on the server
        </span>
      </div>

      {/* Main grid: explorer | editor | instructions */}
      <div className="flex-1 flex min-h-0">
        {/* File explorer */}
        <div className="w-44 shrink-0 border-r border-surface-800 bg-surface-900/50 overflow-y-auto hidden md:block">
          <p className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-surface-500">Files</p>
          {paths.map((p) => (
            <button
              key={p}
              onClick={() => setActivePath(p)}
              className={`w-full flex items-center gap-1.5 px-3 py-1.5 text-xs text-left transition-colors ${
                activePath === p ? 'bg-accent-cyan/10 text-accent-cyan border-l-2 border-accent-cyan' : 'text-surface-300 hover:bg-surface-800 border-l-2 border-transparent'
              }`}
            >
              <FileCode size={12} className="shrink-0" />
              <span className="truncate">{fileName(p)}</span>
              {readonlyPaths.has(p) && <Lock size={10} className="ml-auto text-surface-600 shrink-0" />}
            </button>
          ))}
        </div>

        {/* Editor column */}
        <div className="flex-1 flex flex-col min-w-0 min-h-0">
          {/* Open-file tabs */}
          <div className="shrink-0 flex items-stretch overflow-x-auto bg-surface-900 border-b border-surface-800">
            {paths.map((p) => (
              <button
                key={p}
                onClick={() => setActivePath(p)}
                className={`flex items-center gap-1.5 px-3 py-2 text-xs border-r border-surface-800 whitespace-nowrap transition-colors ${
                  activePath === p ? 'bg-surface-950 text-white' : 'text-surface-400 hover:text-surface-200'
                }`}
              >
                <FileCode size={12} />
                {fileName(p)}
                {readonlyPaths.has(p) && <Lock size={10} className="text-surface-600" />}
              </button>
            ))}
          </div>
          {/* Editor */}
          <div className="flex-1 min-h-0 bg-surface-950">
            {activePath ? (
              <CodeEditor
                key={activePath}
                value={files[activePath] ?? ''}
                onChange={handleEditorChange}
                language={language}
                readOnly={solved || readonlyPaths.has(activePath)}
                onRun={handleRun}
              />
            ) : (
              <div className="h-full flex items-center justify-center text-surface-600 text-sm">No file open</div>
            )}
          </div>

          {/* Bottom panel: Output / Tests / Console */}
          <div className="shrink-0 h-56 flex flex-col border-t border-surface-800 bg-surface-950">
            <div className="flex border-b border-surface-800 bg-surface-900">
              {[
                { key: 'output', label: 'Output', icon: TerminalIcon },
                { key: 'tests', label: 'Test Results', icon: ListChecks },
                { key: 'console', label: 'Console', icon: FileText },
              ].map(({ key, label, icon: Icon }) => (
                <button
                  key={key}
                  onClick={() => setBottomTab(key)}
                  className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors ${
                    bottomTab === key ? 'text-accent-cyan border-b-2 border-accent-cyan' : 'text-surface-500 hover:text-surface-300'
                  }`}
                >
                  <Icon size={12} /> {label}
                </button>
              ))}
            </div>
            <div className="flex-1 overflow-auto p-3">
              {bottomTab === 'output' && (
                <pre className="text-xs font-mono text-surface-200 whitespace-pre-wrap break-words">
                  {output || <span className="text-surface-600">Click Run to execute your code.</span>}
                </pre>
              )}
              {bottomTab === 'console' && (
                <pre className="text-xs font-mono text-accent-red whitespace-pre-wrap break-words">
                  {consoleText || <span className="text-surface-600">Errors and warnings appear here.</span>}
                </pre>
              )}
              {bottomTab === 'tests' && (
                <div className="space-y-1.5">
                  {!testResults ? (
                    <p className="text-xs text-surface-600">Click "Check Solution" to run all tests on the server.</p>
                  ) : (
                    <>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium text-surface-300">
                          {testResults.passed_count}/{testResults.total_count} passed
                          {testResults.preview && <span className="text-surface-500"> (local preview — server is grading…)</span>}
                        </span>
                        {testResults.hidden_total > 0 && (
                          <span className="text-[11px] text-surface-500 flex items-center gap-1">
                            <EyeOff size={10} /> includes {testResults.hidden_total} hidden
                          </span>
                        )}
                      </div>
                      {(testResults.tests || []).map((t, i) => (
                        <TestRow key={i} {...t} />
                      ))}
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Instructions / requirements panel */}
        <div className="w-72 shrink-0 border-l border-surface-800 bg-surface-900/50 overflow-y-auto hidden lg:block">
          <div className="p-4 space-y-4">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-surface-500 mb-1.5">Task</h3>
              <p className="text-sm text-surface-300 leading-relaxed whitespace-pre-wrap">
                {spec?.instructions || scenario?.description || 'Implement the solution.'}
              </p>
            </div>

            {objectives.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-surface-500 mb-1.5">Requirements</h3>
                <ul className="space-y-1.5">
                  {objectives.map((obj, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-surface-300">
                      <CheckCircle2 size={12} className="text-accent-cyan mt-0.5 shrink-0" />
                      <span>{typeof obj === 'string' ? obj : JSON.stringify(obj)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {visibleTests.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-surface-500 mb-1.5">Visible tests</h3>
                <ul className="space-y-1">
                  {visibleTests.map((t, i) => (
                    <li key={i} className="flex items-center gap-2 text-xs text-surface-400">
                      <ListChecks size={11} className="text-surface-500 shrink-0" />
                      <span className="truncate">{t.name}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="rounded-lg bg-surface-800/50 border border-surface-700/50 p-3">
              <p className="text-[11px] text-surface-400 flex items-start gap-1.5">
                <EyeOff size={12} className="text-accent-amber mt-0.5 shrink-0" />
                <span>
                  {hiddenCount > 0
                    ? `${hiddenCount} hidden test${hiddenCount === 1 ? '' : 's'} run on the server when you click Check Solution. Your code must pass every test to solve this scenario.`
                    : 'Your code is graded on the server. It must pass every test to solve this scenario.'}
                </span>
              </p>
            </div>

            {!canRunInBrowser && (
              <div className="rounded-lg bg-accent-amber/5 border border-accent-amber/20 p-3">
                <p className="text-[11px] text-accent-amber flex items-start gap-1.5">
                  <Lightbulb size={12} className="mt-0.5 shrink-0" />
                  <span>In-browser Run is unavailable for {langLabel}. Use Check Solution — the server runs and grades your code.</span>
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
