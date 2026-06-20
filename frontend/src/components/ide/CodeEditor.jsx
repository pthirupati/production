import { useEffect, useRef, useImperativeHandle, forwardRef } from 'react'
import { EditorState, Compartment } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { indentUnit, indentOnInput, bracketMatching, foldGutter } from '@codemirror/language'
import { searchKeymap, highlightSelectionMatches, openSearchPanel } from '@codemirror/search'
import { python } from '@codemirror/lang-python'
import { javascript } from '@codemirror/lang-javascript'
import { json } from '@codemirror/lang-json'
import { yaml } from '@codemirror/lang-yaml'
import { markdown } from '@codemirror/lang-markdown'
import { oneDark } from '@codemirror/theme-one-dark'
import { useThemeStore } from '../../store/themeStore'

/**
 * Map a scenario language to the matching CodeMirror language extension, so the
 * editor gets language-aware syntax highlighting, auto-indent and bracket
 * matching. Unknown languages fall back to plain text (no extension) so the
 * editor never crashes on an unexpected language.
 *
 * TypeScript/JSX/TSX reuse the JS extension (configured for the dialect); JSON
 * also falls back to the JS grammar if the dedicated parser is unavailable.
 */
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

// A light editor theme so the IDE reads well in the app's light mode. Dark mode
// uses the bundled oneDark theme. Colours are intentionally neutral so the
// editor blends with surrounding surface tokens.
const lightTheme = EditorView.theme({
  '&': { backgroundColor: '#ffffff', color: '#1e293b' },
  '.cm-gutters': { backgroundColor: '#f8fafc', color: '#94a3b8', border: 'none' },
  '.cm-activeLineGutter': { backgroundColor: '#eef2f7' },
  '.cm-activeLine': { backgroundColor: '#f1f5f9' },
  '.cm-content': { caretColor: '#0e7490' },
  '&.cm-focused .cm-cursor': { borderLeftColor: '#0e7490' },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': { backgroundColor: '#cbd5e1' },
}, { dark: false })

/**
 * Reusable CodeMirror 6 editor. Controlled-ish: `value` seeds the document and
 * pushes external updates in; `onChange` reports edits back to the parent.
 *
 * Features: line numbers, fold gutter, auto-indent (indentOnInput + tab),
 * bracket matching, language-aware highlighting, an in-editor search & replace
 * panel (Mod-F / Mod-Alt-F, exposed imperatively as openSearch()), and a
 * dark/light theme synced to the app theme store.
 *
 * Props:
 *   value       current document text
 *   onChange    (text) => void
 *   language    'python' | 'javascript' | 'json' | 'yaml' | 'markdown' | ...
 *   readOnly    boolean
 *   onRun       optional () => void bound to Ctrl/Cmd-Enter
 *   fontSize    optional number (px) for the editor font
 * Ref handle: { openSearch(), focus() }
 */
const CodeEditor = forwardRef(function CodeEditor(
  { value = '', onChange, language = 'python', readOnly = false, onRun, fontSize = 13 },
  ref,
) {
  const hostRef = useRef(null)
  const viewRef = useRef(null)
  const onChangeRef = useRef(onChange)
  const onRunRef = useRef(onRun)
  const langCompartment = useRef(new Compartment())
  const themeCompartment = useRef(new Compartment())
  const readOnlyCompartment = useRef(new Compartment())
  const fontCompartment = useRef(new Compartment())

  const theme = useThemeStore((s) => s.theme)
  const isDark = theme !== 'light'

  // Imperative handle so the toolbar's Search button can open the panel.
  useImperativeHandle(ref, () => ({
    openSearch: () => { const v = viewRef.current; if (v) { openSearchPanel(v); v.focus() } },
    focus: () => viewRef.current?.focus(),
  }), [])

  const fontTheme = (px) => EditorView.theme({
    '&': { height: '100%', fontSize: `${px}px` },
    '.cm-scroller': { fontFamily: '"JetBrains Mono", monospace' },
  })

  // Keep latest callbacks without recreating the editor on every render.
  useEffect(() => { onChangeRef.current = onChange }, [onChange])
  useEffect(() => { onRunRef.current = onRun }, [onRun])

  // Create the editor once.
  useEffect(() => {
    if (!hostRef.current) return

    const runKeymap = keymap.of([
      {
        key: 'Mod-Enter',
        run: () => { onRunRef.current?.(); return true },
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
        // Search keymap first so Mod-F opens find/replace; indentWithTab before
        // defaultKeymap so Tab indents in the editor.
        keymap.of([indentWithTab, ...searchKeymap, ...defaultKeymap, ...historyKeymap]),
        langCompartment.current.of(languageExtension(language)),
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

  // Push external value changes into the editor (e.g. switching files / reset).
  useEffect(() => {
    const view = viewRef.current
    if (!view) return
    const current = view.state.doc.toString()
    if (value !== current) {
      view.dispatch({ changes: { from: 0, to: current.length, insert: value } })
    }
  }, [value])

  // Reconfigure language without rebuilding the editor.
  useEffect(() => {
    viewRef.current?.dispatch({ effects: langCompartment.current.reconfigure(languageExtension(language)) })
  }, [language])

  // React to theme toggles live.
  useEffect(() => {
    viewRef.current?.dispatch({ effects: themeCompartment.current.reconfigure(isDark ? oneDark : lightTheme) })
  }, [isDark])

  // React to readOnly changes (e.g. lock the editor after solving).
  useEffect(() => {
    viewRef.current?.dispatch({ effects: readOnlyCompartment.current.reconfigure(EditorState.readOnly.of(readOnly)) })
  }, [readOnly])

  // React to font-size changes (zoom controls).
  useEffect(() => {
    viewRef.current?.dispatch({ effects: fontCompartment.current.reconfigure(fontTheme(fontSize)) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fontSize])

  return <div ref={hostRef} className="h-full w-full overflow-hidden text-left" />
})

export default CodeEditor
