import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import {
  Play, CheckCircle2, XCircle, FileCode, Loader2, Terminal as TerminalIcon,
  ListChecks, FileText, Lightbulb, Lock, EyeOff, AlertTriangle, Trophy,
  Sparkles, Search, Sun, Moon, ZoomIn, ZoomOut, Bug, ScrollText, Save,
} from 'lucide-react'
import toast from 'react-hot-toast'
import CodeEditor from './CodeEditor'
import MentorPanel from './MentorPanel'
import { runPython, runPythonTests } from '../../utils/ide/pyodideRunner'
import { runJavaScript, runJavaScriptTests } from '../../utils/ide/jsRunner'
import { labApi } from '../../api/labs'
import { useThemeStore } from '../../store/themeStore'

const LANG_LABEL = {
  python: 'Python', javascript: 'JavaScript', js: 'JavaScript', node: 'Node.js',
  bash: 'Bash', typescript: 'TypeScript', json: 'JSON', yaml: 'YAML', markdown: 'Markdown',
}

function fileName(path) {
  const parts = (path || '').split('/')
  return parts[parts.length - 1] || path
}

function tsLine(text) {
  const t = new Date().toLocaleTimeString()
  return `[${t}] ${text}`
}

// localStorage key for per-session autosaved drafts. Keyed by lab session so a
// reload (or accidental navigation) restores the exact in-progress files.
const draftKey = (sessionId) => `fixitlab:ide-draft:${sessionId}`

function loadDraft(sessionId) {
  try {
    const raw = localStorage.getItem(draftKey(sessionId))
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed.files === 'object' ? parsed : null
  } catch {
    return null
  }
}

function saveDraft(sessionId, files) {
  try {
    localStorage.setItem(draftKey(sessionId), JSON.stringify({ files, ts: Date.now() }))
    return true
  } catch {
    return false // quota / private mode — autosave silently degrades
  }
}

function clearDraft(sessionId) {
  try { localStorage.removeItem(draftKey(sessionId)) } catch { /* noop */ }
}

/**
 * First FAILING VISIBLE test from a graded result. Hidden tests are never
 * surfaced (no names/expected/actual) — only the message is shown for visible
 * failures, reusing the grader output already returned. Returns null if the
 * first failure is hidden or everything visible passed.
 */
