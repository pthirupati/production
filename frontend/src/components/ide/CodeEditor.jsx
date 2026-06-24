import { useEffect, useRef, useImperativeHandle, forwardRef } from 'react'
import { EditorState, Compartment } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { indentUnit, indentOnInput, bracketMatching, foldGutter } from '@codemirror/language'
import { searchKeymap, highlightSelectionMatches, openSearchPanel } from '@codemirror/search'
import { autocompletion, completeFromList } from '@codemirror/autocomplete'
import { linter, lintGutter } from '@codemirror/lint'
import { vim, Vim } from '@replit/codemirror-vim'
import { python } from '@codemirror/lang-python'
import { javascript } from '@codemirror/lang-javascript'
import { json } from '@codemirror/lang-json'
import { yaml } from '@codemirror/lang-yaml'
import { markdown } from '@codemirror/lang-markdown'
import { oneDark } from '@codemirror/theme-one-dark'
import { useThemeStore } from '../../store/themeStore'

function languageExtension(language) {
  const lang = (language || '').toLowerCase()
  if (lang === 'python' || lang === 'py') return python()
  if (['javascript', 'js', 'node', 'nodejs'].includes(lang)) return javascript()
  if (['typescript', 'ts'].includes(lang)) return javascript({ typescript: true })
  if (lang === 'jsx') return javascript({ jsx: true })
  if (lang === 'tsx') return javascript({ jsx: true, typescript: true })
  if (lang === 'json') return json()
  if (lang === 'yaml' || lang === 'yml') return yaml()
  if (lang === 'markdown' || lang === 'md') return markdown()
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

function autocompleteFor(language) {
  const lang = (language || '').toLowerCase()
  if (lang === 'python' || lang === 'py') return [autocompletion({ override: [PYTHON_KW] })]
  if (['javascript', 'js', 'typescript', 'ts', 'jsx', 'tsx', 'node', 'nodejs'].includes(lang)) {
    return [autocompletion({ override: [JS_KW] })]
  }
  return [autocompletion()]
}

function basicLinter(language) {
  return linter((view) => {
    const text = view.state.doc.toString()
    const diags = []
    const lines = text.split('\n')
    const lang = (language || '').toLowerCase()
    const paren = (text.match(/\(/g) || []).length - (text.match(/\)/g) || []).length
    const brace = (text.match(/\{/g) || []).length - (text.match(/\}/g) || []).length
    if (paren !== 0) {
      diags.push({ from: 0, to: Math.min(1, text.length), severity: 'warning', message: 'Unbalanced parentheses' })
    }
    if (brace !== 0) {
      diags.push({ from: 0, to: Math.min(1, text.length), severity: 'warning', message: 'Unbalanced braces' })
    }
    lines.forEach((line, i) => {
      const pos = lines.slice(0, i).join('\n').length + (i > 0 ? 1 : 0)
      if (lang === 'python' || lang === 'py') {
        if (/\t/.test(line)) {
          diags.push({ from: pos, to: pos + line.length, severity: 'warning', message: 'Use spaces instead of tabs (PEP 8)' })
        }
        if (/^\s+[^\s#]/.test(line) && line.trimEnd().endsWith(':') === false) {
          const prev = lines[i - 1] || ''
          if (/:\s*$/.test(prev) && line.search(/^\s{1,3}[^ ]/) >= 0 && !line.startsWith('    ')) {
            diags.push({ from: pos, to: pos + line.length, severity: 'error', message: 'Expected 4-space indent after block' })
          }
        }
      }
      if (['javascript', 'js', 'typescript', 'ts'].includes(lang) && /console\.log\(/.test(line)) {
        diags.push({ from: pos, to: pos + line.length, severity: 'info', message: 'Remove debug console.log before submit' })
      }
    })
    return diags
  })
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
  { value = '', onChange, language = 'python', readOnly = false, onRun, fontSize = 13, vimMode = false, formatOnSave = false },
  ref,
) {
  const hostRef = useRef(null)
  const viewRef = useRef(null)
  const onChangeRef = useRef(onChange)
  const onRunRef = useRef(onRun)
  const langCompartment = useRef(new Compartment())
  const autocompleteCompartment = useRef(new Compartment())
  const themeCompartment = useRef(new Compartment())
  const readOnlyCompartment = useRef(new Compartment())
  const fontCompartment = useRef(new Compartment())
  const vimCompartment = useRef(new Compartment())
  const lintCompartment = useRef(new Compartment())

  const theme = useThemeStore((s) => s.theme)
  const isDark = theme !== 'light'

  useImperativeHandle(ref, () => ({
    openSearch: () => { const v = viewRef.current; if (v) { openSearchPanel(v); v.focus() } },
    focus: () => viewRef.current?.focus(),
    formatDocument: () => {
      const view = viewRef.current
      if (!view) return
      const lines = view.state.doc.toString().split('\n')
      const formatted = lines.map((l) => {
        const t = l.trimStart()
        if (!t) return ''
        const depth = Math.floor((l.length - t.length) / 4)
        return '    '.repeat(depth) + t
      }).join('\n')
      const cur = view.state.doc.toString()
      if (formatted !== cur) {
        view.dispatch({ changes: { from: 0, to: cur.length, insert: formatted } })
      }
    },
  }), [])

  const fontTheme = (px) => EditorView.theme({
    '&': { height: '100%', fontSize: `${px}px` },
    '.cm-scroller': { fontFamily: '"JetBrains Mono", monospace' },
  })

  useEffect(() => { onChangeRef.current = onChange }, [onChange])
  useEffect(() => { onRunRef.current = onRun }, [onRun])

  useEffect(() => {
    if (!hostRef.current) return

    const runKeymap = keymap.of([
      { key: 'Mod-Enter', run: () => { onRunRef.current?.(); return true } },
      {
        key: 'Mod-Shift-f',
        run: (view) => {
          const lines = view.state.doc.toString().split('\n')
          const formatted = lines.map((l) => {
            const t = l.trimStart()
            if (!t) return ''
            const depth = Math.floor((l.length - t.length) / 4)
            return '    '.repeat(depth) + t
          }).join('\n')
          const cur = view.state.doc.toString()
          if (formatted !== cur) view.dispatch({ changes: { from: 0, to: cur.length, insert: formatted } })
          return true
        },
      },
    ])

    const updateListener = EditorView.updateListener.of((update) => {
      if (update.docChanged) {
        onChangeRef.current?.(update.state.doc.toString())
      }
    })

    const state = EditorState.create({
      doc: value,
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
        runKeymap,
        keymap.of([indentWithTab, ...searchKeymap, ...defaultKeymap, ...historyKeymap]),
        langCompartment.current.of(languageExtension(language)),
        autocompleteCompartment.current.of(autocompleteFor(language)),
        lintCompartment.current.of([lintGutter(), basicLinter(language)]),
        vimCompartment.current.of(vimMode ? vim() : []),
        themeCompartment.current.of(isDark ? oneDark : lightTheme),
        readOnlyCompartment.current.of(EditorState.readOnly.of(readOnly)),
        fontCompartment.current.of(fontTheme(fontSize)),
        updateListener,
        EditorView.lineWrapping,
      ],
    })

    const view = new EditorView({ state, parent: hostRef.current })
    viewRef.current = view
    return () => { view.destroy(); viewRef.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const view = viewRef.current
    if (!view) return
    const current = view.state.doc.toString()
    if (value !== current) {
      view.dispatch({ changes: { from: 0, to: current.length, insert: value } })
    }
  }, [value])

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
  }, [fontSize])

  useEffect(() => {
    viewRef.current?.dispatch({ effects: vimCompartment.current.reconfigure(vimMode ? vim() : []) })
    if (vimMode) Vim.map('jj', '<Esc>', 'insert')
  }, [vimMode])

  useEffect(() => {
    if (!formatOnSave) return undefined
    const formatDoc = () => {
      const view = viewRef.current
      if (!view) return
      const lines = view.state.doc.toString().split('\n')
      const formatted = lines.map((l) => {
        const t = l.trimStart()
        if (!t) return ''
        const depth = Math.floor((l.length - t.length) / 4)
        return '    '.repeat(depth) + t
      }).join('\n')
      const cur = view.state.doc.toString()
      if (formatted !== cur) view.dispatch({ changes: { from: 0, to: cur.length, insert: formatted } })
    }
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        formatDoc()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [formatOnSave])

  return <div ref={hostRef} className="h-full w-full overflow-hidden text-left" />
})

export default CodeEditor
