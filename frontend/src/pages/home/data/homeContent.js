import {
  Terminal, Shield, Clock, Trophy, Zap, Users, Award, Mic2,
  Wrench, Play, Skull, BookOpen, Monitor, CheckCircle2, Ticket, Bot,
} from 'lucide-react'

export const features = [
  { icon: Terminal, title: 'Real Terminal & Simulators', desc: 'Full bash shell via WebSocket plus in-app Grafana, AWX, VMware vCenter, Terraform, and Windows Server — each lab runs in your own isolated sandbox.', color: 'cyan' },
  { icon: Ticket, title: 'Jira & ITSM Workflow', desc: 'Every scenario opens with a realistic Jira ticket — incident narrative, priority, environment state, and resolution criteria. Practice the way platform teams actually work.', color: 'amber' },
  { icon: Mic2, title: 'AI Interview Studio', desc: 'Multi-round voice mock interviews — technical, behavioral, system design, and hands-on lab rounds with resume-aware questions and FIXIT-INT certificates.', color: 'purple' },
  { icon: Shield, title: 'Per-User Lab Isolation', desc: 'Every session gets its own Docker network and container. Your lab cannot see or affect another user\'s environment — safe for teams training together.', color: 'purple' },
  { icon: Clock, title: 'Timed Incident Response', desc: 'Race the clock like a real on-call page. Faster solves earn bonus points — the same pressure you face in production.', color: 'amber' },
  { icon: Zap, title: 'Instant Validation', desc: 'Click "Check Solution" and our grader runs inside your environment to verify the fix — no guessing, no marker files.', color: 'cyan' },
  { icon: Bot, title: 'Guided Hints (3 tiers)', desc: 'Free discovery hints → diagnostic steps → full fix reveal. Learn methodology first, answers only when you need them.', color: 'green' },
  { icon: Award, title: 'Affordable Pricing & Coupons', desc: 'Pay per technology at prices that keep hands-on practice affordable. Promo codes apply automatically at checkout — teams get seat-based billing too.', color: 'amber' },
]

export const scenarioTypes = [
  {
    type: 'fix',
    icon: Wrench,
    label: 'Fix It',
    desc: 'Something is broken. Diagnose the root cause and repair it before the timer runs out — like SadServers or a real on-call page.',
    accent: '#49b5ff',
    bg: 'linear-gradient(165deg, rgba(73,181,255,.08), rgba(255,255,255,.02))',
    iconBg: 'linear-gradient(135deg, rgba(73,181,255,.22), rgba(73,181,255,.06))',
    border: 'rgba(73,181,255,.3)',
    hoverBorder: 'rgba(73,181,255,.45)',
    hoverShadow: '0 30px 60px -25px rgba(73,181,255,.5)',
  },
  {
    type: 'do',
    icon: Play,
    label: 'Build It',
    desc: 'Complete a task from scratch — configure services, ship infrastructure, prove you can deliver end-to-end.',
    accent: '#56e0b0',
    bg: 'linear-gradient(165deg, rgba(86,224,176,.08), rgba(255,255,255,.02))',
    iconBg: 'linear-gradient(135deg, rgba(86,224,176,.22), rgba(86,224,176,.06))',
    border: 'rgba(86,224,176,.3)',
    hoverBorder: 'rgba(86,224,176,.45)',
    hoverShadow: '0 30px 60px -25px rgba(86,224,176,.5)',
  },
  {
    type: 'hack',
    icon: Skull,
    label: 'Hack It',
    desc: 'Exploit a vulnerability, capture a hidden flag, or break into a misconfigured system.',
    accent: '#ec6a5e',
    bg: 'linear-gradient(165deg, rgba(235,106,94,.08), rgba(255,255,255,.02))',
    iconBg: 'linear-gradient(135deg, rgba(235,106,94,.22), rgba(235,106,94,.06))',
    border: 'rgba(235,106,94,.3)',
    hoverBorder: 'rgba(235,106,94,.45)',
    hoverShadow: '0 30px 60px -25px rgba(235,106,94,.5)',
  },
]

