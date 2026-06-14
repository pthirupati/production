import { Link } from 'react-router-dom'

/** Static catalog when API is empty — mirrors seeded CMS posts + common articles. */
export const BLOG_FALLBACK_POSTS = [
  {
    slug: 'teams-coupons-and-security',
    title: "Teams, Coupons, and Platform Security — What's New",
    excerpt: 'Enterprise seat licensing, checkout coupon codes, admin security dashboards, and community threads with screenshot attachments.',
    category: 'Product',
    author: 'Platform Team',
    date: 'June 5, 2026',
    readTime: '4 min read',
    featured: true,
  },
  {
    slug: 'why-hands-on-learning-works',
    title: 'Why Hands-On Learning Works Better Than Reading Docs',
    excerpt: 'Studies show engineers retain 75% of what they practice compared to 10% of what they read. Here is how FixitLab applies active learning.',
    category: 'Education',
    author: 'Thirupathi P.',
    date: 'March 28, 2026',
    readTime: '5 min read',
  },
  {
    slug: 'debugging-nginx-like-a-pro',
    title: 'Debugging Nginx Like a Pro: A Step-by-Step Guide',
    excerpt: 'The systematic approach SREs use: status, nginx -t, error logs, port binding, and curl — with real command examples.',
    category: 'Linux',
    author: 'Platform Team',
    date: 'March 25, 2026',
    readTime: '8 min read',
  },
  {
    slug: 'kubernetes-crashloop-debugging',
    title: 'Kubernetes CrashLoopBackOff: A Practical Debug Checklist',
    excerpt: 'From kubectl describe to logs and probes — how to triage pods that never stay running.',
    category: 'Kubernetes',
    author: 'Platform Team',
    date: 'March 20, 2026',
    readTime: '7 min read',
  },
  {
    slug: 'dns-troubleshooting-guide',
    title: 'DNS Troubleshooting: From dig to Docker Resolver Issues',
    excerpt: 'Resolver chain, nsswitch, and the Docker DNS trap — patterns you will see in production incidents.',
    category: 'Networking',
    author: 'Platform Team',
    date: 'March 15, 2026',
    readTime: '6 min read',
  },
]

export const BLOG_CATEGORIES = ['All', 'Product', 'Education', 'Linux', 'Kubernetes', 'Networking', 'Architecture']

export const categoryBadgeClass = {
  Product: 'text-accent-green bg-accent-green/10 border-accent-green/20',
  Education: 'text-accent-cyan bg-accent-cyan/10 border-accent-cyan/20',
  Linux: 'text-accent-green bg-accent-green/10 border-accent-green/20',
  Kubernetes: 'text-accent-purple bg-accent-purple/10 border-accent-purple/20',
  Networking: 'text-accent-amber bg-accent-amber/10 border-accent-amber/20',
  Architecture: 'text-accent-purple bg-accent-purple/10 border-accent-purple/20',
  Engineering: 'text-accent-cyan bg-accent-cyan/10 border-accent-cyan/20',
}

export function getCategoryClass(category) {
  return categoryBadgeClass[category] || categoryBadgeClass.Education
}
