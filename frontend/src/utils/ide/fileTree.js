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
