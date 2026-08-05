import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import {
  Play, CheckCircle2, XCircle, FileCode, Loader2, Terminal as TerminalIcon,
  ListChecks, FileText, Lightbulb, Lock, EyeOff, AlertTriangle, Trophy,
  Sparkles, Search, Sun, Moon, ZoomIn, ZoomOut, Bug, ScrollText, Save, Eye,
  Plus, Folder, RefreshCw, X, Files, Settings2,
} from 'lucide-react'
import toast from 'react-hot-toast'
import CodeEditor from './CodeEditor'
import MentorPanel from './MentorPanel'
import HtmlPreviewPane from './HtmlPreviewPane'
import IdeExplorer from './IdeExplorer'
import VsCodeWorkbench, { VscEditorTab, VscPanelTab, VscActivityButton } from './VsCodeWorkbench'
import '../../styles/vscode-workbench.css'
import { runPython, runPythonTests } from '../../utils/ide/pyodideRunner'
import { runJavaScript, runJavaScriptTests } from '../../utils/ide/jsRunner'
import { hasHtmlPreview, editorLanguageForPath, listHtmlPaths } from '../../utils/ide/composeHtmlPreview'
import {
  parentDirs, fileBasename, stubContentForPath, newFileHint,
} from '../../utils/ide/fileTree'
import { labApi } from '../../api/labs'
import { useThemeStore } from '../../store/themeStore'

const LANG_LABEL = {
  python: 'Python', javascript: 'JavaScript', js: 'JavaScript', node: 'Node.js', nodejs: 'Node.js',
  bash: 'Bash', shell: 'Shell', sh: 'Shell', typescript: 'TypeScript', ts: 'TypeScript',
  json: 'JSON', yaml: 'YAML', markdown: 'Markdown', html: 'HTML', css: 'CSS', java: 'Java',
}

function fileName(path) {
  return fileBasename(path)
}

function tsLine(text) {
  const t = new Date().toLocaleTimeString()
  return `[${t}] ${text}`
}

// localStorage key for per-session autosaved drafts. Keyed by lab session so a
// reload (or accidental navigation) restores the exact in-progress files.
const draftKey = (sessionId) => `fixitlab:ide-draft:${sessionId}`
const IDE_LAB_USER = 'lab_ide'
const IDE_LAB_PASS = 'lab_ide@123'
const IDE_AUTH_KEY = 'fixitlab_ide_auth'