export const testimonials = [
  { name: 'DevOps Engineer', role: 'SRE · 6 years experience', company: 'Enterprise', initials: 'DE', text: 'FixitLab is the closest thing to real incident response practice. The timed challenges and Jira ticket workflow genuinely simulate production pressure — far better than reading docs or watching videos.' },
  { name: 'Platform Engineer', role: 'Cloud & Kubernetes', company: 'Mid-size SaaS', initials: 'PE', text: 'I use this to prep for interviews. The container labs feel like SSHing into a real broken server at 3am. The AI interview rounds with hands-on lab sections are something no other platform offers.' },
  { name: 'Linux Administrator', role: 'Infrastructure', company: 'Managed services', initials: 'LA', text: 'Finally a platform that teaches the right way — by breaking things and fixing them. The validation engine, guided hints, and per-user isolation mean I can train my whole team without stepping on each other.' },
  { name: 'Cloud Architect', role: 'Multi-cloud', company: 'Consulting', initials: 'CA', text: '5,000+ scenarios across 30 technologies, certification tracks, and mock interviews — all at a fraction of what dedicated interview prep usually costs. The VMware and Ansible simulators are standout features.' },
]

export const interviewBullets = [
  { icon: Mic2, title: 'Live voice-driven sessions', desc: 'Speak naturally — browser STT captures your answer in real time, just like a real video call.' },
  { icon: Award, title: 'STAR scoring engine', desc: 'Every answer scored on Situation, Task, Action, and Result coverage — instantly.' },
  { icon: Terminal, title: 'Hands-on lab interview rounds', desc: 'Some rounds provision a real break-fix lab mid-interview — fix a production incident while the AI interviewer watches.' },
  { icon: Trophy, title: 'Verifiable FIXIT-INT certificates', desc: 'Earn certificates you can add to your résumé and LinkedIn after completing a round.' },
]

export const howItWorksSteps = [
  { step: '01', title: 'Pick a Jira ticket', desc: 'Browse 5,000+ scenarios across 30+ technologies. Each opens with a realistic incident ticket — priority, environment, and what "resolved" looks like.', icon: BookOpen, color: '#49b5ff', bg: 'rgba(73,181,255,.18)', border: 'rgba(73,181,255,.25)', delay: '0s' },
  { step: '02', title: 'Launch your isolated lab', desc: 'Your own container or simulator spins up in seconds — separate network, separate state. Other users\' labs never interfere with yours.', icon: Monitor, color: '#d6a8ee', bg: 'rgba(178,102,224,.18)', border: 'rgba(178,102,224,.25)', delay: '1.2s' },
  { step: '03', title: 'Fix, validate, level up', desc: 'Use the real terminal, Grafana, AWX, or vCenter to diagnose and repair. Click "Check Solution" for instant grading, then sit an AI mock interview.', icon: CheckCircle2, color: '#56e0b0', bg: 'rgba(86,224,176,.18)', border: 'rgba(86,224,176,.25)', delay: '2.4s' },
]

export const vmwareBullets = [
  'Full vCenter UI — hosts, VMs, storage & networking',
  'Live vMotion, HA, DRS, snapshots & maintenance mode',
  'Realistic faults: disconnected hosts, full datastores',
  'Real-time performance charts & recent-tasks panel',
]

export const footerColumns = [
  {
    title: 'Product',
    links: [
      { label: 'Technologies', to: '/#tech' },
      { label: 'Tutorials', to: '/tutorials' },
      { label: 'Mock Interviews', to: '/mock-interviews' },
      { label: 'Pricing', to: '/pricing' },
      { label: 'Get Started', to: '/register' },
    ],
  },
  {
    title: 'Resources',
    links: [
      { label: 'Blog', to: '/blog' },
      { label: 'FAQ', to: '/faq' },
      { label: 'Verify Certificate', to: '/verify-certificate' },
    ],
  },
  {
    title: 'Company',
    links: [
      { label: 'About', to: '/about' },
      { label: 'Privacy', to: '/privacy' },
      { label: 'Terms', to: '/terms' },
      { label: 'Contact', to: '/contact' },
    ],
  },
]
