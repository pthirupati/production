import { Link } from 'react-router-dom'
import PublicLayout from '../components/layout/PublicLayout'
import { FixitPanel } from '../components/design'
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
    gradient: 'from-accent-cyan/20 to-accent-blue/10',
    border: 'border-accent-cyan/20',
    textColor: 'text-accent-cyan',
  },
  {
    name: 'Platform Team',
    role: 'Engineering',
    bio: 'A talented team building the infrastructure that powers thousands of lab sessions. Docker, Kubernetes, AWS, and more.',
    gradient: 'from-accent-green/20 to-accent-cyan/10',
    border: 'border-accent-green/20',
    textColor: 'text-accent-green',
  },
  {
    name: 'Content Team',
    role: 'Scenario Design',
    bio: 'Engineers and developers crafting realistic challenges from real-world incidents across Linux, cloud, databases, and more.',
    gradient: 'from-accent-purple/20 to-accent-pink/10',
    border: 'border-accent-purple/20',
    textColor: 'text-accent-purple',
  },
  {
    name: 'Community',
    role: 'Contributors',
    bio: 'Open-source contributors and beta testers who shape the platform with feedback, scenarios, and improvements.',
    gradient: 'from-accent-amber/20 to-accent-red/10',
    border: 'border-accent-amber/20',
    textColor: 'text-accent-amber',
  },
]

const milestones = [
  { year: '2025', title: 'Idea Born', desc: 'Concept for a hands-on troubleshooting platform started from real hiring pain points.', icon: Brain, color: 'text-accent-purple', bg: 'bg-accent-purple/10', border: 'border-accent-purple/20' },
  { year: '2025', title: 'MVP Launch', desc: 'First Docker-based scenarios went live with Nginx, Cron, and DNS challenges.', icon: Terminal, color: 'text-accent-cyan', bg: 'bg-accent-cyan/10', border: 'border-accent-cyan/20' },
  { year: '2026', title: 'Cloud Labs', desc: 'Added AWS EC2 and DigitalOcean support for advanced scenarios needing real servers.', icon: Cloud, color: 'text-accent-blue', bg: 'bg-accent-blue/10', border: 'border-accent-blue/20' },
  { year: '2026', title: 'Jira & Teams', desc: 'Incident tickets per learner, Jira bot sync, org invites, member analytics, and AI interview coaching.', icon: Ticket, color: 'text-accent-green', bg: 'bg-accent-green/10', border: 'border-accent-green/20' },
  { year: '2026', title: 'Growing Fast', desc: 'Expanded catalog across Linux, cloud, K8s, and AI-powered environments — full admin, billing, and certificate flows.', icon: Zap, color: 'text-accent-amber', bg: 'bg-accent-amber/10', border: 'border-accent-amber/20' },
]

