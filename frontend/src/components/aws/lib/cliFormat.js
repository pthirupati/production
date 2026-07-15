// AWS CLI output shaping: a minimal JMESPath subset for `--query`, ASCII
// renderers for `--output table|text`, generic `--filters` matching for
// describe-instances, and a `--dry-run` sentinel.
//
// Scope is intentionally small (portfolio simulation) but covers the shapes the
// real CLI is used with day-to-day:
//   --query supports  a.b.c        (dotted paths, incl. into arrays -> projection)
//                     a[]          (flatten/projection over a list)
//                     a[0]         (index)
//                     a[?k==`v`]   (filter projection; quotes optional)
//                     a.b[].c      (chained projection)
//   --output json (default) | table | text
//
// The main awsCli() calls applyOutput() as a post-processing pass on the JSON
// result string right before returning.

// ---------------- JMESPath subset ----------------

// Split a query on top-level dots, keeping bracket groups intact.
function splitPath(expr) {
  const parts = []
  let buf = ''
  let depth = 0
  for (let i = 0; i < expr.length; i += 1) {
    const ch = expr[i]
    if (ch === '[') depth += 1
    if (ch === ']') depth -= 1
    if (ch === '.' && depth === 0) { parts.push(buf); buf = '' } else buf += ch
  }
  if (buf !== '') parts.push(buf)
  return parts
}

// Parse a bracket suffix on an identifier segment, e.g. `Reservations[]`,
// `Instances[0]`, `Tags[?Key==\`Name\`]`. Returns { key, brackets: [...] }.
function parseSegment(seg) {
  const brackets = []
  const m = seg.match(/^([^[]*)/)
  const key = m ? m[1] : seg
  const rest = seg.slice(key.length)
  const re = /\[([^\]]*)\]/g
  let bm
  while ((bm = re.exec(rest)) != null) brackets.push(bm[1].trim())
  return { key, brackets }
}

function stripQuotes(v) {
  const s = String(v).trim()
  if ((s.startsWith('`') && s.endsWith('`')) || (s.startsWith("'") && s.endsWith("'")) || (s.startsWith('"') && s.endsWith('"'))) {
    return s.slice(1, -1)
  }
  return s
}

// Coerce a filter literal to compare loosely against JSON values.
function looseEq(a, b) {
  if (a === b) return true
  const bs = stripQuotes(b)
  if (String(a) === bs) return true
  if (bs === 'true' && a === true) return true
  if (bs === 'false' && a === false) return true
  if (bs === 'null' && a == null) return true
  const an = Number(a)
  const bn = Number(bs)
  if (!Number.isNaN(an) && !Number.isNaN(bn) && an === bn) return true
  return false
}

// Apply one `[...]` bracket op to a value.
function applyBracket(value, inner) {
  if (inner === '') {
    // Flatten/projection: if array, keep; if scalar, wrap.
    return Array.isArray(value) ? value : (value == null ? [] : [value])
  }
  // Filter expression [?field==`value`] or [?field!=`value`]
  const fm = inner.match(/^\?\s*([^=!]+?)\s*(==|!=)\s*(.+)$/)
  if (fm) {
    const list = Array.isArray(value) ? value : (value == null ? [] : [value])
    const [, field, op, rawLit] = fm
    return list.filter((item) => {
      const got = resolvePath(item, field.trim())
      const eq = looseEq(got, rawLit)
      return op === '==' ? eq : !eq
    })
  }
  // Numeric index
  if (/^-?\d+$/.test(inner)) {
    if (!Array.isArray(value)) return undefined
    const idx = Number(inner)
    return idx < 0 ? value[value.length + idx] : value[idx]
  }
  return value
}

// Resolve a full dotted/bracketed path against `root`. Handles projection: once
// a segment yields an array via `[]`, subsequent key lookups map over it.
function resolvePath(root, expr) {
  if (!expr || expr === '@') return root
  const segments = splitPath(expr)
  let cur = root
  let projected = false
  for (const seg of segments) {
    const { key, brackets } = parseSegment(seg)
    if (key) {
      if (projected && Array.isArray(cur)) {
        cur = cur.map((el) => (el == null ? undefined : el[key]))
      } else {
        cur = cur == null ? undefined : cur[key]
      }
    }
    for (const b of brackets) {
      const isFilter = b.startsWith('?')
      if (projected && Array.isArray(cur) && b === '') {
        // flatten one level of an already-projected list of lists
        cur = cur.reduce((acc, el) => acc.concat(Array.isArray(el) ? el : (el == null ? [] : [el])), [])
      } else if (projected && Array.isArray(cur) && isFilter) {
        // A filter applies to the whole projected list, not per element.
        cur = applyBracket(cur, b)
      } else if (projected && Array.isArray(cur)) {
        // Index into each element of a projected list.
        cur = cur.map((el) => applyBracket(el, b))
      } else {
        cur = applyBracket(cur, b)
      }
      if (b === '' || isFilter) projected = true
    }
  }
  return cur
}

// Support a top-level multi-select list: `[a.b, c]`.
function runQuery(root, rawQuery) {
  const query = String(rawQuery).trim()
  if (query.startsWith('[') && query.endsWith(']') && query.includes(',') && !/^\[\]/.test(query) && !query.startsWith('[?') && !/^\[-?\d+\]$/.test(query)) {
    const inner = query.slice(1, -1)
    const exprs = splitTopLevel(inner, ',')
    return exprs.map((e) => resolvePath(root, e.trim()))
  }
  return resolvePath(root, query)
}

