/**
 * Build a sandboxed srcDoc for Coding IDE HTML preview.
 * Inlines CSS/JS files and uses the primary .html file as the document.
 */

export function listHtmlPaths(files = {}) {
  return Object.keys(files || {}).filter((p) => /\.html?$/i.test(p))
}

export function listCssPaths(files = {}) {
  return Object.keys(files || {}).filter((p) => /\.css$/i.test(p))
}

export function listBrowserJsPaths(files = {}) {
  return Object.keys(files || {}).filter((p) => {
    if (!/\.jsx?$/i.test(p)) return false
    // Exclude grader harness / node-style solution entrypoints
    const base = p.split('/').pop() || p
    return !/^(solution|check|test|grader)\.jsx?$/i.test(base)
  })
}

export function hasHtmlPreview(files = {}, language = '') {
  if (listHtmlPaths(files).length > 0) return true
  const lang = (language || '').toLowerCase()
  return lang === 'html' || lang === 'htm'
}

/**
 * Compose a full HTML document string suitable for iframe srcDoc.
 */
export function composeHtmlPreview(files = {}, { htmlPath } = {}) {
  const htmlPaths = listHtmlPaths(files)
  const primary = htmlPath && files[htmlPath] != null
    ? htmlPath
    : (htmlPaths.find((p) => /index\.html?$/i.test(p)) || htmlPaths[0])
  if (!primary) {
    // Bare language:html with a single entry file that isn't named .html
    const fallback = Object.keys(files).find((p) => /\.(html?|md)$/i.test(p))
      || Object.keys(files)[0]
    if (!fallback) return '<!DOCTYPE html><html><body><p>No HTML file to preview.</p></body></html>'
    return String(files[fallback] || '')
  }

  let html = String(files[primary] || '')
  const cssBlocks = listCssPaths(files)
    .map((p) => `/* ${p} */\n${files[p] || ''}`)
    .join('\n\n')
  const jsBlocks = listBrowserJsPaths(files)
    .filter((p) => p !== primary)
    .map((p) => `/* ${p} */\n${files[p] || ''}`)
    .join('\n\n')

  if (cssBlocks) {
    if (/<\/head>/i.test(html)) {
      html = html.replace(/<\/head>/i, `<style>\n${cssBlocks}\n</style>\n</head>`)
    } else if (/<body[^>]*>/i.test(html)) {
      html = html.replace(/<body([^>]*)>/i, `<head><style>\n${cssBlocks}\n</style></head><body$1>`)
    } else {
      html = `<style>\n${cssBlocks}\n</style>\n${html}`
    }
  }

  if (jsBlocks) {
    if (/<\/body>/i.test(html)) {
      html = html.replace(/<\/body>/i, `<script>\n${jsBlocks}\n</script>\n</body>`)
    } else {
      html = `${html}\n<script>\n${jsBlocks}\n</script>`
    }
  }

  if (!/<!DOCTYPE/i.test(html) && !/<html/i.test(html)) {
    html = `<!DOCTYPE html><html><head><meta charset="utf-8" /></head><body>${html}</body></html>`
  }
  return html
}

export function editorLanguageForPath(path, fallback = 'javascript') {
  const p = (path || '').toLowerCase()
  if (p.endsWith('.py')) return 'python'
  if (p.endsWith('.ts') || p.endsWith('.tsx')) return 'typescript'
  if (p.endsWith('.jsx')) return 'jsx'
  if (p.endsWith('.js') || p.endsWith('.mjs') || p.endsWith('.cjs')) return 'javascript'
  if (p.endsWith('.json')) return 'json'
  if (p.endsWith('.yml') || p.endsWith('.yaml')) return 'yaml'
  if (p.endsWith('.md') || p.endsWith('.markdown')) return 'markdown'
  if (p.endsWith('.html') || p.endsWith('.htm') || p.endsWith('.css')) return 'markdown'
  return fallback
}
