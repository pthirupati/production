import { Link } from 'react-router-dom'
import {
  Terminal, Shield, Cloud, Server, Users, Award, Target,
  Zap, ArrowRight, Globe, Heart, Code, Cpu, BookOpen,
  CheckCircle2, Github, Linkedin, Twitter, Mail,
  Ticket, Bot, MessageSquare, Trophy, Sparkles, Layers,
  GitBranch, Bookmark, BarChart3, Lock, Monitor, Brain, GraduationCap
} from 'lucide-react'

const team = [
  {
    name: 'Thirupathi P.',
    role: 'Founder & Lead Engineer',
    bio: 'Full-stack engineer passionate about hands-on tech education. Built FixitLab to make real-world technology skills accessible to everyone.',
    color: 'accent-cyan',
  },
  {
    name: 'Platform Team',
    role: 'Engineering',
    bio: 'A talented team building the infrastructure that powers thousands of lab sessions. Docker, Kubernetes, AWS, and more.',
    color: 'accent-green',
  },
  {
    name: 'Content Team',
    role: 'Scenario Design',
    bio: 'Engineers and developers crafting realistic challenges from real-world incidents across Linux, cloud, databases, and more.',
    color: 'accent-purple',
  },
  {
    name: 'Community',
    role: 'Contributors',
    bio: 'Open-source contributors and beta testers who shape the platform with feedback, scenarios, and improvements.',
    color: 'accent-amber',
  },
]

const milestones = [
  { year: '2025', title: 'Idea Born', desc: 'Concept for a hands-on troubleshooting platform started from real hiring pain points.' },
  { year: '2025', title: 'MVP Launch', desc: 'First Docker-based scenarios went live with Nginx, Cron, and DNS challenges.' },
  { year: '2026', title: 'Cloud Labs', desc: 'Added AWS EC2 and DigitalOcean support for advanced scenarios needing real servers.' },
  { year: '2026', title: 'Jira & Teams', desc: 'Incident tickets per learner, Jira bot sync, org invites, member analytics, and AI interview coaching.' },
  { year: '2026', title: 'Growing Fast', desc: 'Expanded catalog across Linux, cloud, K8s, and simulations — full admin, billing, and certificate flows.' },
]

const values = [
  { icon: Terminal, title: 'Learn by Doing', desc: 'We believe the best way to learn is by breaking things and fixing them — not reading docs.' },
  { icon: Shield, title: 'Safe to Fail', desc: 'Every lab is an isolated sandbox (Docker, EC2, or DO). Sessions auto-expire in 15 minutes by default.' },
  { icon: Heart, title: 'Accessible', desc: 'Free tier for everyone. Promo coupons, teams for enterprise, and OAuth sign-up.' },
  { icon: Globe, title: 'Global Community', desc: 'Engineers share threads with screenshots, vote on solutions, and compete on leaderboards.' },
  { icon: Code, title: 'Real Environments', desc: 'Docker containers, AWS EC2, and DigitalOcean droplets — plus unified RHEL simulations.' },
  { icon: Zap, title: 'Instant Feedback', desc: 'Auto-validation checks your fix inside the environment. Know if you solved it immediately.' },
]

