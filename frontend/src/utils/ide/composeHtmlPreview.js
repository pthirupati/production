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

/**
 * Resolve an authored href/src against the document it appears in.
 *
 * The preview renders into an opaque-origin srcDoc iframe (HtmlPreviewPane uses
 * sandbox="allow-scripts" with no allow-same-origin), so there is no origin for
 * a relative URL to resolve against — `href="styles.css"` would 404 silently.
 * Every reference therefore has to be matched back to a key in the virtual file
 * map and inlined, or dropped.
 *
 * Returns the matching file-map key, or '' when the reference names something
 * that is not in the map (a dangling ref, or an absolute/external URL we must
 * leave alone).
 */
export function resolvePreviewRef(files = {}, ref = '', fromPath = '') {
  const raw = String(ref || '').trim()
  if (!raw) return ''
  // Protocol-relative, absolute-scheme, and data: refs are the author's problem,
  // not ours — leave them in the document untouched.
  if (/^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(raw)) return ''
  const clean = raw.split('#')[0].split('?')[0].replace(/^\.\//, '')
  if (!clean) return ''
  if (Object.prototype.hasOwnProperty.call(files, clean)) return clean
  // Root-relative ("/styles.css") maps onto the map key without the leading slash.
  const rooted = clean.replace(/^\/+/, '')
  if (rooted !== clean && Object.prototype.hasOwnProperty.call(files, rooted)) return rooted
  // Relative to the referencing document's directory, e.g. index.html in
  // "src/" referring to "styles.css" means the map key "src/styles.css".
  const dir = String(fromPath || '').includes('/')
    ? String(fromPath).replace(/\/[^/]*$/, '/')
    : ''
  if (dir && Object.prototype.hasOwnProperty.call(files, dir + rooted)) return dir + rooted
  // Last resort: match on basename. Authors write href="styles.css" from a
  // nested document more often than they get the ../ count right, and a
  // wrong-but-unique basename match still previews what they meant.
  const base = rooted.split('/').pop()
  const byBase = Object.keys(files).filter((p) => (p.split('/').pop() || p) === base)
  return byBase.length === 1 ? byBase[0] : ''
}

export function hasHtmlPreview(files = {}, language = '') {
  if (listHtmlPaths(files).length > 0) return true
  const lang = (language || '').toLowerCase()
  return lang === 'html' || lang === 'htm'
}

/**
 * The .html document a learner should land on, or '' when there is none.
 *
 * Every one of the 150 scenarios/html labs declares `entrypoint: solution.js` and
 * marks that file `readonly: true` — it is the grader harness, and its own first
 * line reads "Keep this file; edit index.html and styles.css instead." The IDE
 * opens `spec.entrypoint` on hydrate, so without this preference the learner lands
 * on a read-only harness and has to go find index.html in the tree.
 *
 * Same rule the preview composer uses to pick its primary document, so the open
 * tab and the rendered preview can never disagree.
 *
 * `declaredRoot` is the scenario's `preview.root`, which lets an author name the
 * document explicitly instead of relying on the filename guess. It wins over the
 * heuristic but only when it names a file that actually exists — a typo'd root
 * must not blank the preview, and the backend validator (R10) already fails the
 * build for that case. The heuristic stays as the fallback because 0 of ~155
 * labs declare a root today.
 */
export function preferredHtmlPath(files = {}, declaredRoot = '') {
  const root = String(declaredRoot || '').trim()
  if (root && Object.prototype.hasOwnProperty.call(files || {}, root)) return root
  const htmlPaths = listHtmlPaths(files)
  return htmlPaths.find((p) => /index\.html?$/i.test(p)) || htmlPaths[0] || ''
}

/** postMessage type used by the preview console bridge. */
export const PREVIEW_LOG_TYPE = 'fixitlab:preview-log'

/**
 * Console/error bridge injected into the preview document.
 *
 * Without this, console.log and uncaught exceptions inside the previewed page go
 * nowhere — the learner sees a blank result and no explanation. The whole shim is
 * wrapped in try/catch and appended as the LAST script so that if anything here
 * throws it cannot stop the learner's own code or blank the preview.
 *
 * Messages are capped (MAX_MESSAGES) because a runaway loop in learner code —
 * `while (true) console.log(i++)` — would otherwise flood React state and lock
 * the tab. Once the cap is hit we stop posting entirely.
 */
const CONSOLE_BRIDGE = `<script>
(function () {
  try {
    var MAX_MESSAGES = 200;
    var MAX_LEN = 2000;
    var sent = 0;
    function fmt(v) {
      if (typeof v === 'string') return v;
      if (v instanceof Error) return (v.stack || (v.name + ': ' + v.message));
      try { return JSON.stringify(v); } catch (e) { return String(v); }
    }
    function post(level, args) {
      if (sent >= MAX_MESSAGES) return;
      sent += 1;
      var text = Array.prototype.map.call(args, fmt).join(' ').slice(0, MAX_LEN);
      if (sent === MAX_MESSAGES) {
        text += '\\n[preview] too many messages — console output suppressed.';
      }
      try {
        parent.postMessage({ type: ${JSON.stringify(PREVIEW_LOG_TYPE)}, level: level, text: text }, '*');
      } catch (e) { /* cross-origin parent — nothing we can do */ }
    }
    ['log', 'info', 'warn', 'error', 'debug'].forEach(function (level) {
      var original = console[level];
      console[level] = function () {
        post(level, arguments);
        if (original) { try { original.apply(console, arguments); } catch (e) {} }
      };
    });
    window.addEventListener('error', function (e) {
      post('error', [e.message + ' (' + (e.filename || 'preview') + ':' + e.lineno + ')']);
    });
    window.addEventListener('unhandledrejection', function (e) {
      post('error', ['Unhandled promise rejection: ' + fmt(e.reason)]);
    });
  } catch (e) { /* never let the bridge break the preview */ }
})();
</script>`

/**
 * Compose a full HTML document string suitable for iframe srcDoc.
 *
 * `declaredRoot` (the scenario's `preview.root`) is threaded into the same
 * preferredHtmlPath() call the open-tab selection uses, so a lab that declares a
 * root cannot end up previewing one file while the editor opens another. An
 * explicit `htmlPath` still wins — that is the learner clicking a specific file.
 */
export function composeHtmlPreview(
  files = {},
  { htmlPath, declaredRoot = '', consoleBridge = true } = {},
) {
  const htmlPaths = listHtmlPaths(files)
  const primary = htmlPath && files[htmlPath] != null
    ? htmlPath
    : preferredHtmlPath(files, declaredRoot)
  if (!primary) {
    // Bare language:html with a single entry file that isn't named .html
    const fallback = Object.keys(files).find((p) => /\.(html?|md)$/i.test(p))
      || Object.keys(files)[0]
    if (!fallback) return '<!DOCTYPE html><html><body><p>No HTML file to preview.</p></body></html>'
    return String(files[fallback] || '')
  }

  let html = String(files[primary] || '')

  // --- Resolve authored references in place ------------------------------
  //
  // 40 of the 150 scenarios/html labs ship `<link rel="stylesheet"
  // href="styles.css" />` and 10 ship `<script src="app.js">`; both 404 in an
  // opaque-origin srcDoc. We rewrite each tag to an inline block at the SAME
  // position, because position is semantics: a <script src> in <head> must not
  // silently move to end-of-body, and a <link> ordering determines the cascade.
  //
  // `linkedCss` / `inlinedJs` record what we consumed so the catch-all
  // concatenation below cannot inline the same file a second time — a
  // double-executed side-effectful lab script (counters, DOM appends) produces
  // wrong output that reads like a learner bug.
  const linkedCss = new Set()
  const inlinedJs = new Set()

  html = html.replace(/<link\b[^>]*>/gi, (tag) => {
    // Only stylesheet links are ours; leave preload/icon/manifest alone unless
    // they dangle (below).
    const hrefMatch = tag.match(/\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/i)
    const href = hrefMatch ? (hrefMatch[1] ?? hrefMatch[2] ?? hrefMatch[3] ?? '') : ''
    if (!href) return tag
    if (/^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(href.trim())) return tag // external CDN — keep
    const resolved = resolvePreviewRef(files, href, primary)
    const isStylesheet = /\brel\s*=\s*(?:"[^"]*\bstylesheet\b[^"]*"|'[^']*\bstylesheet\b[^']*'|stylesheet\b)/i.test(tag)
    if (resolved && isStylesheet) {
      linkedCss.add(resolved)
      return `<style data-preview-src="${resolved}">\n${files[resolved] || ''}\n</style>`
    }
    // Unresolvable relative ref: drop it rather than let the iframe fire a
    // 404 the learner cannot see or fix.
    return resolved ? tag : ''
  })

  html = html.replace(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi, (tag, attrs, body) => {
    const srcMatch = attrs.match(/\bsrc\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/i)
    if (!srcMatch) return tag // inline script authored in the document — untouched
    const src = srcMatch[1] ?? srcMatch[2] ?? srcMatch[3] ?? ''
    if (/^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(String(src).trim())) return tag // external CDN
    const resolved = resolvePreviewRef(files, src, primary)
    if (!resolved) return '' // dangling ref (e.g. the perf labs' absent app.js)
    inlinedJs.add(resolved)
    // Strip src/defer/async: the tag is inline now, so those attributes are
    // meaningless and `defer` on an inline script is ignored anyway.
    const kept = attrs
      .replace(/\bsrc\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/i, '')
      .replace(/\b(?:defer|async)\b(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?/gi, '')
      .trim()
    return `<script${kept ? ' ' + kept : ''} data-preview-src="${resolved}">\n${files[resolved] || ''}\n</script>${body.trim() ? `<!-- ${resolved} had inline body, dropped -->` : ''}`
  })

  // --- Catch-all for files the document never referenced ------------------
  //
  // Most labs link nothing at all; the composer is the only reason their CSS/JS
  // applies. Keep inlining the leftovers so those previews do not go blank —
  // but skip anything we already placed above.
  //
  // CSS is the exception: once the document links ANY stylesheet the author has
  // stated which sheets they want, and blindly appending the rest is wrong —
  // theme-dark.css and theme-light.css would both apply and the cascade would
  // pick by file-map key order rather than by what the page asked for. So the
  // unreferenced-CSS fallback only fires for documents that link nothing.
  const cssBlocks = (linkedCss.size > 0 ? [] : listCssPaths(files))
    .map((p) => `/* ${p} */\n${files[p] || ''}`)
    .join('\n\n')
  const jsBlocks = listBrowserJsPaths(files)
    .filter((p) => p !== primary && !inlinedJs.has(p))
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

  if (consoleBridge) {
    // Must run BEFORE the learner's code so it captures their console output,
    // but injected only at a structural boundary we know exists. The final
    // fallback prepends, which is always valid — the browser hoists a leading
    // <script> into the implied <head> rather than dropping the document.
    if (/<head[^>]*>/i.test(html)) {
      html = html.replace(/<head([^>]*)>/i, `<head$1>${CONSOLE_BRIDGE}`)
    } else if (/<body[^>]*>/i.test(html)) {
      html = html.replace(/<body([^>]*)>/i, `<body$1>${CONSOLE_BRIDGE}`)
    } else {
      html = `${CONSOLE_BRIDGE}\n${html}`
    }
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
  if (p.endsWith('.html') || p.endsWith('.htm')) return 'html'
  if (p.endsWith('.css')) return 'css'
  if (p.endsWith('.java')) return 'java'
  if (p.endsWith('.sh') || p.endsWith('.bash') || p.endsWith('.zsh')) return 'shell'
  return fallback
}