function splitTopLevel(s, sep) {
  const out = []
  let buf = ''
  let depth = 0
  for (const ch of s) {
    if (ch === '[' || ch === '(') depth += 1
    if (ch === ']' || ch === ')') depth -= 1
    if (ch === sep && depth === 0) { out.push(buf); buf = '' } else buf += ch
  }
  out.push(buf)
  return out
}

// ---------------- Output renderers ----------------

function scalarText(v) {
  if (v == null) return 'None'
  if (typeof v === 'boolean') return v ? 'True' : 'False'
  return String(v)
}

// `--output text`: tab-separated rows, arrays/objects flattened depth-first.
function renderText(value) {
  const rows = []
  const walk = (v) => {
    if (Array.isArray(v)) { v.forEach(walk); return }
    if (v && typeof v === 'object') {
      rows.push(Object.keys(v).sort().map((k) => scalarText(v[k])).join('\t'))
      return
    }
    rows.push(scalarText(v))
  }
  if (Array.isArray(value)) value.forEach(walk)
  else walk(value)
  return rows.join('\n')
}

// `--output table`: fixed-width ASCII table like the real CLI.
function renderTable(value) {
  let list
  if (Array.isArray(value)) list = value
  else if (value && typeof value === 'object') list = [value]
  else return String(scalarText(value))

  const objRows = list.filter((r) => r && typeof r === 'object' && !Array.isArray(r))
  if (!objRows.length) {
    // list of scalars -> single-column table
    const cells = list.map((v) => scalarText(v))
    const w = Math.max(1, ...cells.map((c) => c.length))
    const bar = `+${'-'.repeat(w + 2)}+`
    return [bar, ...cells.map((c) => `| ${c.padEnd(w)} |`), bar].join('\n')
  }
  const cols = []
  for (const r of objRows) for (const k of Object.keys(r)) if (!cols.includes(k)) cols.push(k)
  const widths = cols.map((c) => Math.max(c.length, ...objRows.map((r) => scalarText(r[c]).length)))
  const sep = `+${widths.map((w) => '-'.repeat(w + 2)).join('+')}+`
  const line = (cells) => `| ${cells.map((c, i) => scalarText(c).padEnd(widths[i])).join(' | ')} |`
  const out = [sep, line(cols), sep.replace(/-/g, '=').replace(/\+/g, '|')]
  for (const r of objRows) out.push(line(cols.map((c) => r[c])))
  out.push(sep)
  return out.join('\n')
}

// ---------------- Public API ----------------

// Post-process a JSON result string with --query / --output / --no-cli-pager.
// Non-JSON strings (AWS error lines, high-level `s3` output) pass through
// unchanged unless a query is requested against parseable JSON.
export function applyOutput(resultString, flags) {
  const wantsQuery = flags.query && typeof flags.query === 'string'
  const output = typeof flags.output === 'string' ? flags.output : null
  if (!wantsQuery && !output) return resultString

  let parsed
  try { parsed = JSON.parse(resultString) } catch { return resultString }

  let value = parsed
  if (wantsQuery) value = runQuery(parsed, flags.query)

  if (output === 'text') return renderText(value)
  if (output === 'table') return renderTable(value)
  // Default JSON: queried scalars print raw, structures pretty-print.
  if (wantsQuery) {
    if (value == null) return 'null'
    if (typeof value !== 'object') return String(value)
  }
  return JSON.stringify(value, null, 4)
}

// ---------------- --filters (describe-instances) ----------------

// Parse the CLI `Name=key,Values=v1,v2` filter syntax into { name, values }.
// Multiple --filters are joined into one string with spaces by the shell split;
// support both a single filter and a space-joined list.
export function parseFilters(raw) {
  if (!raw || raw === true) return []
  const chunks = String(raw).trim().split(/\s+/)
  const out = []
  for (const chunk of chunks) {
    const nameM = chunk.match(/Name=([^,]+)/)
    const valsM = chunk.match(/Values=(.+)$/)
    if (!nameM) continue
    out.push({ name: nameM[1], values: valsM ? valsM[1].split(',') : [] })
  }
  return out
}

// Does one instance (store shape) match a single filter?
function instanceMatchesFilter(inst, filter) {
  const { name, values } = filter
  const has = (v) => values.length === 0 || values.some((pat) => matchGlob(pat, v))
  switch (name) {
    case 'instance-state-name': return has(inst.state)
    case 'instance-id': return has(inst.id)
    case 'instance-type': return has(inst.type)
    case 'availability-zone': return has(inst.az)
    case 'vpc-id': return has(inst.vpcId)
    case 'subnet-id': return has(inst.subnetId)
    case 'image-id': return has(inst.amiId)
    case 'key-name': return has(inst.keyName)
    default:
      if (name === 'tag-key') return Object.keys(inst.tags || {}).some((k) => has(k))
      if (name.startsWith('tag:')) {
        const key = name.slice(4)
        return has((inst.tags || {})[key])
      }
      return true // unknown filter -> non-restrictive
  }
}

function matchGlob(pattern, value) {
  const p = String(pattern)
  if (!p.includes('*') && !p.includes('?')) return String(value) === p
  const re = new RegExp(`^${p.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\?/g, '.')}$`)
  return re.test(String(value))
}

// Filter a list of store instances by all parsed filters (AND semantics).
export function filterInstances(instances, filters) {
  if (!filters.length) return instances
  return instances.filter((inst) => filters.every((f) => instanceMatchesFilter(inst, f)))
}

// ---------------- --dry-run ----------------

export const DRY_RUN_MESSAGE = (op) =>
  `\nAn error occurred (DryRunOperation) when calling the ${op} operation: Request would have succeeded, but DryRun flag is set.`
