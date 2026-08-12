import { describe, it, expect } from 'vitest'
import {
  buildFileTree, parentDirs, stubContentForPath, newFileHint, newFileBasename, fileBasename,
} from './fileTree'
import { preferredHtmlPath } from './composeHtmlPreview'

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

  describe('newFileBasename', () => {
    // Regression: IdeExplorer used to substring-match `.includes('java')`
    // BEFORE its js branch, so 'javascript' labs offered Main.java.
    it('does not mistake javascript for java', () => {
      expect(newFileBasename('javascript')).toBe('module.js')
      expect(newFileBasename('java')).toBe('Main.java')
    })

    it('returns a bare basename with no directory prefix', () => {
      Object.keys({
        python: 1, javascript: 1, typescript: 1, java: 1, html: 1, bash: 1, hcl: 1, cobol: 1,
      }).forEach((lang) => {
        expect(newFileBasename(lang)).not.toContain('/')
      })
    })

    it('names html files so the preview composer will actually pick them up', () => {
      const name = newFileBasename('html')
      expect(preferredHtmlPath({ [name]: '' })).toBe(name)
      // index.html wins over any other html doc, so a new file must be index.html
      // or it silently loses the preview to a pre-existing index.html.
      expect(preferredHtmlPath({ [name]: '', 'index.html': '' })).toBe(name)
    })

    it('gives Terraform/Packer explorers a .tf name, not untitled.txt', () => {
      expect(newFileBasename('hcl')).toBe('module.tf')
      // main.tf is in their protectedPaths and always already exists.
      expect(newFileBasename('hcl')).not.toBe('main.tf')
    })

    it('newFileHint is the same name plus the src/ prefix', () => {
      ['python', 'javascript', 'java', 'html', 'bash', 'hcl', 'zzz'].forEach((lang) => {
        expect(newFileHint(lang, [])).toBe(newFileBasename(lang))
        expect(newFileHint(lang, ['src/a.txt'])).toBe(`src/${newFileBasename(lang)}`)
      })
    })
  })
})
