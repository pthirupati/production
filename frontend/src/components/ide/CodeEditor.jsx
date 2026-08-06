import { useEffect, useRef, useImperativeHandle, forwardRef } from 'react'
import { EditorState, Compartment } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { indentUnit, indentOnInput, bracketMatching, foldGutter, StreamLanguage } from '@codemirror/language'
import { searchKeymap, highlightSelectionMatches, openSearchPanel } from '@codemirror/search'
import { autocompletion, completeFromList } from '@codemirror/autocomplete'
import { linter, lintGutter } from '@codemirror/lint'
import { vim, Vim } from '@replit/codemirror-vim'
import { python } from '@codemirror/lang-python'
import { javascript } from '@codemirror/lang-javascript'
import { json } from '@codemirror/lang-json'
import { yaml } from '@codemirror/lang-yaml'
import { markdown } from '@codemirror/lang-markdown'
import { html } from '@codemirror/lang-html'
import { css } from '@codemirror/lang-css'
// Real CodeMirror 5 modes for java/shell. @codemirror/legacy-modes was already a
// dependency, and there is no lezer grammar for either in the tree, so these give
// us proper tokenizers (string escapes, heredocs, annotations, generics) without
// pulling in @codemirror/lang-java.
import { java as javaMode } from '@codemirror/legacy-modes/mode/clike'
import { shell as shellMode } from '@codemirror/legacy-modes/mode/shell'
import { oneDark } from '@codemirror/theme-one-dark'
import { useThemeStore } from '../../store/themeStore'

const hclLanguage = StreamLanguage.define({
  startState: () => ({}),
  token(stream) {
    if (stream.eatSpace()) return null
    if (stream.match('//') || stream.match('#')) {
      stream.skipToEnd()
      return 'comment'
    }
    if (stream.match('/*')) {
      stream.eatWhile((ch) => ch !== '*' || stream.peek() !== '/')
      stream.match('*/', false)
      stream.match('*/')
      return 'comment'
    }
    if (stream.match(/"(?:[^\\"]|\\.)*"/)) return 'string'
    if (stream.match(/\b(resource|variable|output|provider|terraform|module|data|locals|required_providers|backend)\b/)) {
      return 'keyword'
    }
    if (stream.match(/\b(true|false|null)\b/)) return 'atom'
    if (stream.match(/[a-zA-Z_][\w-]*/)) return 'variable'
    stream.next()
    return null
  },
})

// HTML/CSS/Java/Shell used to be ~20-line hand-rolled StreamLanguage regex
// tokenizers. The HTML one in particular never switched sub-modes, so CSS inside
// <style> and JS inside <script> rendered completely unhighlighted. lang-html and
// lang-css were already in the dependency tree (lang-markdown depends on both), so
// using the real lezer grammars costs no additional bundle weight and gives us
// correct nesting plus tag/property autocompletion for free.
const javaLanguage = StreamLanguage.define(javaMode)
const shellLanguage = StreamLanguage.define(shellMode)

export function languageExtension(language) {
  const lang = (language || '').toLowerCase()
  if (lang === 'python' || lang === 'py') return python()
  if (['javascript', 'js', 'node', 'nodejs'].includes(lang)) return javascript()
  if (['typescript', 'ts'].includes(lang)) return javascript({ typescript: true })
  if (lang === 'jsx') return javascript({ jsx: true })
  if (lang === 'tsx') return javascript({ jsx: true, typescript: true })
  if (lang === 'json') return json()
  if (lang === 'yaml' || lang === 'yml') return yaml()
  if (lang === 'hcl' || lang === 'terraform' || lang === 'tf') return hclLanguage
  if (lang === 'markdown' || lang === 'md') return markdown()
  if (lang === 'html' || lang === 'htm') return html()
  if (lang === 'css') return css()
  if (lang === 'java') return javaLanguage
  if (['shell', 'bash', 'sh', 'zsh'].includes(lang)) return shellLanguage
  return []
}


