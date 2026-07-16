/*
 * In-browser git simulation for the client-side Linux shell (VMware guests,
 * EC2 SSH sessions, CloudShell). Backs a realistic subset of git against the
 * shell's virtual file system: init/clone, status/add/commit, branches,
 * checkout/switch/merge, diff, log, remotes, push/pull, stash, reset, tag,
 * rm/mv/restore — enough to solve every git-based lab scenario.
 *
 * State model (per repo root, kept in the shell-session `repos` map):
 *   branch    current branch name
 *   branches  { name: [ {hash, msg, ts, author, files} ] }  commit lists
 *   trees     { name: { relpath: content } }   worktree snapshot at branch HEAD
 *   index     { relpath: content }             staged snapshot
 *   remotes   { name: url }
 *   stash     [ { msg, files } ]
 *   config    { 'user.name': ..., 'user.email': ... }
 */

function hashOf(str) {
  let h = 5381
  for (let i = 0; i < str.length; i++) h = ((h << 5) + h + str.charCodeAt(i)) >>> 0
  return (h.toString(16) + Math.abs((h * 2654435761) >>> 0).toString(16)).slice(0, 7)
}

function shortDate(ts) {
  return new Date(ts).toString().replace(/ GMT.*$/, ' ') + '+0000'
}

// Tokenize respecting single/double quotes so `git commit -m "my msg"` works.
export function tokenizeGit(line) {
  const tokens = []
  const re = /"([^"]*)"|'([^']*)'|(\S+)/g
  let m
  while ((m = re.exec(line)) !== null) tokens.push(m[1] ?? m[2] ?? m[3])
  return tokens
}

function newRepo() {
  return {
    branch: 'main',
    branches: { main: [] },
    trees: { main: {} },
    index: {},
    remotes: {},
    stash: [],
    config: {},
  }
}

function findRepoRoot(repos, path) {
  let p = path
  while (true) {
    if (repos[p]) return p
    if (p === '/' || !p) return null
    p = p.replace(/\/[^/]*$/, '') || '/'
  }
}

function walkFiles(vfs, root) {
  const files = {}
  const rootNode = vfs.resolveNode(root)
  if (!rootNode || rootNode.type !== 'dir') return files
  const visit = (node, rel) => {
    for (const [name, child] of Object.entries(node.children || {})) {
      if (name === '.git') continue
      const childRel = rel ? `${rel}/${name}` : name
      if (child.type === 'dir') visit(child, childRel)
      else if (child.type === 'file') files[childRel] = child.content ?? ''
    }
  }
  visit(rootNode, '')
  return files
}

function changesVs(tree, files) {
  const modified = []
  const untracked = []
  const deleted = []
  for (const [rel, content] of Object.entries(files)) {
    if (!(rel in tree)) untracked.push(rel)
    else if (tree[rel] !== content) modified.push(rel)
  }
  for (const rel of Object.keys(tree)) if (!(rel in files)) deleted.push(rel)
  return { modified, untracked, deleted }
}