const platformFeatures = [
  {
    icon: Ticket,
    title: 'Jira Incident Workflow',
    color: 'blue',
    desc: 'Many scenarios open with a realistic support ticket — your own issue key, priority, and status timeline. Practice triage the way SRE and L1/L2 teams do in production.',
    bullets: [
      'One personal ticket per user per scenario (not shared across learners)',
      'Ticket moves To Do → In Progress when you start the lab, Done when you pass validation',
      'In-app ticket panel with comments, activity history, and status — no Atlassian login required',
      'Works with real Jira Cloud or built-in simulation mode when Jira is not configured',
    ],
  },
  {
    icon: Bot,
    title: 'Jira Bot & Webhook Sync',
    color: 'cyan',
    desc: 'A server-side integration bot talks to Jira on your behalf. Learners stay inside FixitLab while managers can still update tickets in Jira when connected.',
    bullets: [
      'Bot account creates and transitions issues via the Jira REST API',
      'Bidirectional webhooks sync status changes and comments back to your dashboard',
      'Retry attempts increment run count on the same ticket — mirrors real re-opened incidents',
      'Staff admins get full ticket visibility; learners only see their own issues',
    ],
  },
  {
    icon: Brain,
    title: 'AI Interview Coaching',
    color: 'purple',
    desc: 'Interview-mode scenarios disable spoiler hints and offer AI coaching that nudges you toward the right area without giving away the answer.',
    bullets: [
      'Directional guidance for hiring prep and mock on-call drills',
      'Standard progressive hints still available on learning scenarios',
      'Hint usage tracked and reflected in your score',
    ],
  },
  {
    icon: Monitor,
    title: 'Browser Terminal Labs',
    color: 'green',
    desc: 'Full xterm.js shell over WebSocket — type real commands in Chrome, Firefox, or mobile. Dual-pane terminals and SSH-client scenarios for networking and multi-host puzzles.',
    bullets: [
      'Docker containers for fast spin-up; AWS EC2 & DigitalOcean for cloud-native drills',
      'Unified RHEL simulation engine when you need instant labs without waiting for VMs',
      'Blocked-command guardrails per scenario (e.g. prevent destructive reboots)',
      'Command history and session recording for review',
    ],
  },
  {
    icon: MessageSquare,
    title: 'Community & Leaderboards',
    color: 'amber',
    desc: 'Discuss scenarios, attach screenshots, upvote solutions, and climb technology-specific leaderboards.',
    bullets: [
      'Threaded community posts tied to scenarios and technologies',
      'Global and per-tech rankings with timed scoring bonuses',
      'Achievements, streaks, and downloadable completion certificates',
    ],
  },
  {
    icon: Users,
    title: 'Teams & Enterprise',
    color: 'cyan',
    desc: 'Organizations invite members, track lab usage, and manage seat-based billing from the Team dashboard.',
    bullets: [
      'Email invites, pending invites, and member removal',
      'Per-member analytics — scenarios attempted, completion rate, time in labs',
      'Org plans, coupons, and Razorpay checkout on the Pricing page',
    ],
  },
  {
    icon: BarChart3,
    title: 'Progress & Bookmarks',
    color: 'green',
    desc: 'Your dashboard shows technology progress, difficulty breakdown, recent activity, and saved scenarios to retry later.',
    bullets: [
      'Track solved vs attempted across Linux, Docker, AWS, Kubernetes, and more',
      'Bookmark scenarios for interview prep or team assignments',
      'In-app notifications for billing, Jira updates, and platform announcements',
    ],
  },
  {
    icon: Lock,
    title: 'Auth & Security',
    color: 'purple',
    desc: 'Production-ready auth and isolation so you can practice safely on shared infrastructure.',
    bullets: [
      'Email OTP registration, GitHub/Google OAuth, and password reset flows',
      'Isolated lab sandboxes with automatic session expiry and idle timeout',
      'Admin audit logs, rate limiting, and security dashboards for operators',
    ],
  },
]

const whoItsFor = [
  { icon: GraduationCap, title: 'Students & career switchers', desc: 'Build muscle memory on real shells instead of only watching videos.' },
  { icon: Target, title: 'Interview candidates', desc: 'Timed Fix / Build / Hack scenarios plus Jira tickets simulate on-call and hiring loops.' },
  { icon: Server, title: 'DevOps & SRE teams', desc: 'Run team drills on broken Nginx, DNS, K8s, or cloud misconfigs in minutes.' },
  { icon: Layers, title: 'Hiring managers', desc: 'Assign scenarios, review completion data, and optionally sync incidents to Jira.' },
]

