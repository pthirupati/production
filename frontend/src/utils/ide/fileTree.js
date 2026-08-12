/**
 * Nested folder tree helpers for VS Code–style explorers (Coding / Terraform / Packer).
 */

/** Build a nested folder tree from a flat path → content map. */
export function buildFileTree(fileMap) {
  const root = { name: '', children: {}, files: [] }
  Object.keys(fileMap || {}).sort().forEach((path) => {
    const parts = path.split('/').filter(Boolean)
    let node = root
    parts.forEach((part, i) => {
      if (i === parts.length - 1) {
        if (part === '.keep') return
        node.files.push(path)
      } else {
        if (!node.children[part]) node.children[part] = { name: part, children: {}, files: [] }
        node = node.children[part]
      }
    })
  })
  return root
}

/** Parent directory paths for a file path (e.g. a/b/c.js → ['a','a/b']). */
export function parentDirs(path) {
  const parts = (path || '').split('/').filter(Boolean)
  if (parts.length < 2) return []
  return parts.slice(0, -1).map((_, i, a) => a.slice(0, i + 1).join('/'))
}

/** Basename of a path. */
export function fileBasename(path) {
  const parts = (path || '').split('/')
  return parts[parts.length - 1] || path || ''
}

/** Default stub content by extension / language hint. */
export function stubContentForPath(path, language = '') {
  const p = (path || '').toLowerCase()
  const lang = (language || '').toLowerCase()
  if (p.endsWith('.py') || lang === 'python') return '# New module\n\n'
  if (p.endsWith('.ts') || p.endsWith('.tsx')) return '// New TypeScript module\n\n'
  if (p.endsWith('.jsx') || p.endsWith('.js') || p.endsWith('.mjs')) return '// New module\n\n'
  if (p.endsWith('.java')) return 'public class Main {\n    public static void main(String[] args) {\n    }\n}\n'
  if (p.endsWith('.html') || p.endsWith('.htm')) {
    return '<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="utf-8" />\n  <title>Page</title>\n</head>\n<body>\n\n</body>\n</html>\n'
  }
  if (p.endsWith('.css')) return '/* styles */\n\n'
  if (p.endsWith('.json')) return '{\n}\n'
  if (p.endsWith('.sh') || p.endsWith('.bash')) return '#!/usr/bin/env bash\nset -euo pipefail\n\n'
  if (p.endsWith('.md')) return '# Notes\n\n'
  if (p.endsWith('.yml') || p.endsWith('.yaml')) return '# config\n\n'
  return ''
}

/**
 * Default filename (no directory) for a new file in a given language.
 *
 * Single source of truth: IdeExplorer's inline create-draft needs a bare
 * basename (it joins it onto the right-clicked folder itself), while
 * newFileHint below needs the same name with a src/ prefix. Previously the
 * explorer carried its own substring-match ladder that tested `.includes('java')`
 * before the js branch, so language 'javascript' produced Main.java, and it
 * disagreed with this file on the html name.
 *
 * html → index.html, not page.html: every scenarios/html lab ships an
 * index.html, and both preferredHtmlPath() and the preview composer in
 * composeHtmlPreview.js prefer /index\.html?$/ when picking the primary
 * document. A new page.html would never become the previewed file.
 */
export function newFileBasename(language = '') {
  const lang = (language || '').toLowerCase()
  if (['python', 'py'].includes(lang)) return 'module.py'
  if (['javascript', 'js', 'node', 'nodejs'].includes(lang)) return 'module.js'
  if (['typescript', 'ts'].includes(lang)) return 'module.ts'
  if (lang === 'java') return 'Main.java'
  if (['html', 'htm'].includes(lang)) return 'index.html'
  if (['bash', 'shell', 'sh'].includes(lang)) return 'script.sh'
  // Terraform/Packer workspaces mount IdeExplorer with language="hcl". Not
  // main.tf — that is always present already and is in their protectedPaths,
  // so the create-draft would open pre-filled with a name that can't be saved.
  if (['hcl', 'terraform', 'tf'].includes(lang)) return 'module.tf'
  return 'untitled.txt'
}

/** Guess a sensible new-file path hint from language + existing files. */
export function newFileHint(language = '', existing = []) {
  const hasSrc = (existing || []).some((p) => p.startsWith('src/'))
  return `${hasSrc ? 'src/' : ''}${newFileBasename(language)}`
}

// ── Workspace search + symbol index ────────────────────────────────────────
//
// Everything below is READ-ONLY over the `files` map. Nothing here may mutate
// file content: go-to-definition and find-across-files are navigation aids, and
// grading stays server-side. Both are recomputed from the live `files` object
// rather than cached, because a stale index sends the learner to the wrong line
// after an edit — worse than having no jump at all.

/** Files whose contents are never worth searching or indexing. */
const SEARCHABLE_SKIP = /(^|\/)\.keep$/

