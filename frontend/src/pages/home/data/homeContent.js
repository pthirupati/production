import {
  Terminal, Shield, Clock, Trophy, Zap, Users, Award, Mic2,
  Wrench, Play, Skull, BookOpen, Monitor, CheckCircle2,
} from 'lucide-react'

export const features = [
  { icon: Terminal, title: 'Real Terminal', desc: 'Full interactive bash shell in your browser — connected to a real Linux environment via WebSocket.', color: 'cyan' },
  { icon: Mic2, title: 'AI Interview Studio', desc: 'Multi-round voice mock interviews — resume-aware questions, verifiable FIXIT-INT certificates.', color: 'purple' },
  { icon: Shield, title: 'Isolated Sandbox', desc: 'Docker, AWS EC2, or DigitalOcean labs — each session is isolated and auto-expires after 15 minutes.', color: 'purple' },
  { icon: Clock, title: 'Timed Challenges', desc: 'Race against the clock. Faster solves earn bonus points — just like real incident response.', color: 'amber' },
  { icon: Trophy, title: 'Leaderboard & Scoring', desc: 'Compete globally, track rankings per technology, and earn achievements for milestones.', color: 'green' },
  { icon: Zap, title: 'Auto-Validation', desc: 'Click "Check Solution" and our validation engine runs inside your environment to verify the fix.', color: 'cyan' },
  { icon: Users, title: 'Community Threads', desc: 'Discuss scenarios, attach error screenshots, vote, and react — learn from peers in context.', color: 'purple' },
  { icon: Award, title: 'Teams & Coupons', desc: 'Enterprise seat-based access, org billing, and promo codes at checkout on Pricing.', color: 'amber' },
]

export const scenarioTypes = [
  {
    type: 'fix',
    icon: Wrench,
    label: 'Fix It',
    desc: 'Something is broken. Diagnose the root cause and repair it before the timer runs out.',
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
    desc: 'Complete a task from scratch — configure services, ship infrastructure, prove you can deliver.',
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
  { name: 'Arun Kumar', role: 'Senior DevOps Engineer', company: 'Infosys', initials: 'AK', text: 'FixitLab is the closest thing to real incident response practice. The timed challenges genuinely simulate production pressure — far better than reading docs.' },
  { name: 'Ravi Patel', role: 'Site Reliability Engineer', company: 'Google', initials: 'RP', text: 'I use this to prep for interviews. The container labs are incredibly realistic — it feels like SSHing into a real broken server at 3am.' },
  { name: 'Maria Lee', role: 'Platform Engineer', company: 'DigitalOcean', initials: 'ML', text: 'Finally a platform that teaches the right way — by breaking things and fixing them. The validation engine and hint system are brilliant.' },
  { name: 'Erik Volkov', role: 'Cloud Architect', company: 'AWS', initials: 'EV', text: 'Progressive difficulty plus the AI interview studio keeps me sharp. I learn something new every single session.' },
]

export const interviewBullets = [
  { icon: Mic2, title: 'Live voice-driven sessions', desc: 'Speak naturally — browser STT captures your answer in real time, just like a real video call.' },
  { icon: Award, title: 'STAR scoring engine', desc: 'Every answer scored on Situation, Task, Action, and Result coverage — instantly.' },
  { icon: Shield, title: '100% free — no paid APIs', desc: 'Our in-process scoring engine runs with zero external cost or hidden rate limits.' },
  { icon: Trophy, title: 'Verifiable FIXIT-INT certificates', desc: 'Earn certificates you can add to your résumé and LinkedIn after completing a round.' },
]

export const howItWorksSteps = [
  { step: '01', title: 'Pick a challenge', desc: 'Browse by technology, difficulty and type. Filter by tags or search for something specific.', icon: BookOpen, color: '#49b5ff', bg: 'rgba(73,181,255,.18)', border: 'rgba(73,181,255,.25)', delay: '0s' },
  { step: '02', title: 'Launch the lab', desc: 'An isolated container or cloud instance spins up in seconds — real environment, zero config.', icon: Monitor, color: '#d6a8ee', bg: 'rgba(178,102,224,.18)', border: 'rgba(178,102,224,.25)', delay: '1.2s' },
  { step: '03', title: 'Fix & validate', desc: 'Use the real terminal to diagnose and repair. Click "Check Solution" to score instantly.', icon: CheckCircle2, color: '#56e0b0', bg: 'rgba(86,224,176,.18)', border: 'rgba(86,224,176,.25)', delay: '2.4s' },
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
