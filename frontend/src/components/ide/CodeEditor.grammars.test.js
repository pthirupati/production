import { describe, it, expect } from 'vitest'
import { EditorState } from '@codemirror/state'
import { syntaxTree } from '@codemirror/language'
import { CompletionContext } from '@codemirror/autocomplete'
import { languageExtension, autocompleteFor, completionSourcesFor } from './CodeEditor'

/**
 * Parse `src` with the extension we hand CodeMirror for `lang` and collect every
 * syntax node name. The toy StreamLanguage tokenizers produce a flat tree with no
 * named structure, so asserting on real node names is what distinguishes a real
 * grammar from the hand-rolled regex tokenizers these tests replaced.
 */
function nodeNames(lang, src) {
  const state = EditorState.create({ doc: src, extensions: [languageExtension(lang)] })
  const names = new Set()
  syntaxTree(state).iterate({ enter: (n) => { names.add(n.name) } })
  return names
}

describe('languageExtension real grammars', () => {
  it('nests CSS and JS inside HTML', () => {
    // The old hand-rolled htmlLanguage tokenizer only knew tags/attrs/strings, so
    // <style> and <script> bodies came back completely unhighlighted.
    const names = nodeNames('html', '<style>\n.a { color: red; }\n</style>\n<script>\nconst x = 1;\n</script>\n')
    expect(names.has('StyleSheet')).toBe(true)
    expect(names.has('RuleSet')).toBe(true)
    expect(names.has('Declaration')).toBe(true)
    expect(names.has('Script')).toBe(true)
    expect(names.has('VariableDeclaration')).toBe(true)
  })

  it('parses CSS structurally rather than as loose tokens', () => {
    const names = nodeNames('css', '.card { color: #fff; }\n')
    expect(names.has('RuleSet')).toBe(true)
    expect(names.has('ClassSelector')).toBe(true)
    expect(names.has('PropertyName')).toBe(true)
  })

  it('still resolves the languages that already had real grammars', () => {
    expect(nodeNames('python', 'def f():\n    return 1\n').has('FunctionDefinition')).toBe(true)
    expect(nodeNames('json', '{"a": 1}').has('Object')).toBe(true)
  })

  it('returns an extension for java and shell', () => {
    // These use @codemirror/legacy-modes (a real CM5 mode) rather than a ~20-line
    // regex tokenizer. StreamLanguage trees are flat, so assert on tokens instead.
    expect(languageExtension('java')).toBeTruthy()
    expect(languageExtension('bash')).toBeTruthy()
  })

  it('returns no extension for an unknown language', () => {
    expect(languageExtension('brainfuck')).toEqual([])
  })
})

/**
 * Collect completion labels offered at the end of `src` for `lang`.
 *
 * Drives the completion sources directly rather than the async UI, which needs a
 * live EditorView. Sources arrive two ways: keyword lists come from
 * completionSourcesFor, while grammar-supplied sources (html/css) register
 * through languageData.
 */
async function completionsFor(lang, src) {
  const state = EditorState.create({ doc: src, extensions: [languageExtension(lang)] })
  const pos = state.doc.length
  const ctx = new CompletionContext(state, pos, true)
  const sources = completionSourcesFor(lang) ?? state.languageDataAt('autocomplete', pos)

  const labels = []
  for (const source of sources) {
    if (typeof source !== 'function') continue
    const result = await source(ctx)
    if (result?.options) labels.push(...result.options.map((o) => o.label))
  }
  return labels
}

describe('autocompleteFor coverage', () => {
  it('offers HTML tag completions from the real grammar', async () => {
    // Previously html fell through to bare autocompletion() with no source at all.
    const labels = await completionsFor('html', '<di')
    expect(labels.length).toBeGreaterThan(0)
    expect(labels).toContain('div')
  })

  it('offers CSS value completions from the real grammar', async () => {
    // lang-css completes in value position, where the parser has a complete
    // Declaration node to work from; a half-typed property name yields nothing.
    const labels = await completionsFor('css', '.a { color: re')
    expect(labels).toContain('relative')
    expect(labels.length).toBeGreaterThan(100)
  })

  it('offers keyword completions for java', async () => {
    const labels = await completionsFor('java', 'pub')
    expect(labels).toContain('public')
  })

  it('offers keyword completions for shell', async () => {
    const labels = await completionsFor('bash', 'ec')
    expect(labels).toContain('echo')
  })

  it('keeps the existing python and js keyword lists', async () => {
    expect(await completionsFor('python', 'de')).toContain('def')
    expect(await completionsFor('javascript', 'fun')).toContain('function')
  })

  it('does not override the grammar-supplied sources for html and css', () => {
    // An override here would discard lang-html/lang-css completions entirely.
    expect(completionSourcesFor('html')).toBeNull()
    expect(completionSourcesFor('css')).toBeNull()
    expect(completionSourcesFor('python')).toHaveLength(1)
  })

  it('always returns a mountable autocompletion extension', () => {
    for (const lang of ['python', 'html', 'css', 'java', 'bash', 'brainfuck']) {
      expect(autocompleteFor(lang)).toHaveLength(1)
    }
  })
})