const values = [
  { icon: Terminal, title: 'Learn by Doing', desc: 'We believe the best way to learn is by breaking things and fixing them — not reading docs.', color: 'text-accent-cyan', bg: 'bg-accent-cyan/10 group-hover:bg-accent-cyan/20' },
  { icon: Shield, title: 'Safe to Fail', desc: 'Every lab is an isolated sandbox (Docker, EC2, or DO). Sessions auto-expire in 15 minutes by default.', color: 'text-accent-green', bg: 'bg-accent-green/10 group-hover:bg-accent-green/20' },
  { icon: Heart, title: 'Accessible', desc: 'Free tier for everyone. Promo coupons, teams for enterprise, and OAuth sign-up.', color: 'text-accent-pink', bg: 'bg-accent-pink/10 group-hover:bg-accent-pink/20' },
  { icon: Globe, title: 'Global Community', desc: 'Engineers share threads with screenshots, vote on solutions, and compete on leaderboards.', color: 'text-accent-blue', bg: 'bg-accent-blue/10 group-hover:bg-accent-blue/20' },
  { icon: Code, title: 'Real Environments', desc: 'Docker containers, AWS EC2, and DigitalOcean droplets — plus AI-powered RHEL environments.', color: 'text-accent-purple', bg: 'bg-accent-purple/10 group-hover:bg-accent-purple/20' },
  { icon: Zap, title: 'Instant Feedback', desc: 'Auto-validation checks your fix inside the environment. Know if you solved it immediately.', color: 'text-accent-amber', bg: 'bg-accent-amber/10 group-hover:bg-accent-amber/20' },
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
      'Works with real Jira Cloud or built-in AI-powered mode when Jira is not configured',
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
    icon: MessageSquare,
    title: 'FixitLab Assistant (Help bot)',
    color: 'teal',
    desc: 'Separate from Jira bots — a floating platform guide for subscriptions, launching labs, interviews, and support contacts.',
    bullets: [
      'Click Help on any page — popup chat with typing indicator and quick topics',
      'Answers platform how-to only; Jira ticket and @team questions stay in the lab Jira panel',
      'Users can hide or disable from Profile; admins control welcome text and FAQ in Platform Settings',
      'Jira customer bot + @team bots handle incident details, patching prep, disks, and NICs inside labs',
    ],
  },
  {
    icon: Brain,
    title: 'AI Interview Studio',
    color: 'indigo',
    desc: 'Full mock interview cycles — voice Q&A, resume-aware questions, 3–5 rounds, and FIXIT-INT certificates.',
    bullets: [
      'Technical, manager, HR, deep-dive, and leadership panels',
      'Camera/mic required with adaptive scoring and post-round reports',
      'Monthly Pro/Premium plans separate from lab subscriptions',
      'Public certificate verification at /verify-certificate',
    ],
  },
  {
    icon: Brain,
    title: 'Scenario Interview Coaching',
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
      'Instant AI-powered RHEL environments — labs ready in seconds, no VM provisioning wait',
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
      'Org plans, coupons, and secure checkout on the Pricing page',
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
  { icon: GraduationCap, title: 'Students & career switchers', desc: 'Build muscle memory on real shells instead of only watching videos.', color: 'text-accent-cyan', bg: 'bg-accent-cyan/10' },
  { icon: Target, title: 'Interview candidates', desc: 'Mock Interview Studio for voice panels, plus timed Fix / Build / Hack labs and Jira tickets for on-call prep.', color: 'text-accent-purple', bg: 'bg-accent-purple/10' },
  { icon: Server, title: 'DevOps & SRE teams', desc: 'Run team drills on broken Nginx, DNS, K8s, or cloud misconfigs in minutes.', color: 'text-accent-green', bg: 'bg-accent-green/10' },
  { icon: Layers, title: 'Hiring managers', desc: 'Assign scenarios, review completion data, and optionally sync incidents to Jira.', color: 'text-accent-amber', bg: 'bg-accent-amber/10' },
]

const colorMap = {
  blue:   { bg: 'bg-accent-blue/10 group-hover:bg-accent-blue/20',     text: 'text-accent-blue'   },
  cyan:   { bg: 'bg-accent-cyan/10 group-hover:bg-accent-cyan/20',     text: 'text-accent-cyan'   },
  teal:   { bg: 'bg-accent-cyan/10 group-hover:bg-accent-cyan/20',     text: 'text-accent-cyan'   },
  indigo: { bg: 'bg-accent-blue/10 group-hover:bg-accent-blue/20',     text: 'text-accent-blue'   },
  purple: { bg: 'bg-accent-purple/10 group-hover:bg-accent-purple/20', text: 'text-accent-purple' },
  green:  { bg: 'bg-accent-green/10 group-hover:bg-accent-green/20',   text: 'text-accent-green'  },
  amber:  { bg: 'bg-accent-amber/10 group-hover:bg-accent-amber/20',   text: 'text-accent-amber'  },
}