export function createGitSim({ vfs, cwd, abs, username = 'root' }) {
  const repos = {}

  const wt = (root) => walkFiles(vfs, root)

  const author = (repo) => repo.config['user.name'] || username

  function commitObj(repo, msg, files) {
    const ts = Date.now()
    return { hash: hashOf(msg + ts + Math.random()), msg, ts, author: author(repo), files }
  }

  function restoreTree(root, tree) {
    // Write branch tree files into the VFS worktree (checkout semantics).
    const current = wt(root)
    for (const rel of Object.keys(current)) {
      if (!(rel in tree)) {
        const node = vfs.resolveNode(root)
        // remove file node
        const parts = rel.split('/')
        let dir = node
        for (let i = 0; i < parts.length - 1 && dir; i++) dir = dir.children?.[parts[i]]
        if (dir && dir.children) delete dir.children[parts[parts.length - 1]]
      }
    }
    for (const [rel, content] of Object.entries(tree)) {
      vfs.writeFile(`${root}/${rel}`.replace(/\/+/g, '/'), content)
    }
  }

  function run(line) {
    const tokens = tokenizeGit(line)
    const rest = tokens.slice(1) // drop "git"
    const sub = rest[0]
    const args = rest.slice(1)

    if (!sub || sub === 'help' || sub === '--help') {
      return [
        'usage: git <command> [<args>]',
        '',
        'Common commands: init clone config status add commit log branch',
        '                 checkout switch merge diff remote push pull fetch',
        '                 stash reset tag show rm mv restore',
      ]
    }
    if (sub === '--version') return ['git version 2.43.5']

    if (sub === 'init') {
      const target = args[0] ? abs(args[0]) : cwd.path
      vfs.writeFile(`${target}/.git/HEAD`.replace(/\/+/g, '/'), 'ref: refs/heads/main\n')
      if (!repos[target]) repos[target] = newRepo()
      return [`Initialized empty Git repository in ${target}/.git/`]
    }

    if (sub === 'clone') {
      const url = args.find((a) => !a.startsWith('-')) || ''
      if (!url) return ['fatal: You must specify a repository to clone.']
      const name = args[args.indexOf(url) + 1] && !args[args.indexOf(url) + 1].startsWith('-')
        ? args[args.indexOf(url) + 1]
        : url.replace(/\.git$/, '').split('/').pop()
      const target = abs(name)
      const repo = newRepo()
      repo.remotes.origin = url
      const readme = `# ${name}\n\nCloned from ${url} in the FixItLab lab environment.\n`
      const appFile = '#!/usr/bin/env python3\nprint("hello from ' + name + '")\n'
      vfs.writeFile(`${target}/README.md`, readme)
      vfs.writeFile(`${target}/app.py`, appFile)
      vfs.writeFile(`${target}/.git/HEAD`, 'ref: refs/heads/main\n')
      repo.trees.main = { 'README.md': readme, 'app.py': appFile }
      repo.branches.main = [commitObj(repo, 'Initial commit', ['README.md', 'app.py'])]
      repos[target] = repo
      return [
        `Cloning into '${name}'...`,
        'remote: Enumerating objects: 6, done.',
        'remote: Total 6 (delta 0), reused 6 (delta 0), pack-reused 0',
        'Receiving objects: 100% (6/6), 1.21 KiB | 1.21 MiB/s, done.',
      ]
    }

    const root = findRepoRoot(repos, cwd.path)
    if (sub === 'config') {
      const global = args.includes('--global')
      const kv = args.filter((a) => !a.startsWith('-'))
      const repo = root ? repos[root] : null
      if (args.includes('--list') || args.includes('-l')) {
        const conf = repo ? repo.config : {}
        return Object.entries(conf).map(([k, v]) => `${k}=${v}`)
      }
      if (kv.length >= 2) {
        if (repo) repo.config[kv[0]] = kv.slice(1).join(' ')
        else if (global) {
          // allow global config outside a repo (no-op storage)
          return ['']
        }
        return ['']
      }
      if (kv.length === 1 && repo) return [repo.config[kv[0]] || '']
      return ['']
    }

    if (!root) return [`fatal: not a git repository (or any of the parent directories): .git`]
    const repo = repos[root]
    const tree = repo.trees[repo.branch] || {}
    const files = wt(root)
    const relOf = (p) => {
      const a = abs(p)
      return a === root ? '.' : a.startsWith(root + '/') ? a.slice(root.length + 1) : p
    }

    switch (sub) {
      case 'status': {
        const { modified, untracked, deleted } = changesVs(tree, files)
        const staged = Object.keys(repo.index).filter(
          (rel) => repo.index[rel] !== tree[rel] || !(rel in tree),
        )
        const lines = [`On branch ${repo.branch}`]
        if (staged.length) {
          lines.push('', 'Changes to be committed:', '  (use "git restore --staged <file>..." to unstage)')
          staged.forEach((f) => lines.push(`\tnew file:   ${f}`))
        }
        const unstagedMods = modified.filter((f) => repo.index[f] !== files[f])
        if (unstagedMods.length || deleted.length) {
          lines.push('', 'Changes not staged for commit:', '  (use "git add <file>..." to update what will be committed)')
          unstagedMods.forEach((f) => lines.push(`\tmodified:   ${f}`))
          deleted.forEach((f) => lines.push(`\tdeleted:    ${f}`))
        }
        const untrackedNew = untracked.filter((f) => !(f in repo.index))
        if (untrackedNew.length) {
          lines.push('', 'Untracked files:', '  (use "git add <file>..." to include in what will be committed)')
          untrackedNew.forEach((f) => lines.push(`\t${f}`))
        }
        if (lines.length === 1) lines.push('nothing to commit, working tree clean')
        return lines
      }

      case 'add': {
        const targets = args.filter((a) => !a.startsWith('-'))
        const all = args.includes('-A') || args.includes('--all') || targets.includes('.')
        if (all) {
          for (const [rel, content] of Object.entries(files)) repo.index[rel] = content
        } else {
          for (const t of targets) {
            const rel = relOf(t)
            if (rel in files) repo.index[rel] = files[rel]
            else return [`fatal: pathspec '${t}' did not match any files`]
          }
        }
        return ['']
      }

      case 'commit': {
        const mi = args.indexOf('-m')
        const msg = mi !== -1 ? args[mi + 1] || '' : ''
        if (!msg) return ['Aborting commit due to empty commit message.']
        if (args.includes('-a') || args.includes('-am')) {
          for (const [rel, content] of Object.entries(files)) {
            if (rel in tree) repo.index[rel] = content
          }
        }
        const changed = Object.keys(repo.index).filter(
          (rel) => repo.index[rel] !== tree[rel] || !(rel in tree),
        )
        if (!changed.length) return [`On branch ${repo.branch}`, 'nothing to commit, working tree clean']
        const c = commitObj(repo, msg, changed)
        repo.branches[repo.branch] = [...(repo.branches[repo.branch] || []), c]
        repo.trees[repo.branch] = { ...tree, ...repo.index }
        repo.index = {}
        return [
          `[${repo.branch} ${c.hash}] ${msg}`,
          ` ${changed.length} file${changed.length === 1 ? '' : 's'} changed`,
        ]
      }

      case 'log': {
        const commits = [...(repo.branches[repo.branch] || [])].reverse()
        if (!commits.length) return [`fatal: your current branch '${repo.branch}' does not have any commits yet`]
        if (args.includes('--oneline')) return commits.map((c) => `${c.hash} ${c.msg}`)
        const lines = []
        commits.forEach((c) => {
          lines.push(`commit ${c.hash}${c === commits[0] ? ` (HEAD -> ${repo.branch})` : ''}`)
          lines.push(`Author: ${c.author} <${repo.config['user.email'] || 'root@localhost'}>`)
          lines.push(`Date:   ${shortDate(c.ts)}`)
          lines.push('', `    ${c.msg}`, '')
        })
        return lines
      }

      case 'branch': {
        const names = args.filter((a) => !a.startsWith('-'))
        if (args.includes('-d') || args.includes('-D')) {
          const name = names[0]
          if (!repo.branches[name]) return [`error: branch '${name}' not found.`]
          if (name === repo.branch) return [`error: Cannot delete branch '${name}' checked out`]
          delete repo.branches[name]
          delete repo.trees[name]
          return [`Deleted branch ${name}.`]
        }
        if (names.length) {
          const name = names[0]
          if (repo.branches[name]) return [`fatal: a branch named '${name}' already exists`]
          repo.branches[name] = [...(repo.branches[repo.branch] || [])]
          repo.trees[name] = { ...tree }
          return ['']
        }
        return Object.keys(repo.branches).sort().map((b) => (b === repo.branch ? `* ${b}` : `  ${b}`))
      }

      case 'checkout':
      case 'switch': {
        const create = args.includes('-b') || args.includes('-c')
        const names = args.filter((a) => !a.startsWith('-'))
        const name = names[0]
        if (!name) return ['fatal: missing branch name']
        // checkout -- <file> restores from HEAD
        if (args.includes('--') && !create) {
          const rel = relOf(names[names.length - 1])
          if (rel in tree) {
            vfs.writeFile(`${root}/${rel}`, tree[rel])
            return ['']
          }
          return [`error: pathspec '${name}' did not match any file(s) known to git`]
        }
        if (create) {
          if (repo.branches[name]) return [`fatal: a branch named '${name}' already exists`]
          repo.branches[name] = [...(repo.branches[repo.branch] || [])]
          repo.trees[name] = { ...tree }
          repo.branch = name
          return [`Switched to a new branch '${name}'`]
        }
        if (!repo.branches[name]) return [`error: pathspec '${name}' did not match any file(s) known to git`]
        repo.branch = name
        restoreTree(root, repo.trees[name] || {})
        return [`Switched to branch '${name}'`]
      }

      case 'merge': {
        const name = args.find((a) => !a.startsWith('-'))
        if (!name || !repo.branches[name]) return [`merge: ${name || ''} - not something we can merge`]
        const ours = repo.branches[repo.branch] || []
        const theirs = repo.branches[name] || []
        if (theirs.length <= ours.length) return ['Already up to date.']
        const newCommits = theirs.slice(ours.length)
        repo.branches[repo.branch] = [...theirs]
        repo.trees[repo.branch] = { ...repo.trees[name] }
        restoreTree(root, repo.trees[repo.branch])
        return [
          `Updating ${ours.length ? ours[ours.length - 1].hash : '0000000'}..${theirs[theirs.length - 1].hash}`,
          'Fast-forward',
          ` ${newCommits.length} commit${newCommits.length === 1 ? '' : 's'} applied`,
        ]
      }

      case 'diff': {
        const staged = args.includes('--staged') || args.includes('--cached')
        const base = tree
        const target = staged ? repo.index : files
        const lines = []
        for (const [rel, content] of Object.entries(target)) {
          if (staged && content === base[rel]) continue
          if (!staged && content === base[rel]) continue
          if (!(rel in base) && !staged) continue // untracked not shown by diff
          lines.push(`diff --git a/${rel} b/${rel}`)
          lines.push(`--- a/${rel}`, `+++ b/${rel}`)
          const oldLines = (base[rel] || '').split('\n')
          const newLines = (content || '').split('\n')
          oldLines.filter((l) => !newLines.includes(l)).forEach((l) => lines.push(`-${l}`))
          newLines.filter((l) => !oldLines.includes(l)).forEach((l) => lines.push(`+${l}`))
        }
        return lines.length ? lines : ['']
      }

      case 'remote': {
        if (args[0] === 'add' && args.length >= 3) {
          repo.remotes[args[1]] = args[2]
          return ['']
        }
        if (args[0] === 'remove' && args[1]) {
          delete repo.remotes[args[1]]
          return ['']
        }
        if (args.includes('-v')) {
          return Object.entries(repo.remotes).flatMap(([n, u]) => [`${n}\t${u} (fetch)`, `${n}\t${u} (push)`])
        }
        return Object.keys(repo.remotes)
      }

      case 'push': {
        const remote = args.find((a) => !a.startsWith('-')) || 'origin'
        const url = repo.remotes[remote]
        if (!url) return [`fatal: '${remote}' does not appear to be a git repository`]
        const commits = repo.branches[repo.branch] || []
        const tip = commits.length ? commits[commits.length - 1].hash : '0000000'
        return [
          `Enumerating objects: ${commits.length * 3}, done.`,
          `Counting objects: 100% (${commits.length * 3}/${commits.length * 3}), done.`,
          `Writing objects: 100% (${commits.length * 3}/${commits.length * 3}), 1.22 KiB | 1.2 MiB/s, done.`,
          `To ${url}`,
          `   ${hashOf(url)}..${tip}  ${repo.branch} -> ${repo.branch}`,
        ]
      }

      case 'pull':
        return ['Already up to date.']
      case 'fetch':
        return ['']

      case 'stash': {
        const op = args[0] || 'push'
        if (op === 'list') {
          return repo.stash.map((s, i) => `stash@{${i}}: WIP on ${repo.branch}: ${s.msg}`)
        }
        if (op === 'pop' || op === 'apply') {
          if (!repo.stash.length) return ['No stash entries found.']
          const entry = op === 'apply' ? repo.stash[repo.stash.length - 1] : repo.stash.pop()
          for (const [rel, content] of Object.entries(entry.files)) vfs.writeFile(`${root}/${rel}`, content)
          return [`On branch ${repo.branch}`, 'Changes restored from stash.']
        }
        // push (default): stash dirty files, restore HEAD tree
        const { modified } = changesVs(tree, files)
        if (!modified.length) return ['No local changes to save']
        const entry = { msg: 'local changes', files: {} }
        for (const rel of modified) {
          entry.files[rel] = files[rel]
          vfs.writeFile(`${root}/${rel}`, tree[rel])
        }
        repo.stash.push(entry)
        return [`Saved working directory and index state WIP on ${repo.branch}`]
      }

      case 'reset': {
        const commits = repo.branches[repo.branch] || []
        if (args.includes('HEAD~1') && commits.length) {
          const dropped = commits.pop()
          if (args.includes('--hard')) restoreTree(root, tree)
          return [`HEAD is now at ${commits.length ? commits[commits.length - 1].hash : '0000000'}${dropped ? ` (dropped ${dropped.msg})` : ''}`]
        }
        repo.index = {}
        if (args.includes('--hard')) restoreTree(root, tree)
        return ['']
      }

      case 'revert': {
        const commits = repo.branches[repo.branch] || []
        if (!commits.length) return ['fatal: bad revision']
        const last = commits[commits.length - 1]
        const c = commitObj(repo, `Revert "${last.msg}"`, last.files)
        repo.branches[repo.branch].push(c)
        return [`[${repo.branch} ${c.hash}] Revert "${last.msg}"`]
      }

      case 'tag': {
        repo.tags = repo.tags || []
        const names = args.filter((a) => !a.startsWith('-'))
        if (!names.length) return repo.tags
        repo.tags.push(names[0])
        return ['']
      }

      case 'show': {
        const commits = repo.branches[repo.branch] || []
        if (!commits.length) return ['fatal: bad revision']
        const c = commits[commits.length - 1]
        return [
          `commit ${c.hash} (HEAD -> ${repo.branch})`,
          `Author: ${c.author}`,
          `Date:   ${shortDate(c.ts)}`,
          '',
          `    ${c.msg}`,
        ]
      }

      case 'rm': {
        const targets = args.filter((a) => !a.startsWith('-'))
        for (const t of targets) {
          const rel = relOf(t)
          if (!(rel in files) && !(rel in tree)) return [`fatal: pathspec '${t}' did not match any files`]
          delete repo.index[rel]
          const parts = rel.split('/')
          let dir = vfs.resolveNode(root)
          for (let i = 0; i < parts.length - 1 && dir; i++) dir = dir.children?.[parts[i]]
          if (dir && dir.children) delete dir.children[parts[parts.length - 1]]
        }
        return targets.map((t) => `rm '${relOf(t)}'`)
      }

      case 'mv': {
        const [from, to] = args.filter((a) => !a.startsWith('-'))
        const relFrom = relOf(from)
        if (!(relFrom in files)) return [`fatal: bad source, source=${from}`]
        vfs.writeFile(`${root}/${relOf(to)}`, files[relFrom])
        const parts = relFrom.split('/')
        let dir = vfs.resolveNode(root)
        for (let i = 0; i < parts.length - 1 && dir; i++) dir = dir.children?.[parts[i]]
        if (dir && dir.children) delete dir.children[parts[parts.length - 1]]
        return ['']
      }

      case 'restore': {
        const staged = args.includes('--staged')
        const targets = args.filter((a) => !a.startsWith('-'))
        for (const t of targets) {
          const rel = t === '.' ? null : relOf(t)
          if (staged) {
            if (rel === null) repo.index = {}
            else delete repo.index[rel]
          } else if (rel === null) {
            restoreTree(root, tree)
          } else if (rel in tree) {
            vfs.writeFile(`${root}/${rel}`, tree[rel])
          }
        }
        return ['']
      }

      default:
        return [`git: '${sub}' is not a git command. See 'git --help'.`]
    }
  }

  return { run }
}
