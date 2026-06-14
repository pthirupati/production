import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  Terminal, Clock, ArrowRight, Tag, User, ChevronRight, BookOpen, Sparkles, TrendingUp,
} from 'lucide-react'
import api from '../api/client'
import { BLOG_FALLBACK_POSTS, BLOG_CATEGORIES, getCategoryClass } from '../data/blogFallback'

function mergePosts(apiPosts) {
  const bySlug = new Map()
  for (const p of BLOG_FALLBACK_POSTS) {
    bySlug.set(p.slug, { ...p })
  }
  for (const p of apiPosts || []) {
    bySlug.set(p.slug, { ...bySlug.get(p.slug), ...p })
  }
  return Array.from(bySlug.values()).sort((a, b) => {
    if (a.featured && !b.featured) return -1
    if (!a.featured && b.featured) return 1
    return 0
  })
}

export default function Blog() {
  const [posts, setPosts] = useState(BLOG_FALLBACK_POSTS)
  const [loading, setLoading] = useState(true)
  const [activeCategory, setActiveCategory] = useState('All')

  useEffect(() => {
    api.get('/blog/')
      .then(res => setPosts(mergePosts(res.data)))
      .catch(() => setPosts(BLOG_FALLBACK_POSTS))
      .finally(() => setLoading(false))
  }, [])

  const categories = useMemo(() => {
    const fromPosts = [...new Set(posts.map(p => p.category).filter(Boolean))]
    return ['All', ...BLOG_CATEGORIES.filter(c => c !== 'All' && fromPosts.includes(c)),
      ...fromPosts.filter(c => !BLOG_CATEGORIES.includes(c))]
  }, [posts])

  const filtered = useMemo(() => {
    if (activeCategory === 'All') return posts
    return posts.filter(p => p.category === activeCategory)
  }, [posts, activeCategory])

  const featured = filtered.find(p => p.featured) || filtered[0]
  const rest = filtered.filter(p => p.slug !== featured?.slug)

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 md:py-14 space-y-10">
      {/* Hero */}
      <div className="text-center space-y-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent-cyan/10 text-accent-cyan text-xs font-medium border border-accent-cyan/20">
          <Terminal size={14} /> FixitLab Blog
        </div>
        <h1 className="text-3xl md:text-5xl font-bold text-white tracking-tight">
          Engineering insights &amp; product updates
        </h1>
        <p className="text-surface-400 max-w-2xl mx-auto text-base md:text-lg leading-relaxed">
          Hands-on SRE playbooks, architecture deep dives, and platform news from the team building
          real troubleshooting labs for Linux, Kubernetes, cloud, and more.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-6 pt-2 text-sm text-surface-500">
          <span className="inline-flex items-center gap-1.5"><BookOpen size={15} /> {posts.length} articles</span>
          <span className="inline-flex items-center gap-1.5"><Tag size={15} /> {categories.length - 1} topics</span>
          <span className="inline-flex items-center gap-1.5"><TrendingUp size={15} /> Updated regularly</span>
        </div>
      </div>

      {/* Category tabs */}
      <div className="flex flex-wrap justify-center gap-2">
        {categories.map(cat => (
          <button
            key={cat}
            type="button"
            onClick={() => setActiveCategory(cat)}
            className={`px-4 py-2 rounded-full text-sm font-medium transition-all border ${
              activeCategory === cat
                ? 'bg-accent-cyan/15 text-accent-cyan border-accent-cyan/40'
                : 'bg-surface-900/50 text-surface-400 border-surface-700/50 hover:text-white hover:border-surface-600'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="glass-card p-12 text-center">
          <p className="text-surface-400">No posts in this category yet.</p>
          <button type="button" onClick={() => setActiveCategory('All')} className="btn-secondary mt-4 text-sm">
            View all posts
          </button>
        </div>
      )}

      {featured && (
        <Link
          to={`/blog/${featured.slug}`}
          className="block glass-card overflow-hidden group hover:ring-2 hover:ring-accent-cyan/30 transition-all"
        >
          <div className="p-8 md:p-10 md:flex md:gap-10 md:items-start">
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2 mb-3">
                <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-accent-amber/10 text-accent-amber border border-accent-amber/20">
                  Featured
                </span>
                <span className={`text-xs font-semibold uppercase tracking-wider px-2 py-0.5 rounded border ${getCategoryClass(featured.category)}`}>
                  {featured.category}
                </span>
              </div>
              <h2 className="text-2xl md:text-3xl font-bold text-white group-hover:text-accent-cyan transition-colors">
                {featured.title}
              </h2>
              <p className="text-surface-400 mt-3 max-w-2xl leading-relaxed">{featured.excerpt}</p>
              <div className="flex flex-wrap items-center gap-4 mt-6 text-sm text-surface-500">
                <span className="flex items-center gap-1"><User size={14} /> {featured.author}</span>
                <span>{featured.date}</span>
                <span className="flex items-center gap-1"><Clock size={14} /> {featured.readTime}</span>
              </div>
              <span className="inline-flex items-center gap-1 mt-5 text-accent-cyan text-sm font-medium">
                Read article <ArrowRight size={14} />
              </span>
            </div>
            <div className="hidden md:flex w-48 shrink-0 flex-col items-center justify-center glass-card p-6 mt-6 md:mt-0 bg-surface-900/40">
              <Sparkles className="text-accent-cyan mb-2" size={28} />
              <p className="text-xs text-surface-500 text-center">Practice what you read in a live lab</p>
              <Link to="/register" onClick={e => e.stopPropagation()} className="btn-primary text-xs mt-3 px-4 py-2">
                Start free
              </Link>
            </div>
          </div>
        </Link>
      )}

      {rest.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            {activeCategory === 'All' ? 'All articles' : `${activeCategory} articles`}
            <span className="text-sm font-normal text-surface-500">({rest.length})</span>
          </h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {rest.map(post => (
              <Link
                key={post.slug}
                to={`/blog/${post.slug}`}
                className="glass-card p-6 group hover:ring-1 hover:ring-accent-cyan/20 transition-all flex flex-col h-full"
              >
                <span className={`inline-flex self-start text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${getCategoryClass(post.category)}`}>
                  {post.category}
                </span>
                <h3 className="text-lg font-semibold text-white mt-3 group-hover:text-accent-cyan transition-colors leading-snug">
                  {post.title}
                </h3>
                <p className="text-sm text-surface-400 mt-2 line-clamp-3 flex-1 leading-relaxed">{post.excerpt}</p>
                <div className="flex items-center justify-between mt-5 pt-4 border-t border-surface-800/50 text-xs text-surface-500">
                  <span className="flex items-center gap-1"><User size={12} /> {post.author}</span>
                  <span className="flex items-center gap-1">{post.readTime} <ChevronRight size={14} className="text-surface-600 group-hover:text-accent-cyan" /></span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* CTA */}
      <div className="glass-card p-8 md:p-10 text-center relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/5 to-accent-purple/5 pointer-events-none" />
        <div className="relative max-w-xl mx-auto">
          <h2 className="text-xl md:text-2xl font-bold text-white mb-2">Ready to practice?</h2>
          <p className="text-surface-400 text-sm md:text-base mb-6">
            Stop reading docs — break things safely in real Docker, cloud, and simulated RHEL environments.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link to="/register" className="btn-primary px-6 py-2.5 text-sm">Get started free</Link>
            <Link to="/scenarios" className="btn-secondary px-6 py-2.5 text-sm">Browse scenarios</Link>
          </div>
        </div>
      </div>
    </div>
  )
}