const PYTHON_KW = completeFromList([
  'def', 'class', 'import', 'from', 'return', 'if', 'elif', 'else', 'for', 'while',
  'try', 'except', 'finally', 'with', 'as', 'pass', 'break', 'continue', 'raise',
  'True', 'False', 'None', 'and', 'or', 'not', 'in', 'is', 'lambda', 'yield',
  'print', 'len', 'range', 'list', 'dict', 'set', 'tuple', 'str', 'int', 'float',
])

const JS_KW = completeFromList([
  'function', 'const', 'let', 'var', 'return', 'if', 'else', 'for', 'while',
  'try', 'catch', 'finally', 'class', 'extends', 'import', 'export', 'from',
  'async', 'await', 'new', 'this', 'true', 'false', 'null', 'undefined',
  'console', 'JSON', 'Array', 'Object', 'String', 'Number', 'Promise',
])

const JAVA_KW = completeFromList([
  'public', 'private', 'protected', 'class', 'interface', 'enum', 'record',
  'extends', 'implements', 'static', 'final', 'abstract', 'void', 'return',
  'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'default', 'break',
  'continue', 'new', 'import', 'package', 'try', 'catch', 'finally', 'throw',
  'throws', 'this', 'super', 'null', 'true', 'false', 'instanceof',
  'int', 'long', 'double', 'float', 'boolean', 'char', 'byte', 'short',
  'String', 'System', 'List', 'Map', 'ArrayList', 'HashMap', 'Exception',
])

const SHELL_KW = completeFromList([
  'if', 'then', 'else', 'elif', 'fi', 'for', 'in', 'while', 'until', 'do',
  'done', 'case', 'esac', 'function', 'return', 'exit', 'break', 'continue',
  'export', 'source', 'local', 'readonly', 'declare', 'set', 'unset', 'shift',
  'trap', 'eval', 'exec', 'echo', 'printf', 'read', 'cd', 'pwd', 'ls', 'cat',
  'grep', 'sed', 'awk', 'find', 'xargs', 'chmod', 'chown', 'mkdir', 'rm', 'cp',
  'mv', 'test', 'sleep', 'curl', 'tar', 'sudo',
])

/**
 * Keyword completion sources for languages whose grammar ships none.
 *
 * Returns null when the grammar provides its own: lang-html and lang-css register
 * real tag, attribute and property completions through languageData, and an
 * `override` would throw those away in favour of a worse hardcoded list. Split out
 * from autocompleteFor so the per-language source set is directly assertable —
 * autocompletion()'s resolved config is not reachable from outside CodeMirror.
 */
export function completionSourcesFor(language) {
  const lang = (language || '').toLowerCase()
  if (lang === 'python' || lang === 'py') return [PYTHON_KW]
  if (['javascript', 'js', 'typescript', 'ts', 'jsx', 'tsx', 'node', 'nodejs'].includes(lang)) {
    return [JS_KW]
  }
  if (lang === 'java') return [JAVA_KW]
  if (['shell', 'bash', 'sh', 'zsh'].includes(lang)) return [SHELL_KW]
  return null
}

export function autocompleteFor(language) {
  const override = completionSourcesFor(language)
  return [override ? autocompletion({ override }) : autocompletion()]
}

const PY_LANGS = ['python', 'py']
const JS_LANGS = ['javascript', 'js', 'typescript', 'ts', 'jsx', 'tsx', 'node', 'nodejs']

/**
 * Scan brackets while skipping strings and comments.
 *
 * The previous version counted `(` / `{` over the raw document with a regex, so
 * any paren inside a string or comment — `print("costs $5 (approx)")` — reported
 * "Unbalanced parentheses" on correct code. Diagnostics that cry wolf on valid
 * work are worse than none, so we run a small character scanner instead. This is
 * still not a parser; it is deliberately conservative and only reports a bracket
 * that is genuinely unclosed/unopened outside of string and comment context.
 *
 * Returns [{ pos, message }] where pos is a document offset.
 */