/** Cap on matches so one broad query cannot lock the UI thread. */
export const MAX_SEARCH_MATCHES = 200

/**
 * Find a literal string across every file in the workspace.
 *
 * Returns flat matches ordered by path then line so the UI can render them
 * grouped without re-sorting. `caseSensitive` defaults false to match the
 * behaviour learners expect from an editor's find-in-files.
 */
export function searchAcrossFiles(files, query, { caseSensitive = false, limit = MAX_SEARCH_MATCHES } = {}) {
  const needle = String(query ?? '')
  if (!needle) return []
  const map = files || {}
  const matches = []
  // Sorted so results are stable across renders — Object.keys order follows
  // insertion, which changes as the learner creates files.
  for (const path of Object.keys(map).sort()) {
    if (SEARCHABLE_SKIP.test(path)) continue
    const content = map[path]
    if (typeof content !== 'string') continue
    const lines = content.split('\n')
    for (let i = 0; i < lines.length; i += 1) {
      const line = lines[i]
      const hay = caseSensitive ? line : line.toLowerCase()
      const pin = caseSensitive ? needle : needle.toLowerCase()
      let col = hay.indexOf(pin)
      while (col !== -1) {
        matches.push({
          path,
          line: i + 1,
          column: col + 1,
          // Trimmed for display, but the untrimmed column is what the editor
          // needs to place the cursor, so both are kept.
          preview: line.trim().slice(0, 200),
        })
        if (matches.length >= limit) return matches
        col = hay.indexOf(pin, col + pin.length)
      }
    }
  }
  return matches
}

/**
 * Declaration patterns per language family.
 *
 * Deliberately regex-based rather than a real parser: the workspace holds a
 * handful of small learner files, and a mis-parse in a full AST pass would drop
 * the whole file's symbols. A regex that misses an exotic declaration merely
 * makes go-to-definition unavailable for it, which degrades gracefully.
 */
const SYMBOL_PATTERNS = [
  // python
  { kind: 'function', re: /^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)/ },
  { kind: 'class', re: /^\s*class\s+([A-Za-z_]\w*)/ },
  // js/ts
  { kind: 'function', re: /^\s*(?:export\s+)?(?:async\s+)?function\s*\*?\s+([A-Za-z_$][\w$]*)/ },
  { kind: 'variable', re: /^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)/ },
  { kind: 'class', re: /^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)/ },
]

/**
 * Build a symbol → definitions index across the workspace.
 *
 * A name can legitimately be defined more than once (two files each with a
 * `main`), so every symbol maps to an ARRAY. Callers must handle the ambiguous
 * case by disambiguating rather than silently jumping to the first hit.
 */
export function buildSymbolIndex(files) {
  const map = files || {}
  const index = new Map()
  for (const path of Object.keys(map).sort()) {
    if (SEARCHABLE_SKIP.test(path)) continue
    const content = map[path]
    if (typeof content !== 'string') continue
    const lines = content.split('\n')
    for (let i = 0; i < lines.length; i += 1) {
      const line = lines[i]
      for (const { kind, re } of SYMBOL_PATTERNS) {
        const m = re.exec(line)
        if (!m) continue
        const name = m[1]
        const entry = { name, kind, path, line: i + 1, text: line.trim().slice(0, 200) }
        if (!index.has(name)) index.set(name, [])
        index.get(name).push(entry)
        break // one declaration kind per line
      }
    }
  }
  return index
}

/**
 * Resolve a symbol name to its definition sites.
 *
 * `preferPath` biases toward a definition in the file the learner is already
 * looking at, which is the common case for a local helper shadowing a name
 * defined elsewhere.
 */
export function findDefinitions(files, name, { preferPath = '' } = {}) {
  const symbol = String(name ?? '').trim()
  if (!symbol) return []
  const hits = buildSymbolIndex(files).get(symbol) || []
  if (!preferPath || hits.length < 2) return hits
  const local = hits.filter((h) => h.path === preferPath)
  return local.length ? [...local, ...hits.filter((h) => h.path !== preferPath)] : hits
}

/**
 * Extract the identifier surrounding a character offset.
 *
 * Used to turn a cursor position into a go-to-definition query without asking
 * the learner to select the word first.
 */
export function wordAtOffset(text, offset) {
  const src = String(text ?? '')
  const i = Math.max(0, Math.min(Number(offset) || 0, src.length))
  const isWord = (ch) => /[A-Za-z0-9_$]/.test(ch)
  let start = i
  while (start > 0 && isWord(src[start - 1])) start -= 1
  let end = i
  while (end < src.length && isWord(src[end])) end += 1
  const word = src.slice(start, end)
  // A leading digit means we grabbed a numeric literal, not an identifier.
  if (!word || /^\d/.test(word)) return ''
  return word
}
