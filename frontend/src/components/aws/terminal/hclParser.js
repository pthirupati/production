// Shared HCL tokenizer for the Terraform simulation.
//
// Parses a practical subset of HCL (resource / provider / variable / output /
// data blocks, nested blocks, map + list attributes) into plain JS so both the
// terminal engine (terraformSim.js) and the IDE-driven apply bridge
// (utils/terraformAwsBridge.js) create resources from the SAME parse — no more
// low-fidelity regex path. This is a pure parser: it never touches the store.

// Strip // and # line comments and /* */ blocks without touching strings.
function stripComments(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .map((line) => {
      // remove trailing # or // comments (naive: ok for lab HCL)
      const hashOutside = line.replace(/("(?:[^"\\]|\\.)*")|(#.*$)|(\/\/.*$)/g, (m, str) => (str ? str : ''))
      return hashOutside
    })
    .join('\n')
}

// Extract `key = value` and `key { ... }` pairs from a block body.
export function parseBody(body) {
  const attrs = {}
  const blocks = []
  let i = 0
  const n = body.length
  while (i < n) {
    // skip whitespace/commas
    while (i < n && /\s|,/.test(body[i])) i += 1
    if (i >= n) break
    // read identifier
    const idMatch = /^[A-Za-z0-9_-]+/.exec(body.slice(i))
    if (!idMatch) { i += 1; continue }
    const key = idMatch[0]
    i += key.length
    while (i < n && /\s/.test(body[i])) i += 1
    if (body[i] === '{') {
      // nested block (ingress, tags as block-style, etc.)
      const { inner, end } = readBraces(body, i)
      blocks.push({ key, body: inner })
      i = end
    } else if (body[i] === '=') {
      i += 1
      while (i < n && /\s/.test(body[i])) i += 1
      if (body[i] === '{') {
        const { inner, end } = readBraces(body, i)
        attrs[key] = parseBody(inner).attrs // map value e.g. tags = { Name = "x" }
        i = end
      } else if (body[i] === '[') {
        const { inner, end } = readBrackets(body, i)
        attrs[key] = inner.split(',').map((s) => unquote(s.trim())).filter(Boolean)
        i = end
      } else {
        // scalar until newline
        let j = i
        while (j < n && body[j] !== '\n') j += 1
        attrs[key] = unquote(body.slice(i, j).trim())
        i = j
      }
    } else {
      i += 1
    }
  }
  return { attrs, blocks }
}

function readBraces(src, open) {
  let depth = 0
  for (let i = open; i < src.length; i += 1) {
    if (src[i] === '{') depth += 1
    else if (src[i] === '}') { depth -= 1; if (depth === 0) return { inner: src.slice(open + 1, i), end: i + 1 } }
  }
  return { inner: src.slice(open + 1), end: src.length }
}
function readBrackets(src, open) {
  let depth = 0
  for (let i = open; i < src.length; i += 1) {
    if (src[i] === '[') depth += 1
    else if (src[i] === ']') { depth -= 1; if (depth === 0) return { inner: src.slice(open + 1, i), end: i + 1 } }
  }
  return { inner: src.slice(open + 1), end: src.length }
}
function unquote(s) {
  if (!s) return s
  const m = /^"((?:[^"\\]|\\.)*)"$/.exec(s)
  if (m) return m[1]
  if (s === 'true') return true
  if (s === 'false') return false
  if (/^-?\d+$/.test(s)) return parseInt(s, 10)
  return s
}

// Replace bare `var.NAME` scalar references with the declared variable's default
// so the console mirrors the values the config actually resolves to (what a real
// `terraform apply` would use). Unknown refs are left untouched. Recurses into
// list + map attributes (e.g. tags = { Name = var.app }). Interpolated strings
// like "${var.env}-web" are intentionally not substituted — same limitation the
// terminal engine has always had.
const VAR_REF = /^var\.([A-Za-z0-9_-]+)$/
function resolveVars(value, variables) {
  if (typeof value === 'string') {
    const m = VAR_REF.exec(value)
    if (m && variables[m[1]] !== undefined) return variables[m[1]]
    return value
  }
  if (Array.isArray(value)) return value.map((v) => resolveVars(v, variables))
  if (value && typeof value === 'object') {
    const out = {}
    for (const [k, v] of Object.entries(value)) out[k] = resolveVars(v, variables)
    return out
  }
  return value
}

// Parse all resource/provider/variable/output blocks from concatenated HCL.
export function parseHcl(src) {
  const clean = stripComments(src)
  const resources = []
  let provider = null
  const outputs = []
  const variables = {}
  const re = /\b(resource|provider|variable|output|data)\b/g
  let m
  while ((m = re.exec(clean))) {
    const kind = m[1]
    let i = m.index + kind.length
    // read quoted labels until {
    const labels = []
    while (i < clean.length && clean[i] !== '{') {
      const lm = /"((?:[^"\\]|\\.)*)"/.exec(clean.slice(i))
      const idm = /[A-Za-z0-9_-]+/.exec(clean.slice(i))
      if (lm && clean.slice(i).indexOf(lm[0]) <= 2) { labels.push(lm[1]); i += clean.slice(i).indexOf(lm[0]) + lm[0].length }
      else if (clean[i] === '{') break
      else if (idm && /\S/.test(clean[i])) { labels.push(idm[0]); i += clean.slice(i).indexOf(idm[0]) + idm[0].length }
      else i += 1
    }
    if (clean[i] !== '{') continue
    const { inner, end } = readBraces(clean, i)
    re.lastIndex = end
    const parsed = parseBody(inner)
    if (kind === 'resource') resources.push({ type: labels[0], name: labels[1], ...parsed })
    else if (kind === 'provider' && labels[0] === 'aws') provider = parsed.attrs
    else if (kind === 'output') outputs.push({ name: labels[0], ...parsed })
    else if (kind === 'variable' && labels[0]) variables[labels[0]] = parsed.attrs.default
  }
  // Resolve declared variable defaults into resource + provider attributes.
  if (Object.keys(variables).length) {
    resources.forEach((r) => { r.attrs = resolveVars(r.attrs, variables) })
    if (provider) provider = resolveVars(provider, variables)
  }
  return { resources, provider, outputs, variables }
}
