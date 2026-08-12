import { describe, it, expect } from 'vitest'
import {
  searchAcrossFiles, buildSymbolIndex, findDefinitions, wordAtOffset,
  MAX_SEARCH_MATCHES,
} from './fileTree'

const PY_FILES = {
  'src/main.py': 'from helpers import shout\n\ndef main():\n    print(shout("hi"))\n',
  'src/helpers.py': 'def shout(text):\n    return text.upper()\n\nclass Greeter:\n    pass\n',
  'src/.keep': '',
}

const JS_FILES = {
  'src/app.js': 'export function render() {\n  return total()\n}\n',
  'src/util.js': 'export const total = () => 1\nclass Box {}\n',
}

describe('searchAcrossFiles', () => {
  it('finds every occurrence with 1-based line and column', () => {
    const hits = searchAcrossFiles(PY_FILES, 'shout')
    // import line, def line, and the call inside main()
    expect(hits).toHaveLength(3)
    const helpers = hits.find((h) => h.path === 'src/helpers.py')
    expect(helpers).toMatchObject({ line: 1, column: 5 })
  })

  it('returns results sorted by path so renders are stable', () => {
    // Object key order follows insertion; a learner creating a file must not
    // reshuffle existing results.
    const shuffled = { 'src/main.py': PY_FILES['src/main.py'], 'src/helpers.py': PY_FILES['src/helpers.py'] }
    const paths = searchAcrossFiles(shuffled, 'shout').map((h) => h.path)
    expect(paths).toEqual([...paths].sort())
  })

  it('is case-insensitive by default and exact when asked', () => {
    expect(searchAcrossFiles(PY_FILES, 'SHOUT').length).toBe(3)
    expect(searchAcrossFiles(PY_FILES, 'SHOUT', { caseSensitive: true })).toHaveLength(0)
  })

  it('finds repeated matches on the same line without looping forever', () => {
    const hits = searchAcrossFiles({ 'a.py': 'x = x + x' }, 'x')
    expect(hits.map((h) => h.column)).toEqual([1, 5, 9])
  })

  it('caps results so a broad query cannot lock the UI', () => {
    const many = { 'a.py': 'a\n'.repeat(MAX_SEARCH_MATCHES + 50) }
    expect(searchAcrossFiles(many, 'a')).toHaveLength(MAX_SEARCH_MATCHES)
  })

  it('ignores .keep placeholders and non-string content', () => {
    expect(searchAcrossFiles({ 'src/.keep': 'shout' }, 'shout')).toHaveLength(0)
    expect(searchAcrossFiles({ 'a.py': null }, 'shout')).toHaveLength(0)
  })

  it('returns nothing for an empty query rather than matching everything', () => {
    expect(searchAcrossFiles(PY_FILES, '')).toEqual([])
  })

  it('never mutates the files map', () => {
    const snapshot = JSON.stringify(PY_FILES)
    searchAcrossFiles(PY_FILES, 'shout')
    expect(JSON.stringify(PY_FILES)).toBe(snapshot)
  })
})

describe('buildSymbolIndex', () => {
  it('indexes python defs and classes with their file and line', () => {
    const idx = buildSymbolIndex(PY_FILES)
    expect(idx.get('shout')).toEqual([
      { name: 'shout', kind: 'function', path: 'src/helpers.py', line: 1, text: 'def shout(text):' },
    ])
    expect(idx.get('Greeter')[0]).toMatchObject({ kind: 'class', line: 4 })
  })

  it('indexes js functions, consts and classes', () => {
    const idx = buildSymbolIndex(JS_FILES)
    expect(idx.get('render')[0]).toMatchObject({ kind: 'function', path: 'src/app.js' })
    expect(idx.get('total')[0]).toMatchObject({ kind: 'variable', path: 'src/util.js' })
    expect(idx.get('Box')[0]).toMatchObject({ kind: 'class' })
  })

  it('keeps every definition when a name is declared twice', () => {
    // Silently dropping a duplicate would make go-to-definition jump to the
    // wrong file with no way for the caller to notice the ambiguity.
    const idx = buildSymbolIndex({ 'a.py': 'def main():\n    pass\n', 'b.py': 'def main():\n    pass\n' })
    expect(idx.get('main')).toHaveLength(2)
  })
})

describe('findDefinitions', () => {
  it('resolves a symbol across files', () => {
    expect(findDefinitions(PY_FILES, 'shout')[0]).toMatchObject({ path: 'src/helpers.py', line: 1 })
  })

  it('prefers a definition in the file being edited when ambiguous', () => {
    const files = { 'a.py': 'def main():\n    pass\n', 'b.py': 'def main():\n    pass\n' }
    expect(findDefinitions(files, 'main', { preferPath: 'b.py' })[0].path).toBe('b.py')
    // ...but still reports the other site so the UI can disambiguate.
    expect(findDefinitions(files, 'main', { preferPath: 'b.py' })).toHaveLength(2)
  })

  it('returns empty for unknown or blank names', () => {
    expect(findDefinitions(PY_FILES, 'nope')).toEqual([])
    expect(findDefinitions(PY_FILES, '   ')).toEqual([])
  })
})

describe('wordAtOffset', () => {
  it('extracts the identifier under the cursor from either edge', () => {
    const src = 'print(shout("hi"))'
    expect(wordAtOffset(src, 6)).toBe('shout')   // before the s
    expect(wordAtOffset(src, 9)).toBe('shout')   // mid-word
    expect(wordAtOffset(src, 11)).toBe('shout')  // after the t
  })

  it('ignores numeric literals so 42 is never a symbol lookup', () => {
    expect(wordAtOffset('x = 42', 5)).toBe('')
  })

  it('handles $ and _ identifiers and out-of-range offsets', () => {
    expect(wordAtOffset('const _priv$ = 1', 8)).toBe('_priv$')
    expect(wordAtOffset('abc', 999)).toBe('abc')
    expect(wordAtOffset('', 0)).toBe('')
  })
})