function isIdeAuthenticated() {
  try {
    return sessionStorage.getItem(IDE_AUTH_KEY) === '1'
  } catch {
    return false
  }
}

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
  const [authenticated, setAuthenticated] = useState(isIdeAuthenticated)
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginError, setLoginError] = useState('')
  const [spec, setSpec] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const [files, setFiles] = useState({})        // { path: content }
  const [readonlyPaths, setReadonlyPaths] = useState(new Set())
  const [activePath, setActivePath] = useState('')
  const [openTabs, setOpenTabs] = useState([])  // ordered open editor tabs
  const [dirtyPaths, setDirtyPaths] = useState(() => new Set())
  const [expandedDirs, setExpandedDirs] = useState(() => new Set())
  const [showExplorer, setShowExplorer] = useState(true)
  const seedFilesRef = useRef({})               // last server template (for Refresh)
  const seedReadonlyRef = useRef(new Set())

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

  // Right panel: 'instructions' | 'mentor' | 'preview'
  const [rightTab, setRightTab] = useState('instructions')
  const [previewKey, setPreviewKey] = useState(0)
  const [mentor, setMentor] = useState(null)
  const [mentorLoading, setMentorLoading] = useState(false)
  // Latest run/grade context the mentor analyzes.
  const lastCtx = useRef({ output: '', error: '', tests: [] })

  const [fontSize, setFontSize] = useState(13)
  const [vimMode, setVimMode] = useState(false)
  const [formatOnSave, setFormatOnSave] = useState(true)
  const editorRef = useRef(null)
  const theme = useThemeStore((s) => s.theme)
  const toggleTheme = useThemeStore((s) => s.toggleTheme)
  const isDark = theme !== 'light'

  const mountedRef = useRef(true)
  useEffect(() => () => { mountedRef.current = false }, [])
  useEffect(() => { if (solvedProp) setSolved(true) }, [solvedProp])

  const language = spec?.language || 'python'
  const showHtmlPreview = hasHtmlPreview(files, language)
  const editorLanguage = editorLanguageForPath(activePath, language)
  const htmlPaths = listHtmlPaths(files)

  // Prefer opening the HTML document when a previewable project loads.
  useEffect(() => {
    if (!showHtmlPreview || !htmlPaths.length) return
    if (activePath && /\.html?$/i.test(activePath)) return
    const preferred = htmlPaths.find((p) => /index\.html?$/i.test(p)) || htmlPaths[0]
    if (preferred) {
      setActivePath(preferred)
      setOpenTabs((tabs) => (tabs.includes(preferred) ? tabs : [...tabs, preferred]))
    }
    setRightTab((tab) => (tab === 'instructions' ? 'preview' : tab))
  // eslint-disable-next-line react-hooks/exhaustive-deps -- only on first html detection / file set change
  }, [showHtmlPreview, htmlPaths.join('|')])

  const appendTerminal = useCallback((line) => {
    setTerminalText((prev) => (prev ? prev + '\n' : '') + tsLine(line))
  }, [])

  // ── Load the coding spec (hidden tests stripped server-side) ──
  const applySpecFiles = useCallback((s, { mergeDraft = true, announce = false } = {}) => {
    const fileMap = {}
    const ro = new Set()
    ;(s.files || []).forEach((f) => {
      if (!f?.path) return
      fileMap[f.path] = f.content || ''
      if (f.readonly) ro.add(f.path)
    })
    seedFilesRef.current = { ...fileMap }
    seedReadonlyRef.current = new Set(ro)

    if (mergeDraft) {
      const draft = loadDraft(sessionId)
      if (draft?.files) {
        let restored = false
        Object.entries(draft.files).forEach(([path, content]) => {
          if (ro.has(path) || typeof content !== 'string') return
          // Restore edits AND learner-created files not in the server seed.
          if (!(path in fileMap) || content !== fileMap[path]) {
            fileMap[path] = content
            restored = true
          }
        })
        if (restored) {
          setSavedAt(draft.ts || Date.now())
          if (announce) appendTerminal('restored your autosaved work from this browser')
        }
      }
    }

    const dirs = new Set()
    Object.keys(fileMap).forEach((p) => parentDirs(p).forEach((d) => dirs.add(d)))
    setExpandedDirs(dirs)
    setFiles(fileMap)
    setReadonlyPaths(ro)
    setDirtyPaths(new Set())
    hydratedRef.current = true
    dirtyRef.current = false

    const entry = s.entrypoint && fileMap[s.entrypoint] !== undefined
      ? s.entrypoint
      : Object.keys(fileMap)[0] || ''
    setActivePath(entry)
    setOpenTabs(entry ? [entry] : Object.keys(fileMap).slice(0, 8))
    return Object.keys(fileMap).length
  }, [sessionId, appendTerminal])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    labApi.getCodingSpec(sessionId)
      .then((data) => {
        if (cancelled) return
        const s = data.spec || {}
        setSpec(s)
        const n = applySpecFiles(s, { mergeDraft: true, announce: true })
        if (n === 0) {
          appendTerminal('warning: this lab has no starter files — use New File to begin')
        }
        if (data.validation_passed) setSolved(true)
      })
      .catch((err) => {
        if (cancelled) return
        setLoadError(err?.response?.data?.error || 'Could not load the coding environment.')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- load once per session
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
      if (saveDraft(sessionId, editable)) {
        setSavedAt(Date.now())
        setDirtyPaths(new Set())
      }
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
    setDirtyPaths((prev) => (prev.has(activePath) ? prev : new Set(prev).add(activePath)))
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
      const lineCount = composedSource().split('\n').length
      setDebugText(tsLine(
        `Run · lang=${language} · file=${entrypoint} · lines=${lineCount} · stdout=${stdout.length}b · stderr=${stderr.length}b`
      ))
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
        `Check · file=${entrypoint} · passed=${result.passed_count ?? 0}/${result.total_count ?? 0}` +
        ` · hidden=${spec?.hidden_test_count || 0} · verdict=${result.passed ? 'PASS' : result.needs_review ? 'NEEDS_REVIEW' : 'FAIL'}` +
        (result.error ? ` · err=${String(result.error).slice(0, 120)}` : '')
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

  // ── Manual save (Ctrl/Cmd+S or toolbar) — forces an immediate draft flush ──
  const handleSave = useCallback(() => {
    const editable = {}
    Object.keys(files).forEach((p) => {
      if (!readonlyPaths.has(p)) editable[p] = files[p]
    })
    if (saveDraft(sessionId, editable)) {
      setSavedAt(Date.now())
      setDirtyPaths(new Set())
      dirtyRef.current = false
      appendTerminal('saved to browser storage')
    }
  }, [files, readonlyPaths, sessionId, appendTerminal])

  // ── Explorer: folders, files, tabs ──
  const toggleDir = useCallback((path) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }, [])

  const openFile = useCallback((path) => {
    setActivePath(path)
    setOpenTabs((prev) => (prev.includes(path) ? prev : [...prev, path]))
  }, [])

  const closeTab = useCallback((path, e) => {
    e?.stopPropagation?.()
    setOpenTabs((prev) => {
      const idx = prev.indexOf(path)
      const next = prev.filter((p) => p !== path)
      setActivePath((cur) => {
        if (cur !== path) return cur
        if (!next.length) return ''
        return next[Math.max(0, idx - 1)] || next[0]
      })
      return next
    })
  }, [])

  const createFile = useCallback(() => {
    const existing = Object.keys(files)
    const suggestion = newFileHint(language, existing)
    const input = window.prompt('New file path', suggestion)
    if (!input) return
    const path = input.trim().replace(/^\/+/, '')
    if (!path) return
    if (files[path] !== undefined) { toast.error('A file already exists at that path'); return }
    setFiles((prev) => ({ ...prev, [path]: stubContentForPath(path, language) }))
    setExpandedDirs((prev) => {
      const next = new Set(prev)
      parentDirs(path).forEach((d) => next.add(d))
      return next
    })
    setOpenTabs((prev) => (prev.includes(path) ? prev : [...prev, path]))
    setActivePath(path)
    dirtyRef.current = true
    setDirtyPaths((prev) => new Set(prev).add(path))
    appendTerminal(`created ${path}`)
  }, [files, language, appendTerminal])

  const createFolder = useCallback(() => {
    const input = window.prompt('New folder path', 'new-folder')
    if (!input) return
    const dir = input.trim().replace(/^\/+|\/+$/g, '')
    if (!dir) return
    const keepPath = `${dir}/.keep`
    if (files[keepPath] !== undefined) return
    setFiles((prev) => ({ ...prev, [keepPath]: '' }))
    setExpandedDirs((prev) => {
      const next = new Set(prev)
      next.add(dir)
      parentDirs(keepPath).forEach((d) => next.add(d))
      return next
    })
    dirtyRef.current = true
    appendTerminal(`created folder ${dir}/`)
  }, [files, appendTerminal])

  const deleteFile = useCallback((path) => {
    if (readonlyPaths.has(path)) return
    if (!window.confirm(`Delete ${path}? This cannot be undone.`)) return
    setFiles((prev) => {
      const next = { ...prev }
      delete next[path]
      return next
    })
    setOpenTabs((prev) => {
      const idx = prev.indexOf(path)
      const next = prev.filter((p) => p !== path)
      setActivePath((cur) => {
        if (cur !== path) return cur
        if (!next.length) return ''
        return next[Math.max(0, idx - 1)] || next[0]
      })
      return next
    })
    setDirtyPaths((prev) => {
      if (!prev.has(path)) return prev
      const next = new Set(prev)
      next.delete(path)
      return next
    })
    dirtyRef.current = true
    appendTerminal(`deleted ${path}`)
  }, [readonlyPaths, appendTerminal])

  const renameFile = useCallback((path) => {
    if (readonlyPaths.has(path)) return
    const input = window.prompt('Rename file', path)
    if (!input) return
    const next = input.trim().replace(/^\/+/, '')
    if (!next || next === path) return
    if (files[next] !== undefined) { toast.error('A file already exists at that path'); return }
    setFiles((prev) => {
      const copy = { ...prev }
      copy[next] = copy[path]
      delete copy[path]
      return copy
    })
    setOpenTabs((prev) => prev.map((p) => (p === path ? next : p)))
    setActivePath((prev) => (prev === path ? next : prev))
    setDirtyPaths((prev) => {
      if (!prev.has(path)) return prev
      const copy = new Set(prev)
      copy.delete(path)
      copy.add(next)
      return copy
    })
    dirtyRef.current = true
    appendTerminal(`renamed ${path} → ${next}`)
  }, [files, readonlyPaths, appendTerminal])

  // ── Reload starter files from the server, discarding local drafts ──
  const handleRefresh = useCallback(async () => {
    if (solved || loading) return
    if (dirtyRef.current && !window.confirm('Reload starter files? This discards local edits.')) return
    try {
      const data = await labApi.getCodingSpec(sessionId)
      const s = data.spec || {}
      setSpec(s)
      applySpecFiles(s, { mergeDraft: false, announce: false })
      clearDraft(sessionId)
      appendTerminal('reloaded starter files from server')
      toast.success('Starter files reloaded')
    } catch (err) {
      toast.error(err?.response?.data?.error || 'Could not reload starter files')
    }
  }, [solved, loading, sessionId, applySpecFiles, appendTerminal])

  if (!authenticated) {
    const submitLogin = (e) => {
      e.preventDefault()
      const ok = loginUser.trim().toLowerCase() === IDE_LAB_USER && loginPass === IDE_LAB_PASS
      if (ok) {
        try { sessionStorage.setItem(IDE_AUTH_KEY, '1') } catch { /* ignore */ }
        setLoginError('')
        setAuthenticated(true)
      } else {
        setLoginError(`Invalid credentials. Use ${IDE_LAB_USER} / ${IDE_LAB_PASS} for training labs.`)
      }
    }

    return (
      <div className="flex-1 min-h-0 bg-[#1e1e1e] text-[#cccccc] flex flex-col">
        <div className="h-9 bg-[#2d2d30] border-b border-[#3e3e42] flex items-center px-4 text-xs">
          <span className="font-semibold text-white">FixitLab IDE</span>
          <span className="ml-2 text-[#858585]">{scenario?.title || 'Coding Lab'}</span>
        </div>
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="w-full max-w-sm bg-[#252526] border border-[#3e3e42] shadow-2xl rounded overflow-hidden">
            <div className="px-5 py-4 bg-[#007acc] text-white font-semibold flex items-center gap-2">
              <FileCode size={18} /> VS Code Workbench
            </div>
            <form onSubmit={submitLogin} className="p-5 space-y-4">
              <p className="text-sm text-[#cccccc]">Sign in to the multi-language IDE training environment.</p>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-[#969696] mb-1">Username</label>
                <input value={loginUser} onChange={(e) => setLoginUser(e.target.value)} autoFocus autoComplete="username"
                  placeholder={IDE_LAB_USER}
                  className="w-full bg-[#1e1e1e] border border-[#3e3e42] rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-[#007acc]" />
              </div>
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-[#969696] mb-1">Password</label>
                <input type="password" value={loginPass} onChange={(e) => setLoginPass(e.target.value)} autoComplete="current-password"
                  className="w-full bg-[#1e1e1e] border border-[#3e3e42] rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-[#007acc]" />
              </div>
              {loginError && <p className="text-xs text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2">{loginError}</p>}
              <button type="submit" className="w-full py-2 rounded bg-[#007acc] text-white font-semibold">
                Sign In
              </button>
              <button type="button"
                onClick={() => { setLoginUser(IDE_LAB_USER); setLoginPass(IDE_LAB_PASS); setLoginError('') }}
                className="w-full py-1.5 text-xs text-[#cccccc] border border-[#3e3e42] rounded hover:bg-[#2d2d30]">
                Use lab credentials (autofill)
              </button>
              <p className="text-[10px] text-[#969696] text-center pt-2 border-t border-[#3e3e42]">
                Training credentials: <span className="font-mono text-white">{IDE_LAB_USER}</span> / <span className="font-mono text-white">{IDE_LAB_PASS}</span>
              </p>
            </form>
          </div>
        </div>
      </div>
    )
  }

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

  const visibleTests = spec?.visible_tests || []
  const hiddenCount = spec?.hidden_test_count || 0
  const objectives = scenario?.objectives || []
  const langLabel = LANG_LABEL[(language || '').toLowerCase()] || language
  const mentorDisabled = !lastCtx.current.output && !lastCtx.current.error && !lastCtx.current.tests.length && !mentor
  const tabPaths = openTabs.filter((p) => files[p] !== undefined)
  const protectedPaths = new Set(Object.keys(seedFilesRef.current).filter((p) => seedReadonlyRef.current.has(p)))

  const BOTTOM_TABS = [
    { key: 'terminal', label: 'Terminal', icon: TerminalIcon },
    { key: 'output', label: 'Output', icon: ScrollText },
    { key: 'logs', label: 'Logs', icon: FileText },
    { key: 'tests', label: 'Test Results', icon: ListChecks },
    { key: 'debug', label: 'Debug Console', icon: Bug },
  ]

  return (
    <VsCodeWorkbench
      theme="app"
      className="flex-1 min-h-0"
      title={`${langLabel} IDE`}
      subtitle={scenario?.title || 'Coding Lab'}
      toolbar={(
        <>
          <button type="button" onClick={handleRun} disabled={running || checking || solved || !activePath} className="vsc-btn" title="Run (Ctrl/Cmd+Enter)">
            {running ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
            {pyLoading && running ? 'Loading…' : 'Run'}
          </button>
          <button type="button" onClick={handleCheck} disabled={checking || running || solved} className="vsc-btn vsc-btn-primary" title="Grade on server">
            {checking ? <Loader2 size={13} className="animate-spin" /> : solved ? <Trophy size={13} /> : <ListChecks size={13} />}
            {solved ? 'Solved' : 'Check Solution'}
          </button>
          <button type="button" onClick={handleSave} disabled={solved} className="vsc-btn" title="Save (Ctrl/Cmd+S)">
            <Save size={13} /> Save
          </button>
          <button type="button" onClick={handleRefresh} disabled={solved || loading} className="vsc-btn" title="Reload lab starter files">
            <RefreshCw size={13} /> Refresh
          </button>
          <button type="button" onClick={() => editorRef.current?.openSearch()} className="vsc-btn" title="Find (Ctrl/Cmd+F)"><Search size={13} /></button>
          <button type="button" onClick={() => setVimMode((v) => !v)} className={`vsc-btn ${vimMode ? 'vsc-btn-primary' : ''}`} title="Toggle Vim keybindings">
            Vim
          </button>
          <button type="button" onClick={() => editorRef.current?.formatDocument?.()} className="vsc-btn" title="Format document">Format</button>
          <button
            type="button"
            onClick={() => setFormatOnSave((v) => !v)}
            className={`vsc-btn ${formatOnSave ? 'vsc-btn-primary' : ''}`}
            title="Format on Save"
          >
            <Settings2 size={13} /> FoS
          </button>
          <button type="button" onClick={() => setFontSize((f) => Math.max(10, f - 1))} className="vsc-btn" title="Zoom out"><ZoomOut size={13} /></button>
          <button type="button" onClick={() => setFontSize((f) => Math.min(22, f + 1))} className="vsc-btn" title="Zoom in"><ZoomIn size={13} /></button>
          <button type="button" onClick={toggleTheme} className="vsc-btn" title="Toggle theme">{isDark ? <Sun size={13} /> : <Moon size={13} />}</button>
          <button type="button" onClick={() => { setRightTab('mentor'); if (!mentor) askMentor('all') }} className="vsc-btn"><Sparkles size={13} /> Mentor</button>
          {showHtmlPreview && (
            <button
              type="button"
              onClick={() => { setRightTab('preview'); setPreviewKey((k) => k + 1) }}
              className={`vsc-btn ${rightTab === 'preview' ? 'vsc-btn-primary' : ''}`}
              title="Live HTML preview"
            >
              <Eye size={13} /> Preview
            </button>
          )}
          {(savedAt && !solved) && (
            <span className="text-[10px] text-emerald-400 flex items-center gap-1">
              <Save size={11} /> {dirtyPaths.size ? 'Edited' : 'Saved'}
            </span>
          )}
          <span className="text-[10px] text-[var(--vsc-muted)] hidden lg:inline flex items-center gap-1"><EyeOff size={10} /> {hiddenCount} hidden</span>
        </>
      )}
      activityBar={(
        <div className="vsc-activity-bar hidden sm:flex">
          <VscActivityButton active={showExplorer} onClick={() => setShowExplorer((v) => !v)} title="Explorer">
            <Files size={22} />
          </VscActivityButton>
          <VscActivityButton active={bottomTab === 'terminal'} onClick={() => setBottomTab('terminal')} title="Terminal">
            <TerminalIcon size={22} />
          </VscActivityButton>
          <VscActivityButton active={bottomTab === 'tests'} onClick={() => setBottomTab('tests')} title="Test Results">
            <ListChecks size={22} />
          </VscActivityButton>
        </div>
      )}
      showSidebar={showExplorer}
      sidebarHeader={(
        <div className="flex items-center justify-between gap-1 w-full">
          <span>EXPLORER</span>
          <div className="flex items-center gap-0.5">
            <button type="button" onClick={createFolder} disabled={solved} className="p-0.5 text-[var(--vsc-accent)]" title="New folder"><Folder size={12} /></button>
            <button type="button" onClick={createFile} disabled={solved} className="p-0.5 text-[var(--vsc-accent)]" title="New file"><Plus size={12} /></button>
            <button type="button" onClick={handleRefresh} disabled={solved} className="p-0.5 text-[var(--vsc-muted)]" title="Refresh"><RefreshCw size={12} /></button>
          </div>
        </div>
      )}
      sidebar={(
        <IdeExplorer
          files={files}
          activePath={activePath}
          dirtyPaths={dirtyPaths}
          readonlyPaths={readonlyPaths}
          protectedPaths={protectedPaths}
          expandedDirs={expandedDirs}
          onToggleDir={toggleDir}
          onOpenFile={openFile}
          onDeleteFile={solved ? undefined : deleteFile}
          onRenameFile={solved ? undefined : renameFile}
          onCreateFile={solved ? undefined : createFile}
          emptyHint="No files in this lab yet. Create a file or folder, or ask support if the lab should have starters."
        />
      )}
      editorTabs={tabPaths.length ? tabPaths.map((p) => (
        <VscEditorTab key={p} active={activePath === p} onClick={() => openFile(p)}>
          <FileCode size={12} />
          <span className="truncate max-w-[120px]">{fileName(p)}</span>
          {dirtyPaths.has(p) && !readonlyPaths.has(p) && <span className="text-amber-400">●</span>}
          {readonlyPaths.has(p) && <Lock size={10} className="opacity-50" />}
          {!solved && (
            <span
              role="button"
              tabIndex={0}
              className="ml-1 opacity-50 hover:opacity-100"
              title="Close"
              onClick={(e) => closeTab(p, e)}
              onKeyDown={(e) => { if (e.key === 'Enter') closeTab(p, e) }}
            >
              <X size={11} />
            </span>
          )}
        </VscEditorTab>
      )) : (
        <div className="px-3 py-1.5 text-[11px] text-[var(--vsc-muted)]">No open editors</div>
      )}
      editor={activePath && files[activePath] !== undefined ? (
        <CodeEditor
          ref={editorRef}
          key={`${activePath}:${vimMode ? 'vim' : 'norm'}`}
          value={files[activePath] ?? ''}
          onChange={handleEditorChange}
          onSave={handleSave}
          language={editorLanguage}
          readOnly={solved || readonlyPaths.has(activePath)}
          onRun={handleRun}
          fontSize={fontSize}
          vimMode={vimMode}
          formatOnSave={formatOnSave}
        />
      ) : (
        <div className="h-full flex flex-col items-center justify-center gap-3 text-[var(--vsc-muted)] text-sm p-6 text-center">
          <FileCode size={36} className="opacity-40" />
          <p>{Object.keys(files).length ? 'Select a file from the Explorer' : 'No file open'}</p>
          {!solved && (
            <button type="button" onClick={createFile} className="vsc-btn vsc-btn-primary">
              <Plus size={13} /> New File
            </button>
          )}
        </div>
      )}
      bottomPanel={{
        height: 224,
        tabs: BOTTOM_TABS.map(({ key, label, icon: Icon }) => (
          <VscPanelTab key={key} active={bottomTab === key} onClick={() => setBottomTab(key)}>
            <Icon size={12} /> {label}
            {key === 'tests' && testResults && (
              <span className="ml-1 text-[9px] opacity-80">{testResults.passed_count}/{testResults.total_count}</span>
            )}
          </VscPanelTab>
        )),
        content: (
          <>
            {bottomTab === 'terminal' && (
              <pre className="text-[var(--vsc-text)] whitespace-pre-wrap break-words m-0">
                {terminalText || 'Run or Check Solution to see a session transcript here.'}
              </pre>
            )}
            {bottomTab === 'output' && (
              <pre className="text-[var(--vsc-text)] whitespace-pre-wrap break-words m-0">
                {output || 'Click Run to execute your code. stdout appears here.'}
              </pre>
            )}
            {bottomTab === 'logs' && (
              <pre className="text-red-400 whitespace-pre-wrap break-words m-0">
                {logsText || 'stderr and runtime errors appear here.'}
              </pre>
            )}
            {bottomTab === 'tests' && (
              <div className="space-y-1.5 font-sans">
                {!testResults ? (
                  <p className="text-xs text-[var(--vsc-muted)]">Click Check Solution to run all tests on the server.</p>
                ) : (
                  <>
                    <div className="flex items-center justify-between mb-1 text-xs">
                      <span>{testResults.passed_count}/{testResults.total_count} passed{testResults.preview && ' (preview)'}</span>
                      {testResults.hidden_total > 0 && <span className="text-[var(--vsc-muted)] flex items-center gap-1"><EyeOff size={10} /> {testResults.hidden_total} hidden</span>}
                    </div>
                    {(() => {
                      const fail = firstFailingVisible(testResults.tests)
                      if (!fail) return null
                      return (
                        <div className="rounded border border-red-500/30 bg-red-500/10 p-2 mb-1.5 text-xs">
                          <p className="font-semibold text-red-400 flex items-center gap-1"><XCircle size={12} /> {fail.name}</p>
                          {fail.message && <p className="font-mono text-red-300/90 mt-1 whitespace-pre-wrap">{fail.message}</p>}
                          <button onClick={() => askMentor('tests')} disabled={mentorLoading} className="mt-2 vsc-btn"><Sparkles size={11} /> Why did this fail?</button>
                        </div>
                      )
                    })()}
                    {(testResults.tests || []).map((t, i) => <TestRow key={i} {...t} />)}
                  </>
                )}
              </div>
            )}
            {bottomTab === 'debug' && (
              <div className="space-y-2 font-sans">
                <pre className="text-cyan-400 whitespace-pre-wrap break-words m-0 text-xs">{debugText || 'Diagnostics from Run / Check appear here.'}</pre>
                {(output || logsText || testResults) && (
                  <button onClick={() => askMentor('all')} disabled={mentorLoading} className="vsc-btn"><Sparkles size={12} /> Ask Mentor</button>
                )}
              </div>
            )}
          </>
        ),
      }}
      rightPanel={{
        width: rightTab === 'preview' ? 420 : 320,
        header: (
          <>
            <button onClick={() => setRightTab('instructions')} className={`vsc-right-tab ${rightTab === 'instructions' ? 'active' : ''}`}>
              <FileText size={12} className="inline mr-1" /> Instructions
            </button>
            {showHtmlPreview && (
              <button onClick={() => setRightTab('preview')} className={`vsc-right-tab ${rightTab === 'preview' ? 'active' : ''}`}>
                <Eye size={12} className="inline mr-1" /> Preview
              </button>
            )}
            <button onClick={() => { setRightTab('mentor'); if (!mentor) askMentor('all') }} className={`vsc-right-tab ${rightTab === 'mentor' ? 'active' : ''}`}>
              <Sparkles size={12} className="inline mr-1" /> Mentor
            </button>
          </>
        ),
        content: rightTab === 'mentor' ? (
          <MentorPanel report={mentor} loading={mentorLoading} onAsk={(req) => askMentor(req)} onUnlock={handleUnlockReference} disabled={mentorDisabled} />
        ) : rightTab === 'preview' && showHtmlPreview ? (
          <HtmlPreviewPane
            key={previewKey}
            files={files}
            htmlPath={/\.html?$/i.test(activePath || '') ? activePath : undefined}
            onRefresh={() => setPreviewKey((k) => k + 1)}
          />
        ) : (
          <div className="p-4 space-y-4 text-sm">
            <div>
              <h3 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--vsc-muted)] mb-1.5">Task</h3>
              <p className="text-[var(--vsc-text)] leading-relaxed whitespace-pre-wrap">{spec?.instructions || scenario?.description || 'Implement the solution.'}</p>
            </div>
            {objectives.length > 0 && (
              <div>
                <h3 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--vsc-muted)] mb-1.5">Requirements</h3>
                <ul className="space-y-1.5">{objectives.map((obj, i) => (
                  <li key={i} className="flex items-start gap-2 text-[var(--vsc-text)]"><CheckCircle2 size={12} className="text-cyan-400 mt-0.5 shrink-0" /><span>{typeof obj === 'string' ? obj : JSON.stringify(obj)}</span></li>
                ))}</ul>
              </div>
            )}
            {visibleTests.length > 0 && (
              <div>
                <h3 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--vsc-muted)] mb-1.5">Visible tests</h3>
                <ul className="space-y-1">{visibleTests.map((t, i) => (
                  <li key={i} className="flex items-center gap-2 text-xs text-[var(--vsc-muted)]"><ListChecks size={11} /><span className="truncate">{t.name}</span></li>
                ))}</ul>
              </div>
            )}
            {showHtmlPreview && (
              <p className="text-[11px] text-cyan-400 flex gap-1.5"><Eye size={12} className="shrink-0 mt-0.5" /> Open the Preview tab to see your HTML/CSS/JS live.</p>
            )}
            {!canRunInBrowser && (
              <p className="text-[11px] text-amber-400 flex gap-1.5"><Lightbulb size={12} className="shrink-0 mt-0.5" /> Use Check Solution for {langLabel} — server grades your code.</p>
            )}
          </div>
        ),
      }}
      statusBar={{
        left: activePath || 'No file',
        center: `${langLabel} · UTF-8 · Spaces: 4${vimMode ? ' · --VIM--' : ''}${formatOnSave ? ' · FoS' : ''}`,
        right: (
          <>
            <span>{Object.keys(files).length} files</span>
            <span>{fontSize}px</span>
            <span>{solved ? 'Read-only' : dirtyPaths.size ? 'Unsaved' : 'Editing'}</span>
          </>
        ),
      }}
    />
  )
}