function firstFailingVisible(tests) {
  if (!Array.isArray(tests)) return null
  return tests.find((t) => !t.passed && !t.hidden) || null
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
 * Layout: file explorer (left) · editor + tabs + bottom panel (center) ·
 * instructions / AI-Mentor (right). Python runs via Pyodide, JavaScript via a
 * Web Worker — both purely client-side for instant feedback.
 *
 * Bottom panel tabs (all wired to real run/grade content):
 *   Terminal       — a transcript log of Run / Check actions + their results
 *   Output         — stdout from the last Run / server grade
 *   Logs           — stderr / console output
 *   Test Results   — per-test pass/fail (hidden tests masked), local + server
 *   Debug Console   — mentor summary + diagnostics (run/grade metadata)
 *
 * AI Mentor (right tab): rule-based, FREE — explains errors/tests/concepts and
 * suggests improvements WITHOUT revealing the solution unless explicitly
 * unlocked via a confirm gate.
 *
 * "Check Solution" ALWAYS submits to the backend, which re-runs every visible +
 * hidden test in a sandbox; only the backend can mark the scenario solved.
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

  // Bottom panel: terminal | output | logs | tests | debug
  const [bottomTab, setBottomTab] = useState('output')
  const [output, setOutput] = useState('')        // stdout
  const [logsText, setLogsText] = useState('')     // stderr / console
  const [terminalText, setTerminalText] = useState('')  // action transcript
  const [debugText, setDebugText] = useState('')   // diagnostics + mentor summary
  const [testResults, setTestResults] = useState(null)
  const [running, setRunning] = useState(false)
  const [checking, setChecking] = useState(false)
  const [pyLoading, setPyLoading] = useState(false)
  const [solved, setSolved] = useState(solvedProp)
  const [savedAt, setSavedAt] = useState(null)   // last autosave timestamp (ms)
  // Guards so we only persist AFTER the spec has loaded + any draft restored,
  // never overwriting a saved draft with the initial server template. `dirtyRef`
  // gates autosave on a genuine edit so the "Saved" badge isn't shown before the
  // user has typed anything.
  const hydratedRef = useRef(false)
  const dirtyRef = useRef(false)

  // Right panel: 'instructions' | 'mentor'
  const [rightTab, setRightTab] = useState('instructions')
  const [mentor, setMentor] = useState(null)
  const [mentorLoading, setMentorLoading] = useState(false)
  // Latest run/grade context the mentor analyzes.
  const lastCtx = useRef({ output: '', error: '', tests: [] })

  const [fontSize, setFontSize] = useState(13)
  const editorRef = useRef(null)
  const theme = useThemeStore((s) => s.theme)
  const toggleTheme = useThemeStore((s) => s.toggleTheme)
  const isDark = theme !== 'light'

  const mountedRef = useRef(true)
  useEffect(() => () => { mountedRef.current = false }, [])
  useEffect(() => { if (solvedProp) setSolved(true) }, [solvedProp])

  const language = spec?.language || 'python'

  const appendTerminal = useCallback((line) => {
    setTerminalText((prev) => (prev ? prev + '\n' : '') + tsLine(line))
  }, [])

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
        // Restore autosaved drafts: overlay saved content for editable files
        // that still exist in the spec, so a reload doesn't lose work. Readonly
        // (scaffold) files always come from the server.
        const draft = loadDraft(sessionId)
        if (draft?.files) {
          let restored = false
          Object.entries(draft.files).forEach(([path, content]) => {
            if (path in fileMap && !ro.has(path) && typeof content === 'string' && content !== fileMap[path]) {
              fileMap[path] = content
              restored = true
            }
          })
          if (restored) {
            setSavedAt(draft.ts || Date.now())
            appendTerminal('restored your autosaved work from this browser')
          }
        }
        setFiles(fileMap)
        setReadonlyPaths(ro)
        // Mark hydrated on the next tick so the save-effect doesn't immediately
        // re-persist the initial state (it only fires on genuine edits after).
        hydratedRef.current = true
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

  // ── Autosave editable files to localStorage (debounced) ──
  useEffect(() => {
    if (!hydratedRef.current || loading || !dirtyRef.current) return
    const editable = {}
    Object.keys(files).forEach((p) => {
      if (!readonlyPaths.has(p)) editable[p] = files[p]
    })
    if (Object.keys(editable).length === 0) return
    const id = setTimeout(() => {
      if (saveDraft(sessionId, editable)) setSavedAt(Date.now())
    }, 600)
    return () => clearTimeout(id)
  }, [files, readonlyPaths, sessionId, loading])

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
    setFiles((prev) => {
      if (prev[activePath] === text) return prev
      dirtyRef.current = true   // genuine edit — enable autosave
      return { ...prev, [activePath]: text }
    })
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
    setLogsText('')
    appendTerminal(`$ run ${entrypoint || 'solution'} (${LANG_LABEL[language] || language})`)
    const source = composedSource()
    let stdout = ''
    let stderr = ''
    try {
      if (isPython) {
        setPyLoading(true)
        const res = await runPython(source)
        setPyLoading(false)
        if (!mountedRef.current) return
        stdout = res.stdout || (res.ok ? '(no output)' : '')
        stderr = [res.stderr, res.error].filter(Boolean).join('\n')
        setOutput(stdout)
        if (stderr) { setLogsText(stderr); setBottomTab('logs') }
      } else if (isJs) {
        const res = await runJavaScript(source, { timeoutMs: 8000 })
        if (!mountedRef.current) return
        stdout = res.stdout || (res.ok ? '(no output)' : '')
        stderr = res.error || ''
        setOutput(stdout)
        if (stderr) { setLogsText(stderr); setBottomTab('logs') }
      } else {
        stdout = `Running ${LANG_LABEL[language] || language} in the browser is not supported.\nUse "Check Solution" — the server will run and grade your code.`
        setOutput(stdout)
      }
      appendTerminal(stderr ? 'run finished with errors (see Logs)' : 'run finished')
    } catch (err) {
      stderr = String(err?.message || err)
      setLogsText(stderr)
      setBottomTab('logs')
      appendTerminal('run crashed (see Logs)')
    } finally {
      if (mountedRef.current) { setRunning(false); setPyLoading(false) }
      lastCtx.current = { output: stdout, error: stderr, tests: lastCtx.current.tests }
      setDebugText(tsLine(`Run · lang=${language} · stdout=${stdout.length}b · stderr=${stderr.length}b`))
    }
  }, [running, checking, composedSource, isPython, isJs, language, entrypoint, appendTerminal])

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
    appendTerminal('$ check-solution (grading on server: visible + hidden tests)')

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

      const tests = result.tests || []
      setTestResults({
        tests,
        passed_count: result.passed_count ?? 0,
        total_count: result.total_count ?? 0,
        hidden_total: spec?.hidden_test_count || 0,
        preview: false,
      })
      if (result.stdout) setOutput(result.stdout)
      // Feed the mentor's context from the authoritative grade.
      lastCtx.current = { output: result.stdout || '', error: result.error || '', tests }
      setDebugText(tsLine(
        `Check · passed=${result.passed_count ?? 0}/${result.total_count ?? 0}` +
        ` · hidden=${spec?.hidden_test_count || 0} · verdict=${result.passed ? 'PASS' : result.needs_review ? 'NEEDS_REVIEW' : 'FAIL'}`
      ))

      if (result.needs_review) {
        appendTerminal('server: needs manual review')
        toast(result.message || 'Submission needs manual review.', { icon: '🔎' })
        return
      }
      if (result.passed) {
        setSolved(true)
        clearDraft(sessionId)  // solved — discard the autosaved draft
        appendTerminal('server: ALL TESTS PASSED — solved')
        toast.success(result.message || 'All tests passed! Challenge solved.', { duration: 6000 })
        onSolved?.(result)
      } else {
        if (result.error) { setLogsText(result.error) }
        appendTerminal(`server: ${result.passed_count ?? 0}/${result.total_count ?? 0} passed — not solved`)
        toast(result.message || 'Some tests failed. Keep trying!', { icon: '🔍' })
      }
    } catch (err) {
      appendTerminal('check failed (network/validation error)')
      toast.error(err?.response?.data?.error || 'Validation error')
    } finally {
      if (mountedRef.current) setChecking(false)
    }
  }, [checking, running, solved, canRunInBrowser, runVisibleTests, sessionId, language, files, entrypoint, spec, onSolved, appendTerminal])

  // ── AI Mentor (rule-based, free) ──
  const askMentor = useCallback(async (requested = 'all', { unlock = false } = {}) => {
    setRightTab('mentor')
    setMentorLoading(true)
    try {
      const ctx = lastCtx.current
      const data = await labApi.codeMentor(sessionId, {
        language,
        code: composedSource(),
        output: ctx.output,
        error: ctx.error,
        test_results: ctx.tests,
        requested,
        unlock_reference: unlock,
      })
      if (!mountedRef.current) return
      // Preserve an already-unlocked reference across follow-up asks.
      setMentor((prev) => {
        if (prev?.reference?.unlocked && data?.reference && !data.reference.unlocked) {
          return { ...data, reference: prev.reference }
        }
        return data
      })
      if (data?.summary) setDebugText((p) => (p ? p + '\n' : '') + tsLine(`Mentor: ${data.summary}`))
    } catch (err) {
      if (mountedRef.current) {
        setMentor({
          summary: 'The mentor is offline right now.',
          notes: [{ kind: 'info', title: 'Mentor unavailable', detail: 'Could not reach the mentor service. Your code still runs and grades normally.' }],
          reveals_solution: false,
          reference: { unlocked: false, reference_available: false },
        })
      }
    } finally {
      if (mountedRef.current) setMentorLoading(false)
    }
  }, [sessionId, language, composedSource])

  const handleUnlockReference = useCallback(() => askMentor('all', { unlock: true }), [askMentor])

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
  const mentorDisabled = !lastCtx.current.output && !lastCtx.current.error && !lastCtx.current.tests.length && !mentor

  const BOTTOM_TABS = [
    { key: 'terminal', label: 'Terminal', icon: TerminalIcon },
    { key: 'output', label: 'Output', icon: ScrollText },
    { key: 'logs', label: 'Logs', icon: FileText },
    { key: 'tests', label: 'Test Results', icon: ListChecks },
    { key: 'debug', label: 'Debug Console', icon: Bug },
  ]

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

        {/* Editor controls */}
        <div className="w-px h-5 bg-surface-700 mx-1" />
        <button
          onClick={() => editorRef.current?.openSearch()}
          className="flex items-center gap-1.5 px-2 py-1.5 rounded-md text-xs font-medium border border-surface-700 text-surface-300 hover:border-accent-cyan hover:text-accent-cyan transition-colors"
          title="Search & replace (Ctrl/Cmd+F)"
        >
          <Search size={13} /> <span className="hidden sm:inline">Find</span>
        </button>
        <div className="hidden sm:flex items-center gap-0.5">
          <button onClick={() => setFontSize((f) => Math.max(10, f - 1))} className="p-1.5 rounded text-surface-400 hover:text-surface-100" title="Zoom out"><ZoomOut size={13} /></button>
          <button onClick={() => setFontSize((f) => Math.min(22, f + 1))} className="p-1.5 rounded text-surface-400 hover:text-surface-100" title="Zoom in"><ZoomIn size={13} /></button>
        </div>
        <button
          onClick={toggleTheme}
          className="p-1.5 rounded text-surface-400 hover:text-accent-amber transition-colors"
          title={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
        >
          {isDark ? <Sun size={14} /> : <Moon size={14} />}
        </button>
        <button
          onClick={() => { setRightTab('mentor'); if (!mentor) askMentor('all') }}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium border transition-colors ${
            rightTab === 'mentor' ? 'border-accent-purple/50 text-accent-purple bg-accent-purple/10' : 'border-surface-700 text-surface-300 hover:border-accent-purple hover:text-accent-purple'
          }`}
          title="Open the rule-based AI Mentor"
        >
          <Sparkles size={13} /> <span className="hidden md:inline">Mentor</span>
        </button>

        {savedAt && !solved && (
          <span
            className="ml-auto flex items-center gap-1 text-[11px] text-accent-green/80"
            title={`Your work is autosaved in this browser · ${new Date(savedAt).toLocaleTimeString()}`}
          >
            <Save size={11} /> <span className="hidden sm:inline">Saved</span>
          </span>
        )}
        <span className={`text-[11px] text-surface-500 hidden lg:flex items-center gap-1 ${savedAt && !solved ? '' : 'ml-auto'}`}>
          <EyeOff size={11} /> {hiddenCount} hidden test{hiddenCount === 1 ? '' : 's'} run on the server
        </span>
      </div>

      {/* Main grid: explorer | editor | right panel */}
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
                ref={editorRef}
                key={activePath}
                value={files[activePath] ?? ''}
                onChange={handleEditorChange}
                language={language}
                readOnly={solved || readonlyPaths.has(activePath)}
                onRun={handleRun}
                fontSize={fontSize}
              />
            ) : (
              <div className="h-full flex items-center justify-center text-surface-600 text-sm">No file open</div>
            )}
          </div>
          {/* VS Code-style status bar */}
          <div className="shrink-0 flex items-center justify-between gap-3 px-3 py-1 bg-[#007acc]/90 text-white text-[10px] font-mono border-t border-surface-800">
            <span className="truncate">{activePath ? fileName(activePath) : 'No file'}</span>
            <span className="hidden sm:inline">{langLabel} · UTF-8 · Spaces: 4</span>
            <span className="flex items-center gap-2 shrink-0">
              <span>{fontSize}px</span>
              <span>{solved ? 'Read-only' : 'Editing'}</span>
            </span>
          </div>

          {/* Bottom panel: Terminal / Output / Logs / Test Results / Debug Console */}
          <div className="shrink-0 h-56 flex flex-col border-t border-surface-800 bg-surface-950">
            <div className="flex border-b border-surface-800 bg-surface-900 overflow-x-auto">
              {BOTTOM_TABS.map(({ key, label, icon: Icon }) => (
                <button
                  key={key}
                  onClick={() => setBottomTab(key)}
                  className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium whitespace-nowrap transition-colors ${
                    bottomTab === key ? 'text-accent-cyan border-b-2 border-accent-cyan' : 'text-surface-500 hover:text-surface-300'
                  }`}
                >
                  <Icon size={12} /> {label}
                  {key === 'tests' && testResults && (
                    <span className={`ml-1 text-[10px] px-1 rounded ${testResults.passed_count === testResults.total_count && testResults.total_count > 0 ? 'bg-accent-green/20 text-accent-green' : 'bg-surface-800 text-surface-400'}`}>
                      {testResults.passed_count}/{testResults.total_count}
                    </span>
                  )}
                </button>
              ))}
            </div>
            <div className="flex-1 overflow-auto p-3">
              {bottomTab === 'terminal' && (
                <pre className="text-xs font-mono text-surface-300 whitespace-pre-wrap break-words">
                  {terminalText || <span className="text-surface-600">Run or Check Solution to see a session transcript here.</span>}
                </pre>
              )}
              {bottomTab === 'output' && (
                <pre className="text-xs font-mono text-surface-200 whitespace-pre-wrap break-words">
                  {output || <span className="text-surface-600">Click Run to execute your code. stdout appears here.</span>}
                </pre>
              )}
              {bottomTab === 'logs' && (
                <pre className="text-xs font-mono text-accent-red whitespace-pre-wrap break-words">
                  {logsText || <span className="text-surface-600">stderr, console output and runtime errors appear here.</span>}
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

                      {/* First failing VISIBLE test, surfaced prominently. Hidden
                          test internals are never shown — only visible failures. */}
                      {(() => {
                        const fail = firstFailingVisible(testResults.tests)
                        if (!fail) return null
                        return (
                          <div className="rounded-lg border border-accent-red/30 bg-accent-red/[0.07] p-2.5 mb-1.5">
                            <div className="flex items-center gap-1.5 mb-1">
                              <XCircle size={13} className="text-accent-red shrink-0" />
                              <span className="text-[11px] font-semibold uppercase tracking-wider text-accent-red">
                                First failing test
                              </span>
                            </div>
                            <p className="text-xs font-mono font-medium text-surface-100 break-words">{fail.name}</p>
                            {fail.message ? (
                              <p className="mt-1.5 text-[11px] font-mono text-accent-red/90 break-words whitespace-pre-wrap">
                                {fail.message}
                              </p>
                            ) : (
                              <p className="mt-1.5 text-[11px] text-surface-400">
                                This assertion didn't hold. Check your output against what this test expects.
                              </p>
                            )}
                            <button
                              onClick={() => askMentor('tests')}
                              disabled={mentorLoading}
                              className="mt-2 flex items-center gap-1.5 px-2 py-1 rounded text-[10px] font-medium border border-accent-purple/40 text-accent-purple hover:bg-accent-purple/10 disabled:opacity-50"
                            >
                              <Sparkles size={11} /> Why did this fail?
                            </button>
                          </div>
                        )
                      })()}

                      {(testResults.tests || []).map((t, i) => (
                        <TestRow key={i} {...t} />
                      ))}
                    </>
                  )}
                </div>
              )}
              {bottomTab === 'debug' && (
                <div className="space-y-2">
                  <pre className="text-xs font-mono text-accent-cyan whitespace-pre-wrap break-words">
                    {debugText || <span className="text-surface-600">Diagnostics from each Run / Check (language, byte counts, verdict) and mentor summaries appear here.</span>}
                  </pre>
                  {(output || logsText || testResults) && (
                    <button
                      onClick={() => askMentor('all')}
                      disabled={mentorLoading}
                      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-medium border border-accent-purple/40 text-accent-purple hover:bg-accent-purple/10 disabled:opacity-50"
                    >
                      <Sparkles size={12} /> Ask the AI Mentor to diagnose this
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right panel: Instructions / AI Mentor (tabbed) */}
        <div className="w-72 xl:w-80 shrink-0 border-l border-surface-800 bg-surface-900/50 hidden lg:flex flex-col min-h-0">
          <div className="shrink-0 flex border-b border-surface-800">
            <button
              onClick={() => setRightTab('instructions')}
              className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors ${
                rightTab === 'instructions' ? 'text-accent-cyan border-b-2 border-accent-cyan' : 'text-surface-500 hover:text-surface-300'
              }`}
            >
              <FileText size={12} /> Instructions
            </button>
            <button
              onClick={() => { setRightTab('mentor'); if (!mentor) askMentor('all') }}
              className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors ${
                rightTab === 'mentor' ? 'text-accent-purple border-b-2 border-accent-purple' : 'text-surface-500 hover:text-surface-300'
              }`}
            >
              <Sparkles size={12} /> AI Mentor
            </button>
          </div>

          {rightTab === 'mentor' ? (
            <MentorPanel
              report={mentor}
              loading={mentorLoading}
              onAsk={(req) => askMentor(req)}
              onUnlock={handleUnlockReference}
              disabled={mentorDisabled}
            />
          ) : (
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
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

              <div className="rounded-lg bg-accent-purple/5 border border-accent-purple/20 p-3">
                <p className="text-[11px] text-surface-300 flex items-start gap-1.5">
                  <Sparkles size={12} className="text-accent-purple mt-0.5 shrink-0" />
                  <span>
                    Stuck? Open the <button onClick={() => { setRightTab('mentor'); if (!mentor) askMentor('all') }} className="text-accent-purple underline">AI Mentor</button> — it explains
                    errors and what failing tests check, and teaches the concept, without giving away the answer.
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
          )}
        </div>
      </div>
    </div>
  )
}
