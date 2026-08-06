import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import {
  Sparkles, Send, CheckCircle2, XCircle, Lightbulb, Target, BookOpen,
  Bot, User, Trophy, RotateCcw, ChevronRight, Gauge, Loader2,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { labApi } from '../../api/labs'
import VsCodeWorkbench, { VscFileItem, VscEditorTab, VscPanelTab } from '../ide/VsCodeWorkbench'
import '../../styles/vscode-workbench.css'

/*
 * PromptPlayground — a FREE, fully rule-based "AI practice" simulator for the
 * Prompt Engineering technology.
 *
 * IMPORTANT / HONEST: There is NO real language model here and NO paid API. The
 * "assistant" replies and the prompt-quality feedback are produced entirely by
 * the deterministic heuristics in this file (and re-checked server-side by
 * apps.labs.prompt_eval). The goal is to let learners *feel* what specific,
 * well-structured prompts get back versus vague ones — a teaching aid, not a
 * model. It runs 100% client-side and offline.
 *
 * Routing: opened by LabRunner when scenario.coding_mode is true AND
 * scenario.coding_spec.kind === 'prompt'. The spec is fetched from the same
 * /coding-spec/ endpoint the CodingIDE uses; prompt_config carries the lesson
 * text, rubric, and exercises.
 *
 * Props:
 *   sessionId  lab session UUID
 *   scenario   scenario summary (title, description)
 *   solved     externally controlled solved flag
 *   onSolved   (result) => void — called once the backend confirms completion
 */

// ── Rule-based prompt analysis (mirrors backend apps/labs/prompt_eval.py) ──
// The hint lists and the matcher below MUST stay byte-for-byte equivalent to
// prompt_eval.py: the server re-check is the real gate, so any drift makes the
// UI promise a pass the backend then rejects.
const ROLE_HINTS = ['you are', 'act as', 'acting as', "you're a", "you're an", 'as a', 'as an', 'imagine you', 'pretend you', 'your role', 'role:', 'persona', 'system prompt', 'you will be', 'assume the role', 'take on the role', 'take on the identity', 'respond as', 'reply as', 'answer as', 'behave like', 'speak as', 'roleplay', 'role-play', 'in the voice of', 'from the perspective of', 'you play', 'your job is', 'your task is to act', 'expert in', 'acts as', 'serve as']
const LIMIT_HINTS = ['word', 'sentence', 'bullet', 'paragraph', 'character', 'char', 'under', 'at most', 'no more than', 'max', 'maximum', 'limit', 'concise', 'brief', 'briefly', 'short', 'shorter', 'one line', 'single line', 'tl;dr', 'exactly', 'fewer', 'less than', 'no longer than', 'cap', 'token', 'at maximum', 'up to', 'keep it to', 'not exceed', 'one-liner']
const EXAMPLE_HINTS = ['example', 'e.g.', 'for instance', 'such as', 'like this', '->', 'sample', 'for example', 'demonstrated by', 'as shown', "here's one", 'here is one']
const FORMAT_HINTS = ['json', 'bullet', 'list', 'table', 'numbered', 'paragraph', 'yaml', 'csv', 'markdown', 'one word', 'one sentence', 'format', 'step', 'schema', 'template', 'heading', 'column', 'field']
const CONTEXT_HINTS = ['context', 'given', 'based on', 'using the', 'from the', 'here is', 'here are', 'the following', 'according to', '"""', '```', '<document>']
const DELIMITER_HINTS = ['"""', '```', '<document>', '</document>', '<context>', '<<<', '###', "'''"]
const CONTRADICTIONS = [['one sentence', 'paragraph'], ['one sentence', 'multi-paragraph'], ['single sentence', 'detailed'], ['brief', 'comprehensive'], ['one word', 'explain in detail']]

// A numeric cap ("in 120 tokens", "3 bullets", "<=200 chars") is a limit even
// when phrased without any keyword above.
const NUMERIC_LIMIT_RE = /(?:<=?\s*\d+|\b\d+\s*(?:word|sentence|bullet|line|paragraph|char|character|token|item|point|step)s?\b)/i

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/*
 * Word-boundary hint matcher. Plain `includes` was the core grading bug:
 * 'short' fired on 'shortcoming', 'limit' on 'limitations', 'word' on
 * 'wording', 'persona' on 'personal', and 'as a ' on 'was a '/'has a ' — so
 * nearly any past-tense sentence satisfied require_any_role. Only a trailing
 * 's' is allowed; a blanket 'ing'/'ed' would re-break 'word' -> 'wording'.
 * Longest hints first so 'no more than' wins over 'more'.
 */
const compileHints = (hints) => {
  const uniq = [...new Set(hints.map((h) => h.trim()).filter(Boolean))].sort((a, b) => b.length - a.length)
  const parts = uniq.map((h) => (/[a-z0-9]$/i.test(h) ? `${escapeRe(h)}s?\\b` : escapeRe(h)))
  return new RegExp(`(?<![A-Za-z0-9])(?:${parts.join('|')})`, 'i')
}

const ROLE_RE = compileHints(ROLE_HINTS)
const LIMIT_RE = compileHints(LIMIT_HINTS)
const EXAMPLE_RE = compileHints(EXAMPLE_HINTS)
const FORMAT_RE = compileHints(FORMAT_HINTS)

const assignsRole = (text) => ROLE_RE.test(text)
const statesLimit = (text) => LIMIT_RE.test(text) || NUMERIC_LIMIT_RE.test(text)

/** Cheap "is this a real word" proxy — no dictionary needed. */
const looksLikeWord = (token) => {
  const t = token.toLowerCase().replace(/[^a-z]/g, '')
  if (t.length < 2) return false
  if (!/[aeiouy]/.test(t)) return false      // rejects xxx / zzz / qwrt
  return new Set(t).size > 1                 // rejects aaa / bbb
}

/*
 * Reject keyword-stuffed filler ("you are xxx yyy zzz aaa bbb ..."), which used
 * to clear min_words + require_any_role. Real prompts measure 0.87-0.93
 * word-like; that gibberish measures 0.13, so 0.6 leaves a wide margin. JSON
 * prompts ({"name": string}) measure 0.93 and are unaffected.
 */
const isGibberish = (raw) => {
  const tokens = (raw || '').match(/\S+/g) || []
  if (tokens.length < 6) return false
  return tokens.filter(looksLikeWord).length / tokens.length < 0.6
}

/*
 * Imperative verbs for the live "Clear task" meter. This meter is UI-only — it
 * drives the quality gauge and the sandbox reply, NOT the completion gate — so
 * it has no server counterpart to stay in sync with.
 */
const ACTION_VERB_RE = compileHints([
  'summarize', 'summarise', 'write', 'list', 'explain', 'describe', 'compare',
  'extract', 'classify', 'translate', 'rewrite', 'generate', 'create', 'draft',
  'analyze', 'analyse', 'review', 'convert', 'return', 'produce', 'identify',
  'outline', 'suggest', 'recommend', 'find', 'fix', 'debug', 'refactor',
  'calculate', 'rank', 'sort', 'group', 'label', 'answer', 'respond', 'give',
  'provide', 'build', 'design', 'plan', 'critique', 'evaluate', 'diagnose',
])

// Substring match — kept ONLY for author-supplied require/any_of term lists.
// Scenario YAML ships stems ('instruction' must catch 'instructions', 'param'
// -> 'parameters'), so those must not get word-boundary treatment.
const hasAny = (text, needles) => needles.some((n) => text.includes(n))
const countExamplePairs = (raw) => {
  const arrows = (raw.match(/->|=>|➞|→/g) || []).length
  const labeled = (raw.match(/\b(input|output|example)\b\s*[:\-]/gi) || []).length
  return Math.max(arrows, Math.floor(labeled / 2))
}
const countListItems = (raw) => {
  const numbered = (raw.match(/^\s*\d+[.)]\s+\S/gm) || []).length
  const bullets = (raw.match(/^\s*[-*•]\s+\S/gm) || []).length
  return Math.max(numbered, bullets)
}
const requestsJson = (text) => text.includes('json') || (text.includes('{') && text.includes('}') && text.includes(':'))