export function findBracketProblems(src, language = '') {
  const text = String(src ?? '')
  const lang = (language || '').toLowerCase()
  const isPy = PY_LANGS.includes(lang)
  const hashComments = isPy || ['shell', 'bash', 'sh', 'zsh', 'yaml', 'yml'].includes(lang)
  const slashComments = !isPy
  const PAIRS = { ')': '(', ']': '[', '}': '{' }
  const OPENERS = '([{'
  const NAMES = { '(': 'parenthesis', '[': 'bracket', '{': 'brace' }

  const stack = []
  const problems = []
  let i = 0
  while (i < text.length) {
    const ch = text[i]

    // Python triple-quoted strings must be checked before single quotes.
    if (isPy && (text.startsWith('"""', i) || text.startsWith("'''", i))) {
      const q = text.slice(i, i + 3)
      const end = text.indexOf(q, i + 3)
      i = end === -1 ? text.length : end + 3
      continue
    }
    if (ch === '"' || ch === "'" || (!isPy && ch === '`')) {
      i += 1
      while (i < text.length && text[i] !== ch) {
        if (text[i] === '\\') i += 1  // escape: skip the escaped char
        i += 1
      }
      i += 1
      continue
    }
    if (hashComments && ch === '#') {
      const nl = text.indexOf('\n', i)
      i = nl === -1 ? text.length : nl
      continue
    }
    if (slashComments && text.startsWith('//', i)) {
      const nl = text.indexOf('\n', i)
      i = nl === -1 ? text.length : nl
      continue
    }
    if (slashComments && text.startsWith('/*', i)) {
      const end = text.indexOf('*/', i + 2)
      i = end === -1 ? text.length : end + 2
      continue
    }

    if (OPENERS.includes(ch)) {
      stack.push({ ch, pos: i })
    } else if (PAIRS[ch]) {
      const top = stack[stack.length - 1]
      if (!top || top.ch !== PAIRS[ch]) {
        problems.push({ pos: i, message: `Unmatched closing ${NAMES[PAIRS[ch]]} '${ch}'` })
      } else {
        stack.pop()
      }
    }
    i += 1
  }

  stack.forEach(({ ch, pos }) => {
    problems.push({ pos, message: `Unclosed ${NAMES[ch]} '${ch}'` })
  })
  return problems.sort((a, b) => a.pos - b.pos)
}

/**
 * Advisory diagnostics for the editor gutter and the Problems panel.
 *
 * Purely advisory by design: grading is server-side (CodingIDE handleCheck), and
 * nothing here may ever gate Check Solution.
 */