export default function About() {
  return (
    <div className="min-h-screen bg-surface-950">
      {/* Nav */}
      <nav className="border-b border-surface-800/50 backdrop-blur-xl sticky top-0 z-50 bg-surface-950/90">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-accent-cyan to-brand-600 flex items-center justify-center shadow-lg shadow-accent-cyan/20">
              <Terminal size={18} className="text-white" />
            </div>
            <span className="text-xl font-bold text-white tracking-tight">FixitLab</span>
          </Link>
          <div className="hidden md:flex items-center gap-6">
            <Link to="/scenarios" className="text-sm text-surface-400 hover:text-white transition-colors">Scenarios</Link>
            <Link to="/pricing" className="text-sm text-surface-400 hover:text-white transition-colors">Pricing</Link>
            <Link to="/blog" className="text-sm text-surface-400 hover:text-white transition-colors">Blog</Link>
            <Link to="/about" className="text-sm text-white font-medium">About</Link>
          </div>
          <Link to="/register" className="btn-primary text-sm px-5">Get Started Free</Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0">
          <div className="absolute inset-0 opacity-[0.03]"
            style={{ backgroundImage: 'linear-gradient(rgb(var(--a-cyan)) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--a-cyan)) 1px, transparent 1px)', backgroundSize: '60px 60px' }} />
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-accent-purple/5 rounded-full blur-3xl" />
          <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] bg-accent-cyan/5 rounded-full blur-3xl" />
        </div>

        <div className="max-w-4xl mx-auto px-6 pt-20 pb-16 text-center relative">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-purple/10 border border-accent-purple/20 text-accent-purple text-sm mb-6">
            <Heart size={14} />
            Our Mission
          </div>
          <h1 className="text-5xl lg:text-6xl font-extrabold text-white leading-[1.1] mb-6">
            Master Technology
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-accent-cyan via-brand-400 to-accent-purple">
              Through Practice
            </span>
          </h1>
          <p className="text-lg text-surface-400 max-w-2xl mx-auto leading-relaxed">
            FixitLab was built by engineers who were tired of theoretical learning.
            We believe the best way to master any technology is to actually use it —
            on real infrastructure, with real problems, and real consequences.
          </p>
        </div>
      </section>

      {/* Stats */}
      <section className="border-y border-surface-800/50 bg-surface-900/30">
        <div className="max-w-5xl mx-auto px-6 py-12">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            {[
              { value: '9+', label: 'Scenarios', icon: Target },
              { value: '3+', label: 'Technologies', icon: Cpu },
              { value: '3', label: 'Cloud Providers', icon: Cloud },
              { value: '24/7', label: 'Availability', icon: CheckCircle2 },
            ].map(({ value, label, icon: Icon }) => (
              <div key={label}>
                <Icon size={24} className="text-accent-cyan mx-auto mb-2" />
                <p className="text-3xl font-bold text-white">{value}</p>
                <p className="text-sm text-surface-400">{label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Our Values */}
      <section className="max-w-7xl mx-auto px-6 py-20">
        <h2 className="text-3xl font-bold text-white text-center mb-3">What We Believe</h2>
        <p className="text-surface-400 text-center mb-12 max-w-xl mx-auto">
          These principles guide every feature we build and every scenario we design.
        </p>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {values.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="glass-card-hover p-6 group">
              <div className="w-12 h-12 rounded-xl bg-accent-cyan/10 flex items-center justify-center mb-4 group-hover:bg-accent-cyan/20 transition-colors">
                <Icon size={24} className="text-accent-cyan" />
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
              <p className="text-sm text-surface-400 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Platform capabilities — features not fully covered on Home */}
      <section className="bg-surface-900/30 border-y border-surface-800/50">
        <div className="max-w-7xl mx-auto px-6 py-20">
          <div className="text-center mb-14">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-cyan/10 border border-accent-cyan/20 text-accent-cyan text-sm mb-4">
              <Sparkles size={14} />
              Full platform tour
            </div>
            <h2 className="text-3xl font-bold text-white mb-3">Everything FixitLab Offers</h2>
            <p className="text-surface-400 max-w-2xl mx-auto leading-relaxed">
              Beyond launching a terminal — FixitLab combines incident workflows, AI coaching,
              team analytics, and community learning. Here is what you get when you browse, sign up, or assign labs to your team.
            </p>
          </div>
          <div className="grid lg:grid-cols-2 gap-6">
            {platformFeatures.map(({ icon: Icon, title, desc, bullets, color }) => {
              const iconBg = {
                blue: 'bg-blue-500/10 group-hover:bg-blue-500/20',
                cyan: 'bg-accent-cyan/10 group-hover:bg-accent-cyan/20',
                purple: 'bg-accent-purple/10 group-hover:bg-accent-purple/20',
                green: 'bg-accent-green/10 group-hover:bg-accent-green/20',
                amber: 'bg-accent-amber/10 group-hover:bg-accent-amber/20',
              }[color] || 'bg-accent-cyan/10'
              const iconText = {
                blue: 'text-blue-400',
                cyan: 'text-accent-cyan',
                purple: 'text-accent-purple',
                green: 'text-accent-green',
                amber: 'text-accent-amber',
              }[color] || 'text-accent-cyan'
              return (
                <div key={title} className="glass-card-hover p-6 group">
                  <div className={`w-12 h-12 rounded-xl ${iconBg} flex items-center justify-center mb-4 transition-colors`}>
                    <Icon size={24} className={iconText} />
                  </div>
                  <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
                  <p className="text-sm text-surface-400 leading-relaxed mb-4">{desc}</p>
                  <ul className="space-y-2">
                    {bullets.map((b) => (
                      <li key={b} className="flex gap-2 text-sm text-surface-300">
                        <CheckCircle2 size={14} className={`${iconText} shrink-0 mt-0.5`} />
                        <span>{b}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* Who it's for */}
      <section className="max-w-7xl mx-auto px-6 py-20">
        <h2 className="text-3xl font-bold text-white text-center mb-3">Who Uses FixitLab?</h2>
        <p className="text-surface-400 text-center mb-12 max-w-xl mx-auto">
          From solo learners to engineering orgs running structured drills.
        </p>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {whoItsFor.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="glass-card p-5 text-center">
              <div className="w-11 h-11 rounded-xl bg-surface-800 flex items-center justify-center mx-auto mb-3">
                <Icon size={22} className="text-accent-cyan" />
              </div>
              <h3 className="text-sm font-semibold text-white mb-2">{title}</h3>
              <p className="text-xs text-surface-400 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
        <div className="mt-10 flex flex-wrap justify-center gap-3 text-sm">
          <Link to="/scenarios" className="btn-secondary px-5 py-2 inline-flex items-center gap-2">
            Browse scenarios <ArrowRight size={14} />
          </Link>
          <Link to="/leaderboard" className="btn-secondary px-5 py-2 inline-flex items-center gap-2">
            <Trophy size={14} /> Leaderboard
          </Link>
          <Link to="/community" className="btn-secondary px-5 py-2 inline-flex items-center gap-2">
            <MessageSquare size={14} /> Community
          </Link>
          <Link to="/pricing" className="btn-secondary px-5 py-2 inline-flex items-center gap-2">
            Teams & pricing
          </Link>
        </div>
      </section>

      {/* The Story / Timeline */}
      <section className="bg-surface-900/30 border-y border-surface-800/50">
        <div className="max-w-4xl mx-auto px-6 py-20">
          <h2 className="text-3xl font-bold text-white text-center mb-12">Our Journey</h2>
          <div className="relative">
            {/* Vertical line */}
            <div className="absolute left-8 top-0 bottom-0 w-px bg-surface-700 hidden md:block" />
            <div className="space-y-10">
              {milestones.map(({ year, title, desc }, i) => (
                <div key={i} className="flex gap-6 items-start">
                  <div className="shrink-0 w-16 text-right hidden md:block">
                    <span className="text-sm font-bold text-accent-cyan">{year}</span>
                  </div>
                  <div className="shrink-0 w-4 h-4 rounded-full bg-accent-cyan border-4 border-surface-900 relative z-10 mt-1 hidden md:block" />
                  <div className="glass-card p-5 flex-1">
                    <span className="text-xs text-accent-cyan font-bold md:hidden">{year}</span>
                    <h3 className="text-lg font-semibold text-white mt-1">{title}</h3>
                    <p className="text-sm text-surface-400 mt-1">{desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Team */}
      <section className="max-w-7xl mx-auto px-6 py-20">
        <h2 className="text-3xl font-bold text-white text-center mb-3">The Team</h2>
        <p className="text-surface-400 text-center mb-12 max-w-xl mx-auto">
          FixitLab is built by a small, focused team that cares deeply about hands-on technology education.
        </p>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-5xl mx-auto">
          {team.map(({ name, role, bio, color }) => (
            <div key={name} className="glass-card-hover p-6 text-center group">
              <div className={`w-20 h-20 rounded-2xl bg-${color}/10 border border-${color}/20 flex items-center justify-center mx-auto mb-4 group-hover:scale-110 transition-transform`}>
                <span className={`text-2xl font-bold text-${color}`}>
                  {name.split(' ').map(w => w[0]).join('')}
                </span>
              </div>
              <h3 className="text-base font-semibold text-white">{name}</h3>
              <p className={`text-xs text-${color} font-medium mb-2`}>{role}</p>
              <p className="text-sm text-surface-400 leading-relaxed">{bio}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Tech Stack */}
      <section className="bg-surface-900/30 border-y border-surface-800/50">
        <div className="max-w-5xl mx-auto px-6 py-20">
          <h2 className="text-3xl font-bold text-white text-center mb-3">Built With</h2>
          <p className="text-surface-400 text-center mb-12">Production-grade stack trusted by enterprise teams.</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            {[
              { name: 'React 18', cat: 'Frontend' },
              { name: 'Django 5', cat: 'Backend' },
              { name: 'PostgreSQL', cat: 'Database' },
              { name: 'Redis', cat: 'Cache' },
              { name: 'Docker', cat: 'Containers' },
              { name: 'Kubernetes', cat: 'Orchestration' },
              { name: 'Terraform', cat: 'IaC' },
              { name: 'AWS EC2', cat: 'Cloud' },
              { name: 'DigitalOcean', cat: 'Cloud' },
              { name: 'Celery', cat: 'Task Queue' },
              { name: 'RabbitMQ', cat: 'Broker' },
              { name: 'Nginx', cat: 'Gateway' },
            ].map(({ name, cat }) => (
              <div key={name} className="glass-card p-3 text-center hover:border-accent-cyan/30 transition-colors">
                <p className="text-sm font-medium text-white">{name}</p>
                <p className="text-[10px] text-surface-500">{cat}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-4xl mx-auto px-6 py-20 text-center">
        <div className="glass-card p-12 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/5 to-accent-purple/5" />
          <div className="relative">
            <h2 className="text-3xl font-bold text-white mb-4">Ready to start fixing?</h2>
            <p className="text-surface-400 mb-8 max-w-md mx-auto">
              Join the community of engineers who learn by doing. Free forever.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Link to="/register" className="btn-primary text-lg px-10 py-3.5 inline-flex items-center gap-2 shadow-lg shadow-accent-cyan/20">
                Create Free Account <ArrowRight size={18} />
              </Link>
              <Link to="/scenarios" className="btn-secondary text-lg px-10 py-3.5 inline-flex items-center gap-2">
                Browse Challenges
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-surface-800/50 bg-surface-900/30">
        <div className="max-w-7xl mx-auto px-6 py-12">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-cyan to-brand-600 flex items-center justify-center">
                <Terminal size={16} className="text-white" />
              </div>
              <span className="text-lg font-bold text-white">FixitLab</span>
            </div>
            <div className="flex items-center gap-6 text-surface-500">
              <Link to="/" className="text-sm hover:text-white transition-colors">Home</Link>
              <Link to="/scenarios" className="text-sm hover:text-white transition-colors">Scenarios</Link>
              <Link to="/pricing" className="text-sm hover:text-white transition-colors">Pricing</Link>
              <Link to="/privacy" className="text-sm hover:text-white transition-colors">Privacy</Link>
              <Link to="/terms" className="text-sm hover:text-white transition-colors">Terms</Link>
              <Link to="/contact" className="text-sm hover:text-white transition-colors">Contact</Link>
            </div>
            <p className="text-xs text-surface-600">&copy; 2026 FixitLab. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
