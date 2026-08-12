import { describe, it, expect } from 'vitest'
import {
  blogPostingSchema,
  breadcrumbSchema,
  scenarioCourseSchema,
} from './useStructuredData'

describe('structured data builders (Z6-7)', () => {
  it('blogPostingSchema emits BlogPosting with headline and dates', () => {
    const data = blogPostingSchema({
      title: 'How GPU labs work',
      slug: 'gpu-labs',
      excerpt: 'A short guide',
      published_at: '2026-08-01T00:00:00Z',
      updated_at: '2026-08-02T00:00:00Z',
      author: 'FixitLab Team',
      category: 'Engineering',
    })
    expect(data).toMatchObject({
      '@type': 'BlogPosting',
      headline: 'How GPU labs work',
      description: 'A short guide',
      datePublished: '2026-08-01T00:00:00Z',
      dateModified: '2026-08-02T00:00:00Z',
      articleSection: 'Engineering',
    })
    expect(data.url).toContain('/blog/gpu-labs')
    expect(data.mainEntityOfPage['@type']).toBe('WebPage')
    expect(data.publisher['@type']).toBe('Organization')
  })

  it('blogPostingSchema is null-safe', () => {
    expect(blogPostingSchema(null)).toBeNull()
    expect(blogPostingSchema({ title: 'No slug' })).toBeNull()
  })

  it('breadcrumbSchema still requires two items', () => {
    expect(breadcrumbSchema([{ name: 'Only' }])).toBeNull()
    const trail = breadcrumbSchema([
      { name: 'Home', path: '/' },
      { name: 'Blog', path: '/blog' },
      { name: 'Post' },
    ])
    expect(trail.itemListElement).toHaveLength(3)
    expect(trail.itemListElement[2]).toEqual({
      '@type': 'ListItem',
      position: 3,
      name: 'Post',
    })
  })

  it('scenarioCourseSchema still includes CourseInstance', () => {
    const course = scenarioCourseSchema({
      title: 'Fix the GPU',
      slug: 'fix-gpu',
      time_limit: 1200,
      technology: { name: 'AI Infra' },
    })
    expect(course.hasCourseInstance['@type']).toBe('CourseInstance')
    expect(course.hasCourseInstance.courseWorkload).toBe('PT20M')
  })
})
