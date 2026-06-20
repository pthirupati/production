import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import {
  Sparkles, Send, CheckCircle2, XCircle, Lightbulb, Target, BookOpen,
  Bot, User, Trophy, RotateCcw, ChevronRight, Gauge, Loader2,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { labApi } from '../../api/labs'

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
const ROLE_HINTS = ['you are', 'act as', "you're a", 'you are a', 'as a ', 'imagine you', 'pretend you', 'your role', 'role:', 'persona', 'system prompt']
const LIMIT_HINTS = ['word', 'words', 'sentence', 'sentences', 'bullet', 'bullets', 'paragraph', 'characters', 'chars', 'under ', 'at most', 'no more than', 'max ', 'maximum', 'limit', 'concise', 'brief', 'short', 'one line', 'tl;dr', 'in 1', 'in 2', 'in 3', 'exactly']
const EXAMPLE_HINTS = ['example', 'e.g.', 'for instance', 'such as', 'like this', '->', 'sample']
const FORMAT_HINTS = ['json', 'bullet', 'list', 'table', 'numbered', 'paragraph', 'yaml', 'csv', 'markdown', 'one word', 'one sentence', 'format', 'steps']
const CONTEXT_HINTS = ['context', 'given', 'based on', 'using the', 'from the', 'here is', 'here are', 'the following', 'according to', '"""', '```', '<document>']
const DELIMITER_HINTS = ['"""', '```', '<document>', '</document>', '<context>', '<<<', '###', "'''"]
const CONTRADICTIONS = [['one sentence', 'paragraph'], ['one sentence', 'multi-paragraph'], ['single sentence', 'detailed'], ['brief', 'comprehensive'], ['one word', 'explain in detail']]

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

/** Score a prompt on the five ingredients — used for the live quality meter. */
function analyzePrompt(raw) {
  const text = (raw || '').trim().toLowerCase()
  const words = text ? text.split(/\s+/).length : 0
  const checks = [
    { key: 'role', label: 'Role / persona', ok: hasAny(text, ROLE_HINTS), tip: 'Tell the AI who to be ("You are a…").' },
    { key: 'context', label: 'Context', ok: hasAny(text, CONTEXT_HINTS) || words > 25, tip: 'Give the background or material it needs.' },
    { key: 'task', label: 'Clear task', ok: words >= 6, tip: 'State the specific task with an action verb.' },
    { key: 'constraints', label: 'Constraints', ok: hasAny(text, LIMIT_HINTS), tip: 'Add a length, tone, or "what to avoid".' },
    { key: 'format', label: 'Output format', ok: hasAny(text, FORMAT_HINTS), tip: 'Ask for bullets, JSON, a table, etc.' },
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

  if (s.min_words != null) mark(words >= s.min_words, 'enough detail')
  if (s.max_words != null) mark(words <= s.max_words, 'concise enough')
  if (s.require_any_role) mark(hasAny(text, ROLE_HINTS), 'assigns a role')
  if (s.mentions_limit) mark(hasAny(text, LIMIT_HINTS), 'states a length/format limit')
  if (s.mentions_example) mark(hasAny(text, EXAMPLE_HINTS), 'includes an example')
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

  return (
    <div className="flex-1 min-h-0 flex flex-col bg-surface-950 text-surface-200">
      {/* Free-practice honesty banner */}
      <div className="shrink-0 px-4 py-2 bg-accent-purple/10 border-b border-accent-purple/20 flex items-center gap-2 text-[11px] text-surface-300">
        <Sparkles size={12} className="text-accent-purple shrink-0" />
        <span>
          Guided <strong className="text-surface-200">AI practice simulator</strong> — replies and scoring are rule-based and 100% free (no live model). Focus on writing great prompts.
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
          <div className="h-full flex flex-col md:flex-row min-h-0">
            {/* Exercise list */}
            <div className="md:w-56 shrink-0 border-b md:border-b-0 md:border-r border-surface-800 overflow-y-auto bg-surface-900/40">
              {exercises.map((ex, i) => {
                const r = results[ex.id]
                return (
                  <button
                    key={ex.id}
                    onClick={() => setActiveEx(i)}
                    className={`w-full text-left px-3 py-2.5 flex items-start gap-2 border-l-2 transition-colors ${
                      i === activeEx ? 'border-accent-cyan bg-surface-800/60' : 'border-transparent hover:bg-surface-800/30'
                    }`}
                  >
                    {r?.passed ? (
                      <CheckCircle2 size={14} className="text-accent-green mt-0.5 shrink-0" />
                    ) : (
                      <Target size={14} className="text-surface-500 mt-0.5 shrink-0" />
                    )}
                    <span className={`text-xs ${i === activeEx ? 'text-surface-100 font-medium' : 'text-surface-400'}`}>
                      {ex.title}
                    </span>
                  </button>
                )
              })}
            </div>

            {/* Active exercise */}
            {current && (
              <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
                <div>
                  <h3 className="text-sm font-bold text-surface-100 flex items-center gap-2">
                    <Target size={14} className="text-accent-cyan" /> {current.title}
                  </h3>
                  <p className="text-sm text-surface-400 mt-1.5 leading-relaxed">{current.goal}</p>
                </div>

                <textarea
                  value={drafts[current.id] ?? ''}
                  onChange={(e) => setDrafts((p) => ({ ...p, [current.id]: e.target.value }))}
                  placeholder="Write your prompt here…"
                  rows={6}
                  className="w-full rounded-lg bg-surface-900 border border-surface-700 focus:border-accent-cyan focus:outline-none text-sm text-surface-100 p-3 font-mono leading-relaxed resize-y"
                />

                <QualityMeter analysis={analyzePrompt(drafts[current.id] || '')} />

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => submitExercise(current)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold border border-accent-cyan/40 text-accent-cyan bg-accent-cyan/10 hover:bg-accent-cyan/20"
                  >
                    <Send size={12} /> Test prompt
                  </button>
                  <button
                    onClick={() => setDrafts((p) => ({ ...p, [current.id]: current.starter || '' }))}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-surface-700 text-surface-400 hover:text-surface-200"
                  >
                    <RotateCcw size={12} /> Reset
                  </button>
                </div>

                {/* Result: simulated reply + checklist */}
                {currentResult && (
                  <div className="space-y-3 pt-1">
                    <div className={`rounded-lg border p-3 ${currentResult.passed ? 'border-accent-green/30 bg-accent-green/5' : 'border-accent-amber/30 bg-accent-amber/5'}`}>
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <Bot size={13} className={currentResult.passed ? 'text-accent-green' : 'text-accent-amber'} />
                        <span className="text-[11px] font-semibold uppercase tracking-wide text-surface-400">Simulated assistant</span>
                      </div>
                      <p className="text-sm text-surface-200 whitespace-pre-wrap leading-relaxed">
                        {replyForExercise(current, currentResult)}
                      </p>
                    </div>

                    {currentResult.passed ? (
                      <p className="text-xs text-accent-green font-medium flex items-center gap-1.5">
                        <CheckCircle2 size={13} /> Exercise cleared — this prompt meets every requirement.
                      </p>
                    ) : (
                      <div className="rounded-lg border border-surface-700/60 bg-surface-900/60 p-3">
                        <p className="text-[11px] font-semibold text-surface-400 mb-1.5">Still missing:</p>
                        <ul className="space-y-1">
                          {currentResult.missing.map((m, i) => (
                            <li key={i} className="flex items-start gap-1.5 text-xs text-surface-300">
                              <XCircle size={11} className="text-accent-red mt-0.5 shrink-0" /> {m}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
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
          <div className="h-full flex flex-col min-h-0">
            <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
              {chat.length === 0 && (
                <div className="text-center py-10 max-w-md mx-auto">
                  <Bot size={28} className="text-surface-600 mx-auto mb-3" />
                  <p className="text-sm text-surface-400">
                    Write any prompt and get a rule-based reply plus a live quality score. Experiment freely — nothing here is graded.
                  </p>
                </div>
              )}
              {chat.map((msg, i) => (
                <div key={i} className={`flex gap-2.5 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {msg.role === 'assistant' && (
                    <div className="w-7 h-7 shrink-0 rounded-md bg-accent-purple/15 border border-accent-purple/30 flex items-center justify-center">
                      <Bot size={14} className="text-accent-purple" />
                    </div>
                  )}
                  <div className={`max-w-[75%] ${msg.role === 'user' ? 'order-1' : ''}`}>
                    <div className={`rounded-lg px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap ${
                      msg.role === 'user'
                        ? 'bg-accent-cyan/15 border border-accent-cyan/25 text-surface-100'
                        : 'bg-surface-800/70 border border-surface-700 text-surface-200'
                    }`}>
                      {msg.text}
                    </div>
                    {msg.role === 'user' && msg.analysis == null && null}
                    {msg.role === 'assistant' && msg.analysis && (
                      <div className="mt-1.5">
                        <span className={`text-[10px] font-mono ${scoreColor(msg.analysis.score)}`}>
                          your prompt scored {msg.analysis.score}/100
                        </span>
                      </div>
                    )}
                  </div>
                  {msg.role === 'user' && (
                    <div className="w-7 h-7 shrink-0 rounded-md bg-accent-cyan/15 border border-accent-cyan/30 flex items-center justify-center order-2">
                      <User size={14} className="text-accent-cyan" />
                    </div>
                  )}
                </div>
              ))}
              <div ref={chatEndRef} />
            </div>
            <div className="shrink-0 border-t border-surface-800 p-3 bg-surface-900/60">
              <div className="flex items-end gap-2">
                <textarea
                  value={sandboxInput}
                  onChange={(e) => setSandboxInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); sendSandbox() }
                  }}
                  placeholder="Write a prompt… (Cmd/Ctrl+Enter to send)"
                  rows={2}
                  className="flex-1 rounded-lg bg-surface-900 border border-surface-700 focus:border-accent-cyan focus:outline-none text-sm text-surface-100 p-2.5 font-mono resize-none"
                />
                <button
                  onClick={sendSandbox}
                  disabled={!sandboxInput.trim()}
                  className="h-10 px-3 rounded-lg bg-accent-cyan text-surface-950 font-semibold flex items-center gap-1.5 text-sm disabled:opacity-50"
                >
                  <Send size={14} /> Send
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
