import { describe, it, expect } from 'vitest'
import { buildFileTree, parentDirs, stubContentForPath, newFileHint, fileBasename } from './fileTree'

describe('fileTree', () => {
  it('builds nested dirs and keeps empty folders from .keep markers', () => {
    const tree = buildFileTree({
      'src/app.js': 'x',
      'src/utils/helpers.js': 'y',
      'src/utils/.keep': '',
      'empty/dir/.keep': '',
      'README.md': '# hi',
    })
    expect(Object.keys(tree.children).sort()).toEqual(['empty', 'src'])
    expect(tree.files).toEqual(['README.md'])
    expect(tree.children.src.files).toEqual(['src/app.js'])
    expect(tree.children.src.children.utils.files).toEqual(['src/utils/helpers.js'])
    expect(tree.children.empty.children.dir.files).toEqual([])
  })

  it('parentDirs and basename', () => {
    expect(parentDirs('a/b/c.js')).toEqual(['a', 'a/b'])
    expect(fileBasename('a/b/c.js')).toBe('c.js')
  })

  it('stubs and hints', () => {
    expect(stubContentForPath('Main.java')).toContain('class Main')
    expect(newFileHint('python', ['src/x.py'])).toBe('src/module.py')
  })
})