// Exported for unit tests only — these are pure functions, and the grading
// rules they implement must stay in lockstep with backend prompt_eval.py.
export { assignsRole, statesLimit, isGibberish, analyzePrompt, evaluateExercise }

/** Score a prompt on the five ingredients — used for the live quality meter. */
function analyzePrompt(raw) {
  const text = (raw || '').trim().toLowerCase()
  const words = text ? text.split(/\s+/).length : 0
  // "Clear task" wants an actual imperative verb, not just 6 words of anything —
  // word count alone let "please help me with this thing" score a full check.
  const hasActionVerb = ACTION_VERB_RE.test(text)
  const substantive = !isGibberish(raw || '')
  const checks = [
    { key: 'role', label: 'Role / persona', ok: assignsRole(text), tip: 'Tell the AI who to be ("You are a…").' },
    { key: 'context', label: 'Context', ok: hasAny(text, CONTEXT_HINTS) || (substantive && words > 25), tip: 'Give the background or material it needs.' },
    { key: 'task', label: 'Clear task', ok: words >= 6 && hasActionVerb && substantive, tip: 'State the specific task with an action verb.' },
    { key: 'constraints', label: 'Constraints', ok: statesLimit(text), tip: 'Add a length, tone, or "what to avoid".' },
    { key: 'format', label: 'Output format', ok: FORMAT_RE.test(text), tip: 'Ask for bullets, JSON, a table, etc.' },
  ]
  const met = checks.filter((c) => c.ok).length
  const score = Math.round((met / checks.length) * 100)
  return { words, checks, met, score }
}