export default function About() {
  return (
    <PublicLayout>
      {/* ── Hero ──────────────────────────────────────────────── */}
      <section className="relative overflow-hidden py-28 aurora-bg mesh-gradient">
        <div className="absolute inset-0 hero-grid opacity-50 pointer-events-none" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[900px] h-[500px] bg-accent-purple/8 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[400px] bg-accent-cyan/6 rounded-full blur-3xl pointer-events-none" />

        <div className="max-w-4xl mx-auto px-6 text-center relative animate-fade-in">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-purple/10 border border-accent-purple/20 text-accent-purple text-sm mb-8">
            <Heart size={14} />
            Our Mission
          </div>
          <h1 className="text-5xl lg:text-7xl font-extrabold text-white leading-[1.05] mb-6 tracking-tight glow-text">
            Master Technology
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-accent-cyan via-accent-blue to-accent-purple">
              Through Practice
            </span>
          </h1>
          <p className="text-xl text-surface-400 max-w-2xl mx-auto leading-relaxed mb-10">
            FixitLab was built by engineers who were tired of theoretical learning.
            We believe the best way to master any technology is to actually use it —
            on real infrastructure, with real problems, and real consequences.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link to="/register" className="btn-primary text-base px-8 py-3 inline-flex items-center gap-2 shadow-lg shadow-accent-cyan/20">
              Start for Free <ArrowRight size={16} />
            </Link>
            <Link to="/scenarios" className="btn-secondary text-base px-8 py-3 inline-flex items-center gap-2">
              Browse Challenges
            </Link>
          </div>
        </div>
      </section>

      <div className="section-divider" />

      {/* ── Stats bar ─────────────────────────────────────────── */}
      <section className="border-y border-surface-800/50 bg-surface-900/40 backdrop-blur-sm">
        <div className="max-w-5xl mx-auto px-6 py-12">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            {[
              { value: '9+',   label: 'Scenarios',       icon: Target,       color: 'text-accent-cyan'   },
              { value: '3+',   label: 'Technologies',    icon: Cpu,          color: 'text-accent-purple' },
              { value: '3',    label: 'Cloud Providers', icon: Cloud,        color: 'text-accent-blue'   },
              { value: '24/7', label: 'Availability',    icon: CheckCircle2, color: 'text-accent-green'  },
            ].map(({ value, label, icon: Icon, color }) => (
              <div key={label} className="group">
                <div className="w-12 h-12 rounded-xl bg-surface-800 flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform">
                  <Icon size={22} className={color} />
                </div>
                <p className="text-3xl font-extrabold text-white mb-1">{value}</p>
                <p className="text-sm text-surface-400">{label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Values ────────────────────────────────────────────── */}
      <section className="max-w-7xl mx-auto px-6 py-24 animate-slide-up">
        <div className="text-center mb-14">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-cyan/10 border border-accent-cyan/20 text-accent-cyan text-sm mb-4">
            <Sparkles size={14} />
            Core Principles
          </div>
          <h2 className="text-4xl font-bold text-white mb-3">What We Believe</h2>
          <p className="text-surface-400 max-w-xl mx-auto leading-relaxed">
            These principles guide every feature we build and every scenario we design.
          </p>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
          {values.map(({ icon: Icon, title, desc, color, bg }, idx) => {
            const vDelays = ['reveal-delay-1','reveal-delay-2','reveal-delay-3','reveal-delay-4','reveal-delay-5','reveal-delay-6']
            return (
            <FixitPanel key={title} className={`group reveal ${vDelays[idx] || 'reveal-delay-1'}`}>
              <div className={`w-12 h-12 rounded-xl ${bg} flex items-center justify-center mb-4 transition-colors`}>
                <Icon size={22} className={color} />
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
              <p className="text-sm text-surface-400 leading-relaxed">{desc}</p>
            </FixitPanel>
            )
          })}
        </div>
      </section>

      <div className="section-divider" />

      {/* ── Timeline / Milestones ─────────────────────────────── */}
      <section className="bg-surface-900/40 border-y border-surface-800/50">
        <div className="max-w-4xl mx-auto px-6 py-24">
          <div className="text-center mb-14">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-amber/10 border border-accent-amber/20 text-accent-amber text-sm mb-4">
              <GitBranch size={14} />
              Our Journey
            </div>
            <h2 className="text-4xl font-bold text-white">From Idea to Platform</h2>
          </div>

          <div className="relative">
            {/* Vertical line */}
            <div className="absolute left-[2.5rem] top-4 bottom-4 w-px bg-gradient-to-b from-accent-cyan/40 via-accent-purple/40 to-accent-amber/40 hidden md:block" />
            <div className="space-y-8">
              {milestones.map(({ year, title, desc, icon: Icon, color, bg, border }, i) => (
                <div key={i} className={`flex gap-5 items-start reveal reveal-delay-${Math.min(i + 1, 5)}`}>
                  {/* Year + icon dot */}
                  <div className="shrink-0 hidden md:flex flex-col items-center gap-1 w-20 pt-1">
                    <span className={`text-xs font-bold ${color} mb-1`}>{year}</span>
                    <div className={`w-9 h-9 rounded-xl ${bg} border ${border} flex items-center justify-center z-10`}>
                      <Icon size={16} className={color} />
                    </div>
                  </div>
                  {/* Card */}
                  <FixitPanel padding="p-5" className="flex-1">
                    <div className="flex items-center gap-2 mb-2 md:hidden">
                      <Icon size={14} className={color} />
                      <span className={`text-xs font-bold ${color}`}>{year}</span>
                    </div>
                    <h3 className="text-lg font-semibold text-white mb-1">{title}</h3>
                    <p className="text-sm text-surface-400 leading-relaxed">{desc}</p>
                  </FixitPanel>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <div className="section-divider" />

      {/* ── Team ──────────────────────────────────────────────── */}
      <section className="max-w-7xl mx-auto px-6 py-24">
        <div className="text-center mb-14">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-green/10 border border-accent-green/20 text-accent-green text-sm mb-4">
            <Users size={14} />
            The People
          </div>
          <h2 className="text-4xl font-bold text-white mb-3">The Team</h2>
          <p className="text-surface-400 max-w-xl mx-auto">
            FixitLab is built by a small, focused team that cares deeply about hands-on technology education.
          </p>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-5xl mx-auto">
          {team.map(({ name, role, bio, gradient, border, textColor }, tIdx) => {
            const tDelays = ['reveal-delay-1','reveal-delay-2','reveal-delay-3','reveal-delay-4']
            return (
            <FixitPanel key={name} padding="p-6" className={`text-center group reveal ${tDelays[tIdx] || 'reveal-delay-1'}`}>
              <div className={`w-20 h-20 rounded-2xl bg-gradient-to-br ${gradient} border ${border} flex items-center justify-center mx-auto mb-5 group-hover:scale-110 transition-transform duration-300`}>
                <span className={`text-2xl font-extrabold ${textColor}`}>
                  {name.split(' ').map(w => w[0]).join('')}
                </span>
              </div>
              <h3 className="text-base font-semibold text-white mb-1">{name}</h3>
              <p className={`text-xs ${textColor} font-semibold mb-3 uppercase tracking-wide`}>{role}</p>
              <p className="text-sm text-surface-400 leading-relaxed">{bio}</p>
            </FixitPanel>
            )
          })}
        </div>
      </section>

      {/* ── Platform Features ─────────────────────────────────── */}
      <section className="bg-surface-900/40 border-y border-surface-800/50">
        <div className="max-w-7xl mx-auto px-6 py-24">
          <div className="text-center mb-14">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-cyan/10 border border-accent-cyan/20 text-accent-cyan text-sm mb-4">
              <Sparkles size={14} />
              Full platform tour
            </div>
            <h2 className="text-4xl font-bold text-white mb-3">Everything FixitLab Offers</h2>
            <p className="text-surface-400 max-w-2xl mx-auto leading-relaxed">
              Beyond launching a terminal — FixitLab combines incident workflows, AI coaching,
              team analytics, and community learning. Here is what you get when you browse, sign up, or assign labs to your team.
            </p>
          </div>
          <div className="grid lg:grid-cols-2 gap-5">
            {platformFeatures.map(({ icon: Icon, title, desc, bullets, color }) => {
              const c = colorMap[color] || colorMap.cyan
              return (
                <FixitPanel key={title} className="group">
                  <div className={`w-12 h-12 rounded-xl ${c.bg} flex items-center justify-center mb-4 transition-colors`}>
                    <Icon size={22} className={c.text} />
                  </div>
                  <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
                  <p className="text-sm text-surface-400 leading-relaxed mb-4">{desc}</p>
                  <ul className="space-y-2">
                    {bullets.map((b) => (
                      <li key={b} className="flex gap-2.5 text-sm text-surface-300">
                        <CheckCircle2 size={14} className={`${c.text} shrink-0 mt-0.5`} />
                        <span>{b}</span>
                      </li>
                    ))}
                  </ul>
                </FixitPanel>
              )
            })}
          </div>
        </div>
      </section>

      {/* ── Who it's for ──────────────────────────────────────── */}
      <section className="max-w-7xl mx-auto px-6 py-24">
        <div className="text-center mb-14">
          <h2 className="text-4xl font-bold text-white mb-3">Who Uses FixitLab?</h2>
          <p className="text-surface-400 max-w-xl mx-auto">
            From solo learners to engineering orgs running structured drills.
          </p>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {whoItsFor.map(({ icon: Icon, title, desc, color, bg }) => (
            <FixitPanel key={title} padding="p-6" className="text-center group">
              <div className={`w-12 h-12 rounded-xl ${bg} flex items-center justify-center mx-auto mb-4 group-hover:scale-110 transition-transform`}>
                <Icon size={22} className={color} />
              </div>
              <h3 className="text-sm font-semibold text-white mb-2">{title}</h3>
              <p className="text-xs text-surface-400 leading-relaxed">{desc}</p>
            </FixitPanel>
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

      {/* ── Why engineers choose FixitLab ─────────────────────── */}
      <section className="bg-surface-900/40 border-y border-surface-800/50">
        <div className="max-w-5xl mx-auto px-6 py-24">
          <h2 className="text-4xl font-bold text-white text-center mb-3">Why engineers choose FixitLab</h2>
          <p className="text-surface-400 text-center mb-12 max-w-2xl mx-auto leading-relaxed">
            Real environments, structured learning paths, and outcomes you can prove — built for practitioners, not slide decks.
          </p>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {[
              { title: 'Hands-on labs', desc: 'Break-fix scenarios in isolated environments — the same muscle memory you need on the job.' },
              { title: 'Verifiable progress', desc: 'Certificates, leaderboards, and interview reports you can share with hiring managers.' },
              { title: 'Always improving', desc: 'New scenarios and interview panels added regularly from real production incidents.' },
              { title: 'Fair pricing', desc: 'Per-technology yearly access and interview plans with clear attempt limits — no surprise renewals.' },
              { title: 'Privacy first', desc: 'You control resume and transcript data. Export or delete from your profile anytime.' },
              { title: 'Community support', desc: 'Discuss scenarios, share fixes, and learn from peers who have been in the same outage.' },
            ].map(({ title, desc }) => (
              <FixitPanel key={title} padding="p-5" className="hover:border-accent-cyan/30 transition-colors">
                <div className="w-2 h-2 rounded-full bg-accent-cyan mb-3" />
                <h3 className="text-sm font-semibold text-white mb-2">{title}</h3>
                <p className="text-xs text-surface-400 leading-relaxed">{desc}</p>
              </FixitPanel>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ───────────────────────────────────────────────── */}
      <section className="max-w-4xl mx-auto px-6 py-24 text-center">
        <FixitPanel hero padding="p-12" className="relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/5 via-transparent to-accent-purple/5 rounded-xl pointer-events-none" />
          <div className="relative">
            <h2 className="text-4xl font-extrabold text-white mb-4">Ready to start fixing?</h2>
            <p className="text-surface-400 mb-8 max-w-md mx-auto leading-relaxed">
              Join the community of engineers who learn by doing. Free forever.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Link to="/register" className="btn-primary text-base px-10 py-3.5 inline-flex items-center gap-2 shadow-lg shadow-accent-cyan/20">
                Create Free Account <ArrowRight size={18} />
              </Link>
              <Link to="/scenarios" className="btn-secondary text-base px-10 py-3.5 inline-flex items-center gap-2">
                Browse Challenges
              </Link>
            </div>
          </div>
        </FixitPanel>
      </section>
    </PublicLayout>
  )
}