export function computeDiagnostics(src, language = '') {
  const text = String(src ?? '')
  const lang = (language || '').toLowerCase()
  const diags = findBracketProblems(text, lang).map(({ pos, message }) => ({
    from: pos,
    to: Math.min(pos + 1, text.length),
    severity: 'warning',
    message,
  }))

  const lines = text.split('\n')
  let pos = 0
  lines.forEach((line) => {
    const lineStart = pos
    pos += line.length + 1  // running offset — the old code re-joined the prefix per line (O(n²))
    if (PY_LANGS.includes(lang) && /^\s*\t/.test(line)) {
      diags.push({
        from: lineStart,
        to: lineStart + line.length,
        severity: 'warning',
        message: 'Use spaces instead of tabs (PEP 8)',
      })
    }
    if (JS_LANGS.includes(lang) && /\bconsole\.log\(/.test(line)) {
      diags.push({
        from: lineStart,
        to: lineStart + line.length,
        severity: 'info',
        message: 'Remove debug console.log before submit',
      })
    }
  })

  return diags.sort((a, b) => a.from - b.from)
}

function basicLinter(language) {
  return linter((view) => computeDiagnostics(view.state.doc.toString(), language))
}

/**
 * Whitespace tidy-up that CANNOT change program semantics.
 *
 * The previous implementation re-quantized every line's leading whitespace to a
 * multiple of 4 (`'    '.repeat(Math.floor(indent / 4))`). That is not
 * formatting — on a 3-space-indented Python file it rewrote
 *   def f(x):
 *      if x:          ->  if x:            (dedented to column 0)
 * turning working code into a SyntaxError. Because this ran on save by default,
 * the corrupted buffer was what got autosaved and sent to the grader.
 *
 * Until a real formatter (prettier / black-wasm) is wired in, we only do things
 * that are safe in every language: strip trailing whitespace, normalise line
 * endings, and guarantee a single trailing newline. Leading indentation is left
 * exactly as the learner typed it.
 */
export function tidyWhitespace(src) {
  const text = String(src ?? '').replace(/\r\n?/g, '\n')
  const tidied = text
    .split('\n')
    .map((line) => line.replace(/[ \t]+$/, ''))
    .join('\n')
  if (!tidied.trim()) return tidied
  return tidied.endsWith('\n') ? tidied.replace(/\n+$/, '\n') : `${tidied}\n`
}

/**
 * Resolve the editor's dark/light choice.
 *
 * `editorTheme` is the editor-specific preference ('auto' | 'dark' | 'light') and
 * `appTheme` the global one. 'auto' — and anything unrecognised, including the
 * undefined seen when an older persisted themeStore payload hydrates without the
 * key — follows the app, preserving the previous coupled behaviour.
 */
export function resolveIsDark(editorTheme, appTheme) {
  if (editorTheme === 'dark') return true
  if (editorTheme === 'light') return false
  return appTheme !== 'light'
}

const lightTheme = EditorView.theme({
  '&': { backgroundColor: '#ffffff', color: '#1e293b' },
  '.cm-gutters': { backgroundColor: '#f8fafc', color: '#94a3b8', border: 'none' },
  '.cm-activeLineGutter': { backgroundColor: '#eef2f7' },
  '.cm-activeLine': { backgroundColor: '#f1f5f9' },
  '.cm-content': { caretColor: '#0e7490' },
  '&.cm-focused .cm-cursor': { borderLeftColor: '#0e7490' },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': { backgroundColor: '#cbd5e1' },
}, { dark: false })

const CodeEditor = forwardRef(function CodeEditor(
  {
    value = '', onChange, language = 'python', readOnly = false, onRun, onSave,
    fontSize = 13, vimMode = false, formatOnSave = false, docPath = '',
  },
  ref,
) {
  const hostRef = useRef(null)
  const viewRef = useRef(null)
  // One EditorState per file path. CodingIDE used to force a remount with
  // key={activePath}, which threw away the CodeMirror state — and with it the
  // whole undo/redo history and cursor position — on every tab switch. Keeping
  // the states here lets us swap documents without losing either.
  const docStatesRef = useRef(new Map())
  const currentPathRef = useRef(docPath)
  // Builds a fresh EditorState with the full extension set. Held in a ref so the
  // doc-swap effect can rebuild state for a newly opened path without needing the
  // create-once mount effect to re-run.
  const createStateRef = useRef(null)
  const onChangeRef = useRef(onChange)
  const onRunRef = useRef(onRun)
  const onSaveRef = useRef(onSave)
  const formatOnSaveRef = useRef(formatOnSave)
  const langCompartment = useRef(new Compartment())
  const autocompleteCompartment = useRef(new Compartment())
  const themeCompartment = useRef(new Compartment())
  const readOnlyCompartment = useRef(new Compartment())
  const fontCompartment = useRef(new Compartment())
  const vimCompartment = useRef(new Compartment())
  const keymapCompartment = useRef(new Compartment())
  const lintCompartment = useRef(new Compartment())

  // Editor theme is its own setting rather than a read of the app theme. An
  // `editorTheme` of 'auto' falls back to the app theme — the historical
  // behaviour, and still the default — while 'dark'/'light' pin the editor
  // independently. Both values are subscribed to so an 'auto' editor still
  // re-renders when the global theme is toggled.
  const appTheme = useThemeStore((s) => s.theme)
  const editorTheme = useThemeStore((s) => s.editorTheme)
  const isDark = resolveIsDark(editorTheme, appTheme)

  // Current prop values for createStateRef: view.setState() rebuilds every
  // compartment from the state it is given, so a state built during a doc swap
  // must be configured from today's props, not the ones captured at mount.
  const languageRef = useRef(language)
  const readOnlyRef = useRef(readOnly)
  const fontSizeRef = useRef(fontSize)
  const vimModeRef = useRef(vimMode)
  const isDarkRef = useRef(isDark)
  languageRef.current = language
  readOnlyRef.current = readOnly
  fontSizeRef.current = fontSize
  vimModeRef.current = vimMode
  isDarkRef.current = isDark

  const formatDoc = (view) => {
    if (!view) return
    const cur = view.state.doc.toString()
    const formatted = tidyWhitespace(cur)
    if (formatted !== cur) {
      view.dispatch({ changes: { from: 0, to: cur.length, insert: formatted } })
    }
  }

  useImperativeHandle(ref, () => ({
    openSearch: () => { const v = viewRef.current; if (v) { openSearchPanel(v); v.focus() } },
    focus: () => viewRef.current?.focus(),
    formatDocument: () => formatDoc(viewRef.current),
    getValue: () => viewRef.current?.state.doc.toString() ?? '',
    // The live EditorView. Exposed so callers (and tests) can run CodeMirror
    // commands such as undo against the editor's real state.
    getView: () => viewRef.current,
  }), [])

  const fontTheme = (px) => EditorView.theme({
    '&': { height: '100%', fontSize: `${px}px` },
    '.cm-scroller': { fontFamily: '"JetBrains Mono", "Fira Code", Menlo, monospace' },
    '.cm-vim-panel, .cm-panels.cm-panels-bottom': {
      backgroundColor: isDark ? '#252526' : '#f3f3f3',
      color: isDark ? '#cccccc' : '#333',
      fontFamily: '"JetBrains Mono", monospace',
      fontSize: '12px',
    },
  })

  const editorKeymaps = (useVim) => {
    const base = useVim
      ? [indentWithTab, ...searchKeymap, ...historyKeymap]
      : [indentWithTab, ...searchKeymap, ...defaultKeymap, ...historyKeymap]
    return keymap.of([
      { key: 'Mod-Enter', run: () => { onRunRef.current?.(); return true } },
      {
        key: 'Mod-s',
        run: (view) => {
          if (formatOnSaveRef.current) formatDoc(view)
          onSaveRef.current?.(view.state.doc.toString())
          return true
        },
      },
      {
        key: 'Mod-Shift-f',
        run: (view) => { formatDoc(view); return true },
      },
      ...base,
    ])
  }

  useEffect(() => { onChangeRef.current = onChange }, [onChange])
  useEffect(() => { onRunRef.current = onRun }, [onRun])
  useEffect(() => { onSaveRef.current = onSave }, [onSave])
  useEffect(() => { formatOnSaveRef.current = formatOnSave }, [formatOnSave])

  // Wire Vim :w / :write / :x once — calls the same Save handler as Cmd-S.
  useEffect(() => {
    const saveFromVim = () => {
      const view = viewRef.current
      if (view && formatOnSaveRef.current) formatDoc(view)
      onSaveRef.current?.(view?.state.doc.toString() ?? '')
    }
    try {
      Vim.defineEx('write', 'w', () => { saveFromVim() })
      Vim.defineEx('update', 'up', () => { saveFromVim() })
      Vim.defineEx('xit', 'x', () => { saveFromVim() })
      Vim.map('jj', '<Esc>', 'insert')
    } catch { /* already defined across remounts */ }
  }, [])

  useEffect(() => {
    if (!hostRef.current) return

    const updateListener = EditorView.updateListener.of((update) => {
      if (update.docChanged) {
        onChangeRef.current?.(update.state.doc.toString())
      }
    })

    createStateRef.current = (doc) => EditorState.create({
      doc,
      extensions: [
        lineNumbers(),
        highlightActiveLineGutter(),
        highlightActiveLine(),
        highlightSelectionMatches(),
        foldGutter(),
        history(),
        indentOnInput(),
        bracketMatching(),
        indentUnit.of('    '),
        EditorState.tabSize.of(4),
        // Vim must be early so it owns input before other keymaps.
        vimCompartment.current.of(vimModeRef.current ? vim({ status: true }) : []),
        keymapCompartment.current.of(editorKeymaps(vimModeRef.current)),
        langCompartment.current.of(languageExtension(languageRef.current)),
        autocompleteCompartment.current.of(autocompleteFor(languageRef.current)),
        lintCompartment.current.of([lintGutter(), basicLinter(languageRef.current)]),
        themeCompartment.current.of(isDarkRef.current ? oneDark : lightTheme),
        readOnlyCompartment.current.of(EditorState.readOnly.of(readOnlyRef.current)),
        fontCompartment.current.of(fontTheme(fontSizeRef.current)),
        updateListener,
        EditorView.lineWrapping,
      ],
    })

    const state = createStateRef.current(value)
    docStatesRef.current.set(currentPathRef.current, state)

    const view = new EditorView({ state, parent: hostRef.current })
    viewRef.current = view
    return () => { view.destroy(); viewRef.current = null }
    // Create once — vim/lang/theme reconfigure via compartments below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Swap documents on tab change, preserving each path's undo history.
  //
  // Runs BEFORE the value-sync effect below (declaration order) so the incoming
  // path's state is installed first; otherwise value-sync would write the new
  // file's text into the outgoing file's state and autosave it to the wrong path.
  useEffect(() => {
    const view = viewRef.current
    if (!view) return
    const prevPath = currentPathRef.current
    if (prevPath === docPath) return

    // Stash the outgoing document so returning to it restores history + cursor.
    docStatesRef.current.set(prevPath, view.state)
    currentPathRef.current = docPath

    const saved = docStatesRef.current.get(docPath)
    // Trust `value` over a stale cached state: the file may have been changed
    // outside the editor (draft restore, Refresh, rename) while it sat closed.
    if (saved && saved.doc.toString() === value) {
      view.setState(saved)
    } else {
      const fresh = createStateRef.current?.(value)
      if (fresh) {
        docStatesRef.current.set(docPath, fresh)
        view.setState(fresh)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- value read intentionally, swap is keyed on docPath
  }, [docPath])

  // Toggle Vim without destroying undo history when possible.
  useEffect(() => {
    const view = viewRef.current
    if (!view) return
    try {
      view.dispatch({
        effects: [
          vimCompartment.current.reconfigure(vimMode ? vim({ status: true }) : []),
          keymapCompartment.current.reconfigure(editorKeymaps(vimMode)),
        ],
      })
    } catch {
      /* ignore */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vimMode])

  useEffect(() => {
    const view = viewRef.current
    if (!view) return
    // The doc-swap effect above already installed the right state for this path.
    if (currentPathRef.current !== docPath) return
    const current = view.state.doc.toString()
    if (value !== current) {
      view.dispatch({ changes: { from: 0, to: current.length, insert: value } })
    }
  }, [value, docPath])

  useEffect(() => {
    viewRef.current?.dispatch({
      effects: [
        langCompartment.current.reconfigure(languageExtension(language)),
        autocompleteCompartment.current.reconfigure(autocompleteFor(language)),
        lintCompartment.current.reconfigure([lintGutter(), basicLinter(language)]),
      ],
    })
  }, [language])

  useEffect(() => {
    viewRef.current?.dispatch({ effects: themeCompartment.current.reconfigure(isDark ? oneDark : lightTheme) })
  }, [isDark])

  useEffect(() => {
    viewRef.current?.dispatch({ effects: readOnlyCompartment.current.reconfigure(EditorState.readOnly.of(readOnly)) })
  }, [readOnly])

  useEffect(() => {
    viewRef.current?.dispatch({ effects: fontCompartment.current.reconfigure(fontTheme(fontSize)) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fontSize, isDark])

  return <div ref={hostRef} className="h-full w-full overflow-hidden text-left" />
})

export default CodeEditor