/** Evaluate one prompt against an exercise's success rules (mirrors backend). */
function evaluateExercise(raw, success) {
  const s = success || {}
  const text = (raw || '').trim().toLowerCase()
  const words = text ? text.split(/\s+/).length : 0
  const matched = []
  const missing = []
  const mark = (cond, label) => (cond ? matched : missing).push(label)

  // Word COUNT alone was gameable with filler, so min_words also requires the
  // words to be word-like (mirrors prompt_eval.evaluate_prompt).
  if (s.min_words != null) mark(words >= s.min_words && !isGibberish(raw || ''), 'enough detail')
  if (s.max_words != null) mark(words <= s.max_words, 'concise enough')
  if (s.require_any_role) mark(assignsRole(text), 'assigns a role')
  if (s.mentions_limit) mark(statesLimit(text), 'states a length/format limit')
  if (s.mentions_example) mark(EXAMPLE_RE.test(text), 'includes an example')
  if (s.has_delimiter) mark(hasAny(raw || '', DELIMITER_HINTS), 'delimits the reference text')
  if (s.requires_json_request) mark(requestsJson(text), 'asks for JSON')
  if (s.no_contradiction) mark(!CONTRADICTIONS.some(([a, b]) => text.includes(a) && text.includes(b)), 'instructions are consistent')
  if (s.min_example_pairs != null) mark(countExamplePairs(raw || '') >= s.min_example_pairs, 'includes worked examples')
  if (s.max_example_pairs != null) mark(countExamplePairs(raw || '') <= s.max_example_pairs, 'stays zero-shot')
  if (s.min_list_items != null) mark(countListItems(raw || '') >= s.min_list_items, 'batches multiple items')
  ;(s.require || []).forEach((group) => mark(group.some((t) => text.includes(t.toLowerCase())), `mentions: ${group.slice(0, 3).join(' / ')}`))
  ;(s.any_of || []).forEach((group) => mark(group.some((t) => text.includes(t.toLowerCase())), `uses: ${group.slice(0, 3).join(' / ')}`))
  ;(s.must_contain_all || []).forEach((group) => mark(group.every((t) => text.includes(t.toLowerCase())), `contains: ${group.slice(0, 3).join(' / ')}`))

  const passed = missing.length === 0 && words > 0
  return { passed, matched, missing, words }
}

const scoreColor = (score) =>
  score >= 80 ? 'text-accent-green' : score >= 50 ? 'text-accent-amber' : 'text-accent-red'
