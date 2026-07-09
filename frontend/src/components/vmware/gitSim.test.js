import { describe, it, expect } from 'vitest'
import { createGitSim, tokenizeGit } from './gitSim.js'

function mkVfs() {
  const root = { type: 'dir', children: {} }
  const resolveNode = (path) => {
    if (path === '/') return root
    let node = root
    for (const part of path.split('/').filter(Boolean)) {
      if (!node.children?.[part]) return null
      node = node.children[part]
    }
    return node
  }
  const writeFile = (path, content) => {
    const parts = path.split('/').filter(Boolean)
    let node = root
    for (const p of parts.slice(0, -1)) {
      if (!node.children[p]) node.children[p] = { type: 'dir', children: {} }
      node = node.children[p]
    }
    node.children[parts[parts.length - 1]] = { type: 'file', content }
  }
  return { resolveNode, writeFile }
}

describe('gitSim', () => {
  it('tokenizes quoted commit messages', () => {
    const t = tokenizeGit('git commit -m "first commit"')
    expect(t).toEqual(['git', 'commit', '-m', 'first commit'])
  })

  it('runs init and commit workflow', () => {
    const vfs = mkVfs()
    const cwd = { path: '/repo' }
    vfs.writeFile('/repo/.keep', '')
    const abs = (p) => (p.startsWith('/') ? p : `/repo/${p}`)
    const git = createGitSim({ vfs, cwd, abs })
    git.run('git init')
    vfs.writeFile('/repo/app.py', 'print(1)\n')
    git.run('git add .')
    const out = git.run('git commit -m "init"')
    expect(out.some((l) => l.includes('[main'))).toBe(true)
  })
})