const scoreBar = (score) =>
  score >= 80 ? 'bg-accent-green' : score >= 50 ? 'bg-accent-amber' : 'bg-accent-red'

/** Live prompt-quality meter shown beneath the composer. */
function QualityMeter({ analysis }) {
  return (
    <div className="rounded-lg border border-surface-700/60 bg-surface-900/60 p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-surface-300 flex items-center gap-1.5">
          <Gauge size={13} className="text-accent-cyan" /> Prompt quality
        </span>
        <span className={`text-sm font-bold font-mono ${scoreColor(analysis.score)}`}>{analysis.score}/100</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-surface-800 overflow-hidden mb-2.5">
        <div className={`h-full rounded-full transition-all duration-300 ${scoreBar(analysis.score)}`} style={{ width: `${analysis.score}%` }} />
      </div>
      <div className="flex flex-wrap gap-1.5">
        {analysis.checks.map((c) => (
          <span
            key={c.key}
            title={c.tip}
            className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium border ${
              c.ok
                ? 'text-accent-green border-accent-green/30 bg-accent-green/10'
                : 'text-surface-500 border-surface-700 bg-surface-800/60'
            }`}
          >
            {c.ok ? <CheckCircle2 size={9} /> : <XCircle size={9} />} {c.label}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function PromptPlayground({ sessionId, scenario, solved: solvedProp = false, onSolved }) {
  const [spec, setSpec] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [solved, setSolved] = useState(solvedProp)

  const [tab, setTab] = useState('exercises') // exercises | lesson | sandbox
  // Per-exercise drafts and their last evaluation.
  const [drafts, setDrafts] = useState({})    // { exId: text }
  const [results, setResults] = useState({})  // { exId: evaluateExercise(...) }
  const [activeEx, setActiveEx] = useState(0)
  // Free-form sandbox chat transcript.
  const [chat, setChat] = useState([])        // [{ role, text, analysis }]
  const [sandboxInput, setSandboxInput] = useState('')
  const [completing, setCompleting] = useState(false)
  const [exPanelTab, setExPanelTab] = useState('output')   // output | quality
  const [sandboxPanelTab, setSandboxPanelTab] = useState('chat') // chat | quality

  const mountedRef = useRef(true)
  const chatEndRef = useRef(null)
  useEffect(() => () => { mountedRef.current = false }, [])
  useEffect(() => { if (solvedProp) setSolved(true) }, [solvedProp])
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [chat])

  // ── Load the prompt config (same endpoint as the coding IDE) ──
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    labApi.getCodingSpec(sessionId)
      .then((data) => {
        if (cancelled) return
        const s = data.spec || {}
        if (s.kind !== 'prompt') {
          setLoadError('This lab is not a prompt scenario.')
          return
        }
        setSpec(s)
        if (data.validation_passed) setSolved(true)
      })
      .catch((err) => {
        if (cancelled) return
        setLoadError(err?.response?.data?.error || 'Could not load the practice console.')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [sessionId])

  const config = spec?.prompt_config || {}
  const lessons = config.lesson || []
  const exercises = useMemo(() => config.exercises || [], [config])

  // Seed drafts from each exercise's starter text once the spec loads.
  useEffect(() => {
    if (!exercises.length) return
    setDrafts((prev) => {
      const next = { ...prev }
      exercises.forEach((ex) => {
        if (next[ex.id] === undefined) next[ex.id] = ex.starter || ''
      })
      return next
    })
  }, [exercises])

  const passedCount = exercises.filter((ex) => results[ex.id]?.passed).length
  const allPassed = exercises.length > 0 && passedCount === exercises.length

  // Build a representative simulated reply for a submitted exercise prompt.
  const replyForExercise = useCallback((ex, evalResult) => {
    if (evalResult.passed) return ex.success_response || 'Nicely done — that prompt would reliably get what you asked for.'
    return ex.partial_response || 'Close — tighten the parts the checklist flags and try again.'
  }, [])

  // ── Submit an exercise prompt (client feedback only; completion is separate) ──
  const submitExercise = useCallback((ex) => {
    const text = drafts[ex.id] || ''
    const evalResult = evaluateExercise(text, ex.success)
    setResults((prev) => ({ ...prev, [ex.id]: evalResult }))
    setExPanelTab('output')
    return evalResult
  }, [drafts])

  // ── Free-form sandbox: send a prompt, get a simulated reply + analysis ──
  const sendSandbox = useCallback(() => {
    const text = sandboxInput.trim()
    if (!text) return
    const analysis = analyzePrompt(text)
    // Deterministic, rule-based "assistant" reply keyed off prompt quality.
    let reply
    if (analysis.score >= 80) {
      reply = "That's a strong, specific prompt — clear role, task, and format. A real assistant would return exactly the shape you asked for. (This is a rule-based practice reply, not a live model.)"
    } else if (analysis.score >= 50) {
      const gap = analysis.checks.find((c) => !c.ok)
      reply = `Decent prompt. To make the reply more predictable, add: ${gap ? gap.tip : 'a clear format and a constraint.'} (Rule-based practice reply.)`
    } else {
      reply = 'That prompt is vague, so the answer would be generic. Add who the AI should be, the exact task, a constraint, and the output format you want. (Rule-based practice reply.)'
    }
    setChat((prev) => [
      ...prev,
      { role: 'user', text },
      { role: 'assistant', text: reply, analysis },
    ])
    setSandboxInput('')
  }, [sandboxInput])

  // ── Complete the lesson: re-validate every exercise on the backend ──
  const handleComplete = useCallback(async () => {
    if (completing || solved) return
    // Evaluate any not-yet-submitted exercises so the UI matches what we send.
    const fresh = {}
    exercises.forEach((ex) => { fresh[ex.id] = evaluateExercise(drafts[ex.id] || '', ex.success) })
    setResults(fresh)
    const localPass = exercises.length > 0 && exercises.every((ex) => fresh[ex.id].passed)
    if (!localPass) {
      const remaining = exercises.filter((ex) => !fresh[ex.id].passed).length
      toast(`${remaining} exercise${remaining !== 1 ? 's' : ''} still need work — see the feedback.`, { icon: '✍️' })
      setTab('exercises')
      const firstUnsolved = exercises.findIndex((ex) => !fresh[ex.id].passed)
      if (firstUnsolved >= 0) setActiveEx(firstUnsolved)
      return
    }
    setCompleting(true)
    try {
      const submissions = {}
      exercises.forEach((ex) => { submissions[ex.id] = drafts[ex.id] || '' })
      const result = await labApi.promptValidate(sessionId, submissions)
      if (!mountedRef.current) return
      if (result.passed) {
        setSolved(true)
        toast.success(result.message || 'Lesson complete!', { duration: 5000 })
        onSolved?.(result)
      } else {
        toast(result.message || 'Not all exercises passed the server check — keep refining.', { icon: '🔍' })
      }
    } catch (err) {
      toast.error(err?.response?.data?.error || 'Could not submit. Try again.')
    } finally {
      if (mountedRef.current) setCompleting(false)
    }
  }, [completing, solved, exercises, drafts, sessionId, onSolved])

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-surface-950">
        <div className="text-center">
          <Loader2 size={28} className="animate-spin text-accent-cyan mx-auto mb-3" />
          <p className="text-sm text-surface-400">Loading the AI practice console…</p>
        </div>
      </div>
    )
  }
  if (loadError) {
    return (
      <div className="flex-1 flex items-center justify-center bg-surface-950 p-6">
        <div className="max-w-md text-center glass-card p-8 space-y-3">
          <XCircle size={36} className="text-accent-red mx-auto" />
          <h2 className="text-lg font-bold text-surface-100">Practice console unavailable</h2>
          <p className="text-sm text-surface-400">{loadError}</p>
        </div>
      </div>
    )
  }

  const current = exercises[activeEx]
  const currentResult = current ? results[current.id] : null
  const currentDraft = current ? (drafts[current.id] || '') : ''
  const currentAnalysis = analyzePrompt(currentDraft)

  const promptTextareaClass = 'w-full h-full min-h-[180px] resize-none border-0 outline-none bg-transparent text-[var(--vsc-text,#e4e4e7)] font-mono text-sm p-3 leading-relaxed placeholder:text-[var(--vsc-muted,#71717a)]'

  return (
    <div className="flex-1 min-h-0 flex flex-col bg-surface-950 text-surface-200">
      {/* Free-practice honesty banner */}
      <div className="shrink-0 px-4 py-2 bg-accent-purple/10 border-b border-accent-purple/20 flex items-center gap-2 text-[11px] text-surface-300">
        <Sparkles size={12} className="text-accent-purple shrink-0" />
        <span>
          Guided <strong className="text-surface-200">AI prompt lab</strong> — replies and scoring are rule-based and 100% free (no live model). Focus on writing great prompts.
        </span>
      </div>

      {/* Progress + complete */}
      <div className="shrink-0 px-4 py-2.5 flex items-center justify-between gap-3 border-b border-surface-800 bg-surface-900/60">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex items-center gap-1.5 text-xs text-surface-400">
            <Trophy size={13} className="text-accent-amber" />
            <span className="font-medium text-surface-200">{passedCount}</span>/{exercises.length} exercises
          </div>
          <div className="h-1.5 w-28 sm:w-40 rounded-full bg-surface-800 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-accent-cyan to-accent-purple transition-all duration-500"
              style={{ width: `${exercises.length ? (passedCount / exercises.length) * 100 : 0}%` }}
            />
          </div>
        </div>
        <button
          onClick={handleComplete}
          disabled={completing || solved}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold border transition-all disabled:opacity-60 ${
            solved
              ? 'border-accent-green/30 text-accent-green bg-accent-green/10'
              : allPassed
                ? 'border-accent-green/40 text-accent-green bg-accent-green/10 hover:bg-accent-green/20'
                : 'border-accent-cyan/40 text-accent-cyan bg-accent-cyan/10 hover:bg-accent-cyan/20'
          }`}
        >
          {completing ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
          {solved ? 'Completed' : 'Complete Lesson'}
        </button>
      </div>

      {/* Tabs */}
      <div className="shrink-0 flex border-b border-surface-800 bg-surface-900/40">
        {[
          { key: 'exercises', label: 'Exercises', icon: Target },
          { key: 'lesson', label: 'Lesson', icon: BookOpen },
          { key: 'sandbox', label: 'Free Practice', icon: Bot },
        ].map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium transition-colors ${
              tab === key ? 'text-accent-cyan border-b-2 border-accent-cyan' : 'text-surface-500 hover:text-surface-300'
            }`}
          >
            <Icon size={13} /> {label}
          </button>
        ))}
      </div>

      <div className="flex-1 min-h-0 overflow-hidden">
        {/* ── Exercises tab ── */}
        {tab === 'exercises' && (
          <VsCodeWorkbench
            theme="app"
            accent="#22d3ee"
            className="h-full"
            sidebarMobile="horizontal"
            title={current?.title || 'Prompt exercise'}
            subtitle={scenario?.title}
            sidebarHeader="EXERCISES"
            sidebar={exercises.map((ex, i) => {
              const r = results[ex.id]
              return (
                <VscFileItem key={ex.id} active={i === activeEx} onClick={() => setActiveEx(i)}>
                  {r?.passed ? '✓ ' : '○ '}{ex.title}
                </VscFileItem>
              )
            })}
            editorTabs={current && (
              <VscEditorTab active>{`${current.id || 'prompt'}.txt`}</VscEditorTab>
            )}
            editorToolbar={current && (
              <div className="flex items-center gap-2 w-full">
                <button type="button" onClick={() => submitExercise(current)}
                  className="vsc-btn vsc-btn-primary flex items-center gap-1">
                  <Send size={12} /> Test prompt
                </button>
                <button type="button"
                  onClick={() => setDrafts((p) => ({ ...p, [current.id]: current.starter || '' }))}
                  className="vsc-btn flex items-center gap-1">
                  <RotateCcw size={12} /> Reset
                </button>
              </div>
            )}
            editor={current ? (
              <div className="h-full min-h-0 flex flex-col">
                <textarea
                  value={currentDraft}
                  onChange={(e) => setDrafts((p) => ({ ...p, [current.id]: e.target.value }))}
                  placeholder="Write your prompt here…"
                  spellCheck={false}
                  className={`${promptTextareaClass} flex-1`}
                />
              </div>
            ) : (
              <div className="p-4 text-sm text-[var(--vsc-muted)]">Select an exercise from the sidebar.</div>
            )}
            bottomPanel={{
              height: 240,
              tabs: (
                <>
                  <VscPanelTab active={exPanelTab === 'output'} onClick={() => setExPanelTab('output')}>Output</VscPanelTab>
                  <VscPanelTab active={exPanelTab === 'quality'} onClick={() => setExPanelTab('quality')}>Quality</VscPanelTab>
                </>
              ),
              content: exPanelTab === 'quality' ? (
                <QualityMeter analysis={currentAnalysis} />
              ) : currentResult ? (
                <div className="space-y-2 text-sm">
                  <div className={`rounded border p-2.5 ${currentResult.passed ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-amber-500/30 bg-amber-500/5'}`}>
                    <div className="flex items-center gap-1.5 mb-1 text-[10px] font-semibold uppercase tracking-wide text-[var(--vsc-muted)]">
                      <Bot size={12} /> Practice assistant
                    </div>
                    <p className="text-[var(--vsc-text)] whitespace-pre-wrap leading-relaxed">
                      {replyForExercise(current, currentResult)}
                    </p>
                  </div>
                  {currentResult.passed ? (
                    <p className="text-xs text-emerald-400 flex items-center gap-1.5">
                      <CheckCircle2 size={12} /> Exercise cleared — meets every requirement.
                    </p>
                  ) : (
                    <ul className="space-y-1 text-xs text-[var(--vsc-text)]">
                      {currentResult.missing.map((m, i) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <XCircle size={10} className="text-red-400 mt-0.5 shrink-0" /> {m}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : (
                <p className="text-xs text-[var(--vsc-muted)]">Run <strong>Test prompt</strong> to see the practice assistant reply and checklist.</p>
              ),
            }}
            rightPanel={{
              width: 280,
              header: 'Brief',
              content: current ? (
                <div className="space-y-3 text-sm">
                  <div>
                    <h3 className="font-semibold text-[var(--vsc-text)] flex items-center gap-1.5 mb-1">
                      <Target size={13} className="text-cyan-400" /> {current.title}
                    </h3>
                    <p className="text-[var(--vsc-muted)] leading-relaxed text-xs">{current.goal}</p>
                  </div>
                  {current.hints?.length > 0 && (
                    <div className="rounded border border-amber-500/20 bg-amber-500/5 p-2.5">
                      <p className="text-[10px] font-semibold text-amber-400 mb-1 flex items-center gap-1">
                        <Lightbulb size={11} /> Hints
                      </p>
                      <ul className="text-xs text-[var(--vsc-muted)] space-y-1">
                        {current.hints.map((h, i) => <li key={i}>• {h}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              ) : null,
            }}
            statusBar={{
              left: `${passedCount}/${exercises.length} exercises passed`,
              center: current ? `${currentAnalysis.words} words` : '',
              right: current ? `Quality ${currentAnalysis.score}/100` : '',
            }}
          />
        )}

        {/* ── Lesson tab ── */}
        {tab === 'lesson' && (
          <div className="h-full overflow-y-auto p-4 sm:p-6 max-w-3xl mx-auto space-y-5">
            <div>
              <h2 className="text-lg font-bold text-surface-100">{scenario?.title || 'Lesson'}</h2>
              {scenario?.description && (
                <p className="text-sm text-surface-400 mt-1.5 leading-relaxed">{scenario.description}</p>
              )}
            </div>
            {lessons.map((sec, i) => (
              <div key={i} className="glass-card p-4">
                <h3 className="text-sm font-semibold text-accent-cyan flex items-center gap-1.5 mb-2">
                  <ChevronRight size={14} /> {sec.heading}
                </h3>
                <p className="text-sm text-surface-300 leading-relaxed whitespace-pre-wrap">{sec.body}</p>
              </div>
            ))}
            <div className="rounded-lg border border-accent-amber/20 bg-accent-amber/5 p-3 flex items-start gap-2">
              <Lightbulb size={14} className="text-accent-amber mt-0.5 shrink-0" />
              <p className="text-xs text-surface-400">
                Head to the <button onClick={() => setTab('exercises')} className="text-accent-cyan font-medium hover:underline">Exercises</button> tab to practice, or try anything in <button onClick={() => setTab('sandbox')} className="text-accent-cyan font-medium hover:underline">Free Practice</button>.
              </p>
            </div>
          </div>
        )}

        {/* ── Free Practice (sandbox chat) tab ── */}
        {tab === 'sandbox' && (
          <VsCodeWorkbench
            theme="app"
            accent="#a78bfa"
            className="h-full"
            title="Free Practice"
            subtitle="Rule-based chat — no live model"
            editorTabs={<VscEditorTab active>prompt.txt</VscEditorTab>}
            editorToolbar={(
              <div className="flex items-center gap-2 w-full">
                <button type="button" onClick={sendSandbox} disabled={!sandboxInput.trim()}
                  className="vsc-btn vsc-btn-primary flex items-center gap-1 disabled:opacity-40">
                  <Send size={12} /> Send (⌘↵)
                </button>
              </div>
            )}
            editor={(
              <div className="h-full min-h-0 flex flex-col">
                <textarea
                  value={sandboxInput}
                  onChange={(e) => setSandboxInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); sendSandbox() }
                  }}
                  placeholder="Write a prompt… (Cmd/Ctrl+Enter to send)"
                  spellCheck={false}
                  className={`${promptTextareaClass} flex-1`}
                />
              </div>
            )}
            bottomPanel={{
              height: 280,
              tabs: (
                <>
                  <VscPanelTab active={sandboxPanelTab === 'chat'} onClick={() => setSandboxPanelTab('chat')}>Chat</VscPanelTab>
                  <VscPanelTab active={sandboxPanelTab === 'quality'} onClick={() => setSandboxPanelTab('quality')}>Quality</VscPanelTab>
                </>
              ),
              content: sandboxPanelTab === 'quality' ? (
                <QualityMeter analysis={analyzePrompt(sandboxInput)} />
              ) : (
                <div className="space-y-3 overflow-y-auto max-h-full pr-1">
                  {chat.length === 0 && (
                    <p className="text-xs text-[var(--vsc-muted)] py-4 text-center">
                      Send a prompt to start a rule-based conversation. Nothing here is graded.
                    </p>
                  )}
                  {chat.map((msg, i) => (
                    <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      {msg.role === 'assistant' && (
                        <div className="w-6 h-6 shrink-0 rounded bg-purple-500/15 flex items-center justify-center">
                          <Bot size={12} className="text-purple-400" />
                        </div>
                      )}
                      <div className={`max-w-[85%] rounded px-2.5 py-2 text-xs leading-relaxed whitespace-pre-wrap ${
                        msg.role === 'user'
                          ? 'bg-cyan-500/15 text-[var(--vsc-text)]'
                          : 'bg-[var(--vsc-tab)] text-[var(--vsc-text)]'
                      }`}>
                        {msg.text}
                        {msg.role === 'assistant' && msg.analysis && (
                          <div className={`mt-1 text-[10px] font-mono ${scoreColor(msg.analysis.score)}`}>
                            prompt scored {msg.analysis.score}/100
                          </div>
                        )}
                      </div>
                      {msg.role === 'user' && (
                        <div className="w-6 h-6 shrink-0 rounded bg-cyan-500/15 flex items-center justify-center">
                          <User size={12} className="text-cyan-400" />
                        </div>
                      )}
                    </div>
                  ))}
                  <div ref={chatEndRef} />
                </div>
              ),
            }}
            statusBar={{
              left: `${chat.length} messages`,
              right: sandboxInput.trim() ? `Quality ${analyzePrompt(sandboxInput).score}/100` : 'Ready',
            }}
          />
        )}
      </div>
    </div>
  )
}
