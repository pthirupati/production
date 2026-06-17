import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import InterviewDemoWidget from '../components/InterviewDemoWidget'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { useDataStore } from '../store/dataStore'
import { scenarioApi } from '../api/scenarios'
import api from '../api/client'
import { PlatformBanners } from '../components/PlatformBanners'
import { PUBLIC_NAV_LINKS } from '../constants/publicNav'
import {
  Terminal, Shield, Clock, Trophy, Zap, Server,
  Cloud, Lock, Cpu, ArrowRight, CheckCircle2,
  Users, Award, BookOpen, Wrench, Skull, Play,
  Star, ChevronRight, Monitor, Globe, Sun, Moon,
  Sparkles, Code2, Rocket, GraduationCap, Layers,
  Activity, GitBranch, Database, Target, Flame, Menu, X, Mic2,
} from 'lucide-react'

const features = [
  { icon: Terminal,     title: 'Real Terminal',             desc: 'Full interactive bash shell in your browser — connected to a real Linux environment via WebSocket.',               color: 'cyan'   },
  { icon: Mic2,         title: 'AI Interview Studio',       desc: 'Multi-round voice mock interviews — resume-aware questions, verifiable FIXIT-INT certificates.',                   color: 'purple' },
  { icon: Shield,       title: 'Isolated Sandbox',          desc: 'Docker, AWS EC2, or DigitalOcean labs — each session is isolated and auto-expires after 15 minutes.',              color: 'purple' },
  { icon: Clock,        title: 'Timed Challenges',          desc: 'Race against the clock. Faster solves earn bonus points — just like real incident response.',                       color: 'amber'  },
  { icon: Trophy,       title: 'Leaderboard & Scoring',     desc: 'Compete globally, track rankings per technology, and earn achievements for milestones.',                           color: 'green'  },
  { icon: Zap,          title: 'Auto-Validation',           desc: 'Click "Check Solution" and our validation engine runs inside your environment to verify the fix.',                  color: 'cyan'   },
  { icon: Users,        title: 'Community Threads',         desc: 'Discuss scenarios, attach error screenshots, vote, and react — learn from peers in context.',                      color: 'purple' },
  { icon: Award,        title: 'Teams & Coupons',           desc: 'Enterprise seat-based access, org billing, and promo codes at checkout on Pricing.',                               color: 'amber'  },
]

const scenarioTypes = [
  { type: 'fix',  icon: Wrench, label: 'Fix It',   desc: 'Something is broken — diagnose the issue and repair it before time runs out.',                        color: 'cyan',   gradient: 'from-accent-cyan/20 to-accent-blue/10'   },
  { type: 'do',   icon: Play,   label: 'Build It',  desc: 'Complete a task from scratch — configure services, set up infrastructure, prove you can ship.',       color: 'green',  gradient: 'from-accent-green/20 to-emerald-400/10'  },
  { type: 'hack', icon: Skull,  label: 'Hack It',   desc: 'Exploit a vulnerability, find a hidden flag, or break into a misconfigured system.',                  color: 'red',    gradient: 'from-accent-red/20 to-rose-400/10'       },
]

const testimonials = [
  { name: 'Arun Kumar',  role: 'Senior DevOps Engineer',    company: 'Infosys',      text: 'FixitLab is the closest thing to real incident response practice. Way better than reading docs. The timed challenges really simulate production pressure.'   },
  { name: 'Ravi Patel',  role: 'Site Reliability Engineer', company: 'Google',       text: 'I use this to prep for interviews. The container-based labs are incredibly realistic — feels like SSHing into a real broken server.'                        },
  { name: 'Maria Lee',   role: 'Junior SysAdmin',           company: 'DigitalOcean', text: 'Finally a platform that teaches Linux the right way — by breaking things and fixing them. The hint system is brilliant.'                                     },
  { name: 'Erik Volkov', role: 'Cloud Architect',           company: 'AWS',          text: 'The progressive difficulty and achievement system keeps me coming back. I learn something new every time, even on easy challenges.'                           },
]

const trustedBy = [
  { name: 'Linux',      icon: Server   },
  { name: 'Docker',     icon: Monitor  },
  { name: 'Networking', icon: Globe    },
  { name: 'AWS',        icon: Cloud    },
  { name: 'Kubernetes', icon: Cpu      },
  { name: 'Database',   icon: Database },
]

export default function Home() {
  const { isAuthenticated } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const getTechnologies = useDataStore(s => s.getTechnologies)
  const [technologies, setTechnologies]           = useState([])
  const [stats, setStats]                         = useState({})
  const [platformConfig, setPlatformConfig]       = useState(null)
  const [mobileNavOpen, setMobileNavOpen]         = useState(false)
  const [activeTestimonial, setActiveTestimonial] = useState(0)

  useEffect(() => {
    getTechnologies().then(setTechnologies).catch(() => {})
    scenarioApi.getPlatformStats().then(setStats).catch(() => {})
    api.get('/config/').then(res => {
      setPlatformConfig(res.data)
      if (res.data?.platform_stats) {
        setStats(prev => ({ ...res.data.platform_stats, ...prev }))
      }
    }).catch(() => {})
  }, [])

  useEffect(() => {
    const timer = setInterval(() => {
      setActiveTestimonial(prev => (prev + 1) % testimonials.length)
    }, 5000)
    return () => clearInterval(timer)
  }, [])

  const techIcons = { Linux: Server, AWS: Cloud, Kubernetes: Cpu, Docker: Monitor, Networking: Globe, 'GPU & NVIDIA': Cpu }

  return (
    <div className="min-h-screen bg-surface-950">

      {/* ─── Sticky Navbar ─── */}
      <div className="sticky top-0 z-50">
        <nav className="border-b border-surface-700/30 backdrop-blur-2xl bg-surface-950/90">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">

            {/* Logo */}
            <Link to="/" className="flex items-center gap-2.5 group shrink-0">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-accent-cyan to-accent-blue flex items-center justify-center shadow-lg shadow-accent-cyan/25 group-hover:shadow-accent-cyan/40 transition-shadow">
                <Terminal size={18} className="text-white" />
              </div>
              <span className="text-xl font-bold text-white tracking-tight">FixitLab</span>
            </Link>

            {/* Desktop nav links */}
            <div className="hidden md:flex items-center gap-5 overflow-x-auto max-w-[60vw] pb-1">
              {PUBLIC_NAV_LINKS.map(({ to, label }) => (
                <Link
                  key={to}
                  to={to}
                  className="text-sm text-surface-400 hover:text-white transition-colors relative group whitespace-nowrap shrink-0"
                >
                  {label}
                  <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-gradient-to-r from-accent-cyan to-accent-purple group-hover:w-full transition-all duration-300" />
                </Link>
              ))}
            </div>

            {/* Right actions */}
            <div className="flex items-center gap-2 sm:gap-3">
              <button
                type="button"
                className="md:hidden p-2 text-surface-400"
                onClick={() => setMobileNavOpen(v => !v)}
                aria-label="Menu"
              >
                {mobileNavOpen ? <X size={20} /> : <Menu size={20} />}
              </button>

              <button
                onClick={toggleTheme}
                className="p-2 rounded-lg text-surface-400 hover:text-white hover:bg-surface-800/50 transition-all"
                aria-label="Toggle theme"
              >
                {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
              </button>

              {isAuthenticated ? (
                <Link to="/dashboard" className="btn-primary text-sm px-5">Dashboard</Link>
              ) : (
                <>
                  <Link to="/login" className="text-sm text-surface-300 hover:text-white transition-colors px-3 py-2 hidden sm:block">
                    Sign In
                  </Link>
                  <Link to="/register" className="btn-primary text-sm px-5">Get Started Free</Link>
                </>
              )}
            </div>
          </div>

          {/* Mobile flyout */}
          {mobileNavOpen && (
            <div className="md:hidden border-t border-surface-800 px-4 py-3 flex flex-col gap-2 bg-surface-950/95 max-h-[70vh] overflow-y-auto">
              {PUBLIC_NAV_LINKS.map(({ to, label }) => (
                <Link
                  key={to}
                  to={to}
                  onClick={() => setMobileNavOpen(false)}
                  className="text-sm text-surface-300 py-2"
                >
                  {label}
                </Link>
              ))}
            </div>
          )}
        </nav>

        {/* Platform banners sit flush under the nav */}
        <PlatformBanners config={platformConfig} showMaintenance showPromo />
      </div>
      {/* ─── end Navbar ─── */}


      {/* ═══════════════════════════════════════════
          SECTION 1 — HERO
          Left: terminal demo  |  Right: copy + CTAs
      ═══════════════════════════════════════════ */}
      <section className="relative overflow-hidden min-h-[92vh] flex items-center">
        {/* Background layers */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute inset-0 hero-gradient" />
          <div className="absolute inset-0 hero-grid opacity-40" />
          <div className="glow-orb-cyan   absolute -top-40  left-1/4  animate-morph" />
          <div className="glow-orb-purple absolute  top-1/3 -right-20 animate-float" />
          <div className="glow-orb-pink   absolute -bottom-40 right-1/3 animate-morph" style={{ animationDelay: '3s' }} />
          {/* Slow rotating dashed ring */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[820px] h-[820px] opacity-[0.05] animate-rotate-slow">
            <div className="w-full h-full rounded-full border-2 border-dashed border-accent-cyan" />
          </div>
          {/* Floating particles */}
          {[...Array(14)].map((_, i) => (
            <div
              key={i}
              className="particle"
              style={{
                width:  `${2 + (i % 4) * 2}px`,
                height: `${2 + (i % 4) * 2}px`,
                background: i % 4 === 0
                  ? 'rgb(var(--a-cyan)   / 0.5)'
                  : i % 4 === 1
                    ? 'rgb(var(--a-purple) / 0.4)'
                    : i % 4 === 2
                      ? 'rgb(var(--a-pink)   / 0.4)'
                      : 'rgb(var(--a-green)  / 0.4)',
                top:  `${5  + i * 6.5}%`,
                left: `${3  + i * 6.8}%`,
                animationDelay:    `${i * 0.5}s`,
                animationDuration: `${6 + i * 0.5}s`,
              }}
            />
          ))}
        </div>

        <div className="max-w-7xl mx-auto px-6 py-20 lg:py-28 relative w-full">
          <div className="grid lg:grid-cols-2 gap-12 xl:gap-20 items-center">

            {/* LEFT col — Terminal demo */}
            <div className="hidden lg:block animate-slide-up">
              <div className="relative">
                <div className="absolute -inset-6 bg-gradient-to-r from-accent-cyan/10 via-accent-blue/8 to-transparent rounded-3xl blur-3xl" />
                <div className="glass-card p-1 card-3d gradient-border relative">
                  {/* Live badge */}
                  <div className="absolute -top-4 -left-4 bg-surface-800/90 backdrop-blur-xl border border-accent-green/30 rounded-xl px-4 py-2 text-xs text-accent-green font-semibold flex items-center gap-2 z-10 shadow-lg shadow-accent-green/10">
                    <div className="w-2 h-2 rounded-full bg-accent-green animate-pulse" />
                    Live Session
                  </div>
                  {/* Timer badge */}
                  <div className="absolute -top-4 right-4 bg-surface-800/90 backdrop-blur-xl border border-accent-amber/30 rounded-xl px-4 py-2 text-xs text-accent-amber font-semibold flex items-center gap-2 z-10 shadow-lg shadow-accent-amber/10">
                    <Clock size={11} /> 12:34 remaining
                  </div>

                  {/* Terminal chrome */}
                  <div className="bg-surface-950 rounded-lg overflow-hidden">
                    <div className="flex items-center gap-2 px-4 py-3 bg-surface-900/80 border-b border-surface-700/50">
                      <div className="w-3 h-3 rounded-full bg-accent-red/80" />
                      <div className="w-3 h-3 rounded-full bg-accent-amber/80" />
                      <div className="w-3 h-3 rounded-full bg-accent-green/80" />
                      <span className="ml-3 text-xs text-surface-500 font-mono">root@fixitlab ~ broken-nginx</span>
                    </div>
                    <div className="p-5 font-mono text-sm leading-loose text-left min-h-[268px]">
                      <p><span className="text-accent-green">root@lab</span>:<span className="text-accent-blue">~</span># <span className="text-surface-200">systemctl status nginx</span></p>
                      <p className="text-accent-red">● nginx.service - A high performance web server</p>
                      <p className="text-surface-500 pl-3">Active: <span className="text-accent-red font-semibold">failed</span> (Result: exit-code)</p>
                      <p className="mt-2"><span className="text-accent-green">root@lab</span>:<span className="text-accent-blue">~</span># <span className="text-surface-200">nginx -t</span></p>
                      <p className="text-accent-red">nginx: [emerg] unknown directive &quot;listn&quot;</p>
                      <p className="mt-2"><span className="text-accent-green">root@lab</span>:<span className="text-accent-blue">~</span># <span className="text-accent-amber">vim /etc/nginx/sites-available/default</span></p>
                      <p><span className="text-accent-green">root@lab</span>:<span className="text-accent-blue">~</span># <span className="text-surface-200">systemctl restart nginx</span></p>
                      <p className="text-accent-green mt-2">● nginx.service - Active: <span className="font-semibold">active (running)</span></p>
                      <p className="text-accent-green mt-3 font-bold flex items-center gap-2">
                        <CheckCircle2 size={14} /> Challenge solved! Score: 185/200
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* RIGHT col — copy + CTAs */}
            <div className="animate-slide-up">
              {/* Eyebrow */}
              <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-cyan/10 border border-accent-cyan/20 text-accent-cyan text-sm mb-8 backdrop-blur-sm">
                <Sparkles size={14} className="animate-pulse" /> Build. Break. Fix. Learn.
              </div>

              {/* Headline */}
              <h1 className="text-5xl lg:text-6xl xl:text-[4.25rem] font-black text-white leading-[1.06] mb-6 tracking-tight">
                Master{' '}
                <span className="relative inline-block">
                  <span
                    className="text-transparent bg-clip-text bg-gradient-to-r from-accent-cyan via-accent-blue to-accent-purple animate-text-gradient text-glow-cyan"
                    style={{ backgroundSize: '200% auto' }}
                  >
                    Technology
                  </span>
                  <span
                    className="absolute -bottom-2 left-0 w-full h-1 bg-gradient-to-r from-accent-cyan via-accent-purple to-accent-pink rounded-full animate-shimmer"
                    style={{ backgroundSize: '200% 100%' }}
                  />
                </span>
                <br />by breaking things.
              </h1>

              {/* Sub-copy */}
              <p className="text-lg lg:text-xl text-surface-300 max-w-[480px] mb-10 leading-relaxed">
                Practice real-world skills on live environments — Linux, Docker, databases, cloud, networking, and more. Timed challenges, auto-validation, hints, and a global leaderboard.
              </p>

              {/* CTAs */}
              <div className="flex flex-col sm:flex-row gap-4 mb-12">
                <Link
                  to="/register"
                  className="group btn-primary text-base px-8 py-4 flex items-center justify-center gap-2 shadow-lg shadow-accent-cyan/25 hover:shadow-accent-cyan/45 transition-all"
                >
                  Start Fixing for Free
                  <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
                </Link>
                <Link
                  to="/scenarios"
                  className="btn-secondary text-base px-8 py-4 flex items-center justify-center gap-2"
                >
                  <Play size={16} /> Browse Challenges
                </Link>
              </div>

              {/* Live stats — only render when data is available */}
              {stats.total_scenarios > 0 && (
                <div className="flex flex-wrap items-center gap-8 pt-8 border-t border-surface-700/30">
                  {[
                    { val: `${stats.total_scenarios}+`,                    label: 'Scenarios', icon: Target       },
                    { val: `${stats.total_users?.toLocaleString()}+`,       label: 'Engineers', icon: Users        },
                    { val: `${stats.total_completions?.toLocaleString()}+`, label: 'Solves',    icon: CheckCircle2 },
                  ].map(({ val, label, icon: Icon }) => (
                    <div key={label} className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-accent-cyan/10 flex items-center justify-center shrink-0">
                        <Icon size={18} className="text-accent-cyan" />
                      </div>
                      <div>
                        <p className="text-2xl font-black text-white leading-none">{val}</p>
                        <p className="text-xs text-surface-400 uppercase tracking-wider mt-0.5">{label}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

          </div>
        </div>
      </section>
      {/* ─── end Hero ─── */}

      <div className="bg-gradient-stripe" />


      {/* ═══════════════════════════════════════════
          SECTION 2 — TECH RIBBON
      ═══════════════════════════════════════════ */}
      <section className="py-14 relative overflow-hidden">
        <div className="absolute inset-0 section-dark" />
        <div className="max-w-7xl mx-auto px-6 relative">
          <p className="text-center text-xs text-surface-500 uppercase tracking-[0.2em] font-semibold mb-10">
            Technologies You Can Master
          </p>
          <div className="flex items-center justify-center gap-10 flex-wrap">
            {trustedBy.map(({ name, icon: Icon }) => (
              <div
                key={name}
                className="flex items-center gap-2.5 text-surface-500 hover:text-accent-cyan transition-all duration-300 group cursor-default"
              >
                <Icon size={22} className="group-hover:scale-110 transition-transform duration-300" />
                <span className="text-sm font-semibold tracking-wide">{name}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="bg-gradient-stripe" />


      {/* ═══════════════════════════════════════════
          SECTION 3 — CHALLENGE MODES (3 cards)
      ═══════════════════════════════════════════ */}
      <section className="relative overflow-hidden py-28">
        <div className="absolute inset-0 bg-mesh-gradient" />
        <div className="absolute inset-0 bg-dots-pattern opacity-30 pointer-events-none" />
        <div className="glow-orb-purple absolute -left-40 top-1/3" />

        <div className="max-w-7xl mx-auto px-6 relative">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-purple/10 border border-accent-purple/20 text-accent-purple text-xs font-bold uppercase tracking-widest mb-5">
              <Code2 size={13} /> Challenge Modes
            </div>
            <h2 className="text-4xl lg:text-5xl font-black text-white mb-4 leading-tight">
              Three Ways to{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-cyan to-accent-purple">
                Prove Yourself
              </span>
            </h2>
            <p className="text-surface-400 max-w-xl mx-auto text-lg">
              Each scenario type tests a different depth of skill.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {scenarioTypes.map(({ type, icon: Icon, label, desc, color, gradient }) => (
              <Link
                to={`/scenarios?type=${type}`}
                key={type}
                className="glass-card-hover card-3d card-shine p-10 text-center group relative overflow-hidden"
              >
                <div className={`absolute inset-0 bg-gradient-to-br ${gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-500`} />
                <div className="relative">
                  <div className={`w-20 h-20 rounded-2xl bg-gradient-to-br ${gradient} border border-surface-700/40 flex items-center justify-center mx-auto mb-7 group-hover:scale-110 group-hover:border-accent-${color}/30 transition-all duration-300`}>
                    <Icon size={36} className={`text-accent-${color}`} />
                  </div>
                  <h3 className="text-2xl font-bold text-white mb-3">{label}</h3>
                  <p className="text-sm text-surface-400 leading-relaxed">{desc}</p>
                  <div className={`mt-7 flex items-center justify-center gap-1.5 text-sm text-accent-${color} opacity-0 group-hover:opacity-100 translate-y-1 group-hover:translate-y-0 transition-all duration-300 font-semibold`}>
                    Try now <ChevronRight size={14} />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <div className="bg-gradient-stripe" />


      {/* ═══════════════════════════════════════════
          SECTION 4 — TECHNOLOGIES GRID
          Live techs first, coming_soon last with badge
      ═══════════════════════════════════════════ */}
      <section className="relative overflow-hidden py-28">
        <div className="absolute inset-0 section-gradient" />
        <div className="glow-orb-cyan   absolute -right-40 top-1/2 -translate-y-1/2" />
        <div className="glow-orb-green  absolute -left-40  bottom-0" />

        <div className="max-w-7xl mx-auto px-6 relative">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-green/10 border border-accent-green/20 text-accent-green text-xs font-bold uppercase tracking-widest mb-5">
              <Layers size={13} /> Technologies
            </div>
            <h2 className="text-4xl lg:text-5xl font-black text-white mb-4 leading-tight">
              Choose Your{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-green to-accent-cyan">
                Technology
              </span>
            </h2>
            <p className="text-surface-400 max-w-xl mx-auto text-lg">
              Subscribe per technology. Cancel anytime.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6 max-w-5xl mx-auto">
            {[
              ...technologies.filter(t => !t.coming_soon),
              ...technologies.filter(t =>  t.coming_soon),
            ].map(tech => {
              const Icon = techIcons[tech.name] || Server

              if (tech.coming_soon) {
                return (
                  <div key={tech.id} className="glass-card p-8 text-center relative opacity-50 cursor-default">
                    <div className="absolute top-3 right-3 px-2 py-0.5 rounded-full bg-accent-amber/10 border border-accent-amber/25 text-accent-amber text-[10px] font-bold tracking-wider uppercase">
                      Coming Soon
                    </div>
                    <div className="w-[68px] h-[68px] rounded-2xl bg-surface-800 border border-surface-700 flex items-center justify-center mx-auto mb-5">
                      <Icon size={32} className="text-surface-600" />
                    </div>
                    <h3 className="text-base font-bold text-surface-500">{tech.name}</h3>
                  </div>
                )
              }

              return (
                <Link
                  to={isAuthenticated ? '/technologies' : '/register'}
                  key={tech.id}
                  className="glass-card-hover card-3d card-shine p-8 text-center group"
                >
                  <div className="w-[68px] h-[68px] rounded-2xl bg-gradient-to-br from-accent-cyan/15 to-accent-purple/15 border border-accent-cyan/20 flex items-center justify-center mx-auto mb-5 group-hover:scale-110 group-hover:border-accent-cyan/40 transition-all duration-300">
                    <Icon size={32} className="text-accent-cyan group-hover:text-white transition-colors" />
                  </div>
                  <h3 className="text-base font-bold text-white mb-1.5">{tech.name}</h3>
                  <p className="text-xs text-surface-500">
                    {tech.scenario_count || 0} scenario{tech.scenario_count !== 1 ? 's' : ''}
                  </p>
                  <div className="mt-5 flex items-center justify-center gap-1 text-xs text-accent-cyan opacity-0 group-hover:opacity-100 translate-y-1 group-hover:translate-y-0 transition-all duration-300 font-semibold">
                    Explore <ChevronRight size={12} />
                  </div>
                </Link>
              )
            })}
          </div>
        </div>
      </section>

      <div className="bg-gradient-stripe" />


      {/* ═══════════════════════════════════════════
          SECTION 5 — AI INTERVIEW STUDIO
          Rich purple gradient, face-to-face framing
          Left: copy + bullets  |  Right: InterviewDemoWidget
      ═══════════════════════════════════════════ */}
      <section className="relative overflow-hidden py-28">
        {/* Deep purple background */}
        <div
          className="absolute inset-0"
          style={{ background: 'linear-gradient(135deg, rgb(88 28 135 / 0.20) 0%, rgb(139 92 246 / 0.10) 40%, rgb(30 27 75 / 0.22) 70%, transparent 100%)' }}
        />
        <div className="absolute inset-0 bg-dots-pattern opacity-20 pointer-events-none" />
        <div className="glow-orb-purple absolute -left-32 top-1/3" style={{ width: '500px', height: '500px' }} />
        <div className="glow-orb-cyan   absolute  right-0  bottom-0" />

        <div className="max-w-7xl mx-auto px-6 relative">
          <div className="grid lg:grid-cols-2 gap-16 xl:gap-20 items-center">

            {/* LEFT — copy */}
            <div className="animate-slide-up">
              <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-purple/15 border border-accent-purple/30 text-accent-purple text-xs font-bold uppercase tracking-widest mb-7">
                <Mic2 size={13} className="animate-pulse" /> AI Interview Studio
              </div>

              <h2 className="text-4xl lg:text-5xl font-black text-white mb-6 leading-tight">
                Get Hired Faster with<br />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-purple via-accent-cyan to-accent-pink">
                  Face-to-Face AI Interviews
                </span>
              </h2>

              <p className="text-surface-300 text-lg mb-10 leading-relaxed">
                Sit across from a live AI interviewer in a real video call interface. Technical, behavioral, and system design rounds — resume-aware questions, instant STAR-framework scoring, and actionable feedback. 100% free, no API key required.
              </p>

              {/* Feature bullets */}
              <div className="space-y-5 mb-10">
                {[
                  { icon: Mic2,   title: 'Live voice-driven sessions',        desc: 'Speak naturally — browser STT captures your answer in real time, just like a real video call.',      color: 'purple' },
                  { icon: Star,   title: 'STAR scoring engine',               desc: 'Every answer scored on Situation, Task, Action, and Result coverage — instantly.',                     color: 'cyan'   },
                  { icon: Shield, title: '100% free — no paid APIs',          desc: 'Our in-process scoring engine runs with zero external cost or hidden rate limits.',                     color: 'green'  },
                  { icon: Award,  title: 'Verifiable FIXIT-INT certificates', desc: 'Earn certificates you can add to your résumé and LinkedIn after completing a round.',                   color: 'amber'  },
                ].map(({ icon: Icon, title, desc, color }) => (
                  <div key={title} className="flex items-start gap-4 group">
                    <div className={`w-10 h-10 rounded-xl bg-accent-${color}/10 border border-accent-${color}/20 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-105 group-hover:bg-accent-${color}/15 transition-all duration-200`}>
                      <Icon size={17} className={`text-accent-${color}`} />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-white leading-snug">{title}</p>
                      <p className="text-xs text-surface-400 mt-1 leading-relaxed">{desc}</p>
                    </div>
                  </div>
                ))}
              </div>

              {/* CTAs */}
              <div className="flex flex-col sm:flex-row gap-3">
                <Link
                  to={isAuthenticated ? '/interview-hub' : '/register'}
                  className="btn-primary px-7 py-3.5 flex items-center gap-2 group shadow-lg shadow-accent-purple/25 hover:shadow-accent-purple/40 transition-all"
                >
                  <Mic2 size={16} className="group-hover:scale-110 transition-transform" />
                  Start Mock Interview
                  <ArrowRight size={15} className="group-hover:translate-x-0.5 transition-transform" />
                </Link>
                <Link to="/mock-interviews" className="btn-secondary px-6 py-3.5 flex items-center gap-2">
                  <Play size={14} /> Watch Demo
                </Link>
              </div>
            </div>

            {/* RIGHT — live InterviewDemoWidget */}
            <div className="hidden lg:block animate-slide-in-right">
              <div className="relative">
                <div className="absolute -inset-8 bg-gradient-to-r from-accent-purple/12 via-accent-cyan/8 to-accent-pink/8 rounded-3xl blur-3xl animate-pulse-glow" />
                <InterviewDemoWidget />
              </div>
            </div>

          </div>

          {/* Mobile: widget stacked below copy */}
          <div className="lg:hidden mt-14">
            <InterviewDemoWidget />
          </div>
        </div>
      </section>

      <div className="bg-gradient-stripe" />


      {/* ═══════════════════════════════════════════
          SECTION 6 — FEATURES GRID
          Strict 2×4 on desktop — 8 features, no orphans
      ═══════════════════════════════════════════ */}
      <section className="relative overflow-hidden py-28">
        <div className="absolute inset-0 section-accent" />
        <div className="absolute inset-0 bg-mesh-gradient-intense opacity-40" />
        <div className="glow-orb-blue absolute left-1/4 top-0" />
        <div className="glow-orb-pink absolute right-0 bottom-0" />

        <div className="max-w-7xl mx-auto px-6 relative">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-cyan/10 border border-accent-cyan/20 text-accent-cyan text-xs font-bold uppercase tracking-widest mb-5">
              <Rocket size={13} /> Platform Features
            </div>
            <h2 className="text-4xl lg:text-5xl font-black text-white mb-4 leading-tight">
              Built for{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-cyan to-accent-blue">
                Serious Engineers
              </span>
            </h2>
            <p className="text-surface-400 max-w-xl mx-auto text-lg">
              Everything you need to master any technology — in one platform.
            </p>
          </div>

          {/* 2×4 grid — exactly 8 items */}
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map(({ icon: Icon, title, desc, color }, idx) => (
              <div
                key={title}
                className="glass-card-hover card-shine p-7 group"
                style={{ animationDelay: `${idx * 0.08}s` }}
              >
                <div className={`w-14 h-14 rounded-xl bg-gradient-to-br from-accent-${color}/20 to-accent-${color}/5 border border-accent-${color}/20 flex items-center justify-center mb-5 group-hover:scale-110 group-hover:border-accent-${color}/35 transition-all duration-300`}>
                  <Icon size={24} className={`text-accent-${color}`} />
                </div>
                <h3 className="text-base font-bold text-white mb-2 leading-snug">{title}</h3>
                <p className="text-sm text-surface-400 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="bg-gradient-stripe" />


      {/* ═══════════════════════════════════════════
          SECTION 7 — HOW IT WORKS (3 steps)
      ═══════════════════════════════════════════ */}
      <section className="relative overflow-hidden py-28">
        <div className="absolute inset-0 section-dark" />
        <div className="glow-orb-purple absolute left-1/4 -top-20" />
        <div className="glow-orb-cyan   absolute right-0   bottom-1/4" />

        <div className="max-w-7xl mx-auto px-6 relative">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-amber/10 border border-accent-amber/20 text-accent-amber text-xs font-bold uppercase tracking-widest mb-5">
              <GraduationCap size={13} /> How It Works
            </div>
            <h2 className="text-4xl lg:text-5xl font-black text-white mb-4 leading-tight">
              Up and Running in{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-amber to-accent-red">
                30 Seconds
              </span>
            </h2>
            <p className="text-surface-400 max-w-xl mx-auto text-lg">
              No setup. No SSH keys. No VMs to configure. Just click and fix.
            </p>
          </div>

          {/* 3 steps */}
          <div className="grid md:grid-cols-3 gap-10 max-w-4xl mx-auto">
            {[
              { step: '01', title: 'Pick a Challenge', desc: 'Browse by technology, difficulty, and type. Filter by tags or search for something specific.',          icon: BookOpen,     color: 'cyan'   },
              { step: '02', title: 'Launch the Lab',   desc: 'An isolated container or cloud instance spins up in seconds — real environment, zero configuration.',  icon: Monitor,      color: 'purple' },
              { step: '03', title: 'Fix & Validate',   desc: 'Use the real terminal to diagnose and repair. Click "Check Solution" to score instantly.',              icon: CheckCircle2, color: 'green'  },
            ].map(({ step, title, desc, icon: Icon, color }, idx) => (
              <div key={step} className="flex flex-col items-center text-center relative group">
                {/* Connector line */}
                {idx < 2 && (
                  <div className="hidden md:block absolute top-10 left-[62%] w-[76%] h-px bg-gradient-to-r from-surface-600 via-accent-cyan/20 to-transparent" />
                )}

                {/* Icon */}
                <div className={`w-20 h-20 rounded-2xl bg-gradient-to-br from-accent-${color}/20 to-accent-${color}/5 border border-surface-700/50 flex items-center justify-center mb-6 group-hover:scale-110 group-hover:border-accent-${color}/30 transition-all duration-300`}>
                  <Icon size={30} className={`text-accent-${color}`} />
                </div>

                {/* Step pill */}
                <div className={`inline-block text-xs text-accent-${color} font-bold bg-accent-${color}/10 border border-accent-${color}/20 rounded-full px-3 py-1 mb-3`}>
                  Step {step}
                </div>

                <h3 className="text-lg font-bold text-white mb-2">{title}</h3>
                <p className="text-sm text-surface-400 leading-relaxed max-w-[240px]">{desc}</p>
              </div>
            ))}
          </div>

          {/* Inline CTA */}
          <div className="mt-16 text-center">
            <Link
              to="/register"
              className="group btn-primary text-base px-9 py-4 inline-flex items-center gap-2 shadow-lg shadow-accent-cyan/25 hover:shadow-accent-cyan/40 transition-all"
            >
              Try Your First Challenge Free
              <ArrowRight size={17} className="group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </div>
      </section>

      <div className="bg-gradient-stripe" />


      {/* ═══════════════════════════════════════════
          SECTION 8 — TESTIMONIALS CAROUSEL
      ═══════════════════════════════════════════ */}
      <section className="relative overflow-hidden py-28">
        <div className="absolute inset-0 section-dark" />
        <div className="absolute inset-0 bg-dots-pattern opacity-20 pointer-events-none" />
        <div className="glow-orb-pink absolute right-0 top-0" />
        <div className="glow-orb-cyan  absolute left-0  bottom-0" />

        <div className="max-w-7xl mx-auto px-6 relative">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-amber/10 border border-accent-amber/20 text-accent-amber text-xs font-bold uppercase tracking-widest mb-5">
              <Star size={13} /> Testimonials
            </div>
            <h2 className="text-4xl lg:text-5xl font-black text-white mb-4 leading-tight">
              Loved by{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-amber to-accent-red">
                Engineers
              </span>
            </h2>
            <p className="text-surface-400 text-lg">
              Trusted by engineers, developers, and IT professionals worldwide.
            </p>
          </div>

          <div className="max-w-3xl mx-auto">
            <div className="glass-card p-10 relative overflow-hidden gradient-border">
              <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/5 via-transparent to-accent-purple/5" />
              <div className="relative">
                {/* Stars */}
                <div className="flex gap-1 mb-6">
                  {[...Array(5)].map((_, i) => (
                    <Star key={i} size={18} className="text-accent-amber fill-accent-amber" />
                  ))}
                </div>

                {/* Quote */}
                <blockquote className="text-xl text-surface-200 leading-relaxed mb-8 italic font-light">
                  &ldquo;{testimonials[activeTestimonial].text}&rdquo;
                </blockquote>

                {/* Author */}
                <div className="flex items-center gap-4">
                  <div className="w-14 h-14 rounded-full bg-gradient-to-br from-accent-cyan to-accent-purple flex items-center justify-center text-lg font-bold text-white shadow-lg shadow-accent-cyan/20 shrink-0">
                    {testimonials[activeTestimonial].name.split(' ').map(n => n[0]).join('')}
                  </div>
                  <div>
                    <p className="text-lg font-bold text-white leading-snug">
                      {testimonials[activeTestimonial].name}
                    </p>
                    <p className="text-sm text-surface-400 mt-0.5">
                      {testimonials[activeTestimonial].role} &middot; {testimonials[activeTestimonial].company}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Dot indicators */}
            <div className="flex justify-center gap-2.5 mt-7">
              {testimonials.map((_, i) => (
                <button
                  key={i}
                  onClick={() => setActiveTestimonial(i)}
                  aria-label={`Testimonial ${i + 1}`}
                  className={`h-2.5 rounded-full transition-all duration-300 ${
                    i === activeTestimonial
                      ? 'bg-accent-cyan w-8'
                      : 'bg-surface-600 hover:bg-surface-500 w-2.5'
                  }`}
                />
              ))}
            </div>
          </div>
        </div>
      </section>

      <div className="bg-gradient-stripe" />


      {/* ═══════════════════════════════════════════
          SECTION 9 — PRICING CTA
      ═══════════════════════════════════════════ */}
      <section className="py-28 relative">
        <div className="glow-orb-cyan   absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2" />
        <div className="glow-orb-purple absolute -right-20 top-0" />

        <div className="max-w-4xl mx-auto px-6 text-center relative">
          <div className="glass-card p-16 relative overflow-hidden gradient-border">
            <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/8 via-transparent to-accent-purple/8" />
            <div className="absolute inset-0 bg-grid-pattern opacity-20" />

            <div className="relative">
              <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-cyan/10 border border-accent-cyan/20 text-accent-cyan text-xs font-bold uppercase tracking-widest mb-7">
                <Sparkles size={13} /> Get Started Today
              </div>

              <h2 className="text-4xl lg:text-5xl font-black text-white mb-6 leading-tight">
                Ready to prove your{' '}
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-cyan to-accent-purple">
                  skills?
                </span>
              </h2>

              <p className="text-surface-400 mb-10 max-w-md mx-auto text-lg leading-relaxed">
                Free demo included. Subscribe per technology. Start troubleshooting in under 30 seconds.
              </p>

              {/* Value props */}
              <div className="flex flex-wrap justify-center gap-6 mb-12">
                {[
                  { icon: CheckCircle2, text: 'Free demo always available' },
                  { icon: Zap,          text: 'Live lab in 30 seconds'     },
                  { icon: Lock,         text: 'No credit card required'    },
                ].map(({ icon: Icon, text }) => (
                  <div key={text} className="flex items-center gap-2 text-sm text-surface-400">
                    <Icon size={15} className="text-accent-cyan shrink-0" />
                    {text}
                  </div>
                ))}
              </div>

              {/* CTAs */}
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Link
                  to="/register"
                  className="group btn-primary text-lg px-10 py-4 inline-flex items-center gap-2 shadow-lg shadow-accent-cyan/30 hover:shadow-accent-cyan/50 transition-all"
                >
                  Create Free Account
                  <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
                </Link>
                <Link to="/about" className="btn-secondary text-lg px-10 py-4 inline-flex items-center gap-2">
                  Learn More
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>


      {/* ═══════════════════════════════════════════
          FOOTER
      ═══════════════════════════════════════════ */}
      <footer className="border-t border-surface-700/30 relative overflow-hidden">
        <div className="absolute inset-0 section-dark" />

        <div className="max-w-7xl mx-auto px-6 py-16 relative">
          <div className="grid md:grid-cols-5 gap-10">

            {/* Brand */}
            <div className="md:col-span-2">
              <Link to="/" className="flex items-center gap-2.5 mb-5 group w-fit">
                <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-accent-cyan to-accent-blue flex items-center justify-center shadow-lg shadow-accent-cyan/20 group-hover:shadow-accent-cyan/35 transition-shadow">
                  <Terminal size={18} className="text-white" />
                </div>
                <span className="text-xl font-bold text-white">FixitLab</span>
              </Link>
              <p className="text-sm text-surface-400 leading-relaxed max-w-xs">
                Hands-on labs for Linux, Docker, databases, cloud, networking, and security. Learn by doing, not reading.
              </p>
            </div>

            {/* Product */}
            <div>
              <h4 className="text-xs font-bold text-white uppercase tracking-[0.12em] mb-5">Product</h4>
              <div className="space-y-3">
                {[
                  ['Scenarios',      '/scenarios'],
                  ['Mock Interviews', '/mock-interviews'],
                  ['Pricing',         '/pricing'],
                  ['Leaderboard',     '/leaderboard'],
                  ['Technologies',    '/technologies'],
                ].map(([label, to]) => (
                  <Link key={to} to={to} className="block text-sm text-surface-400 hover:text-accent-cyan transition-colors">
                    {label}
                  </Link>
                ))}
              </div>
            </div>

            {/* Resources */}
            <div>
              <h4 className="text-xs font-bold text-white uppercase tracking-[0.12em] mb-5">Resources</h4>
              <div className="space-y-3">
                {[
                  ['Blog',               '/blog'],
                  ['FAQ',                '/faq'],
                  ['Community',          '/community'],
                  ['Verify Certificate', '/verify-certificate'],
                ].map(([label, to]) => (
                  <Link key={to} to={to} className="block text-sm text-surface-400 hover:text-accent-cyan transition-colors">
                    {label}
                  </Link>
                ))}
              </div>
            </div>

            {/* Company */}
            <div>
              <h4 className="text-xs font-bold text-white uppercase tracking-[0.12em] mb-5">Company</h4>
              <div className="space-y-3">
                {[
                  ['About',   '/about'],
                  ['Privacy', '/privacy'],
                  ['Terms',   '/terms'],
                  ['Contact', '/contact'],
                ].map(([label, to]) => (
                  <Link key={to} to={to} className="block text-sm text-surface-400 hover:text-accent-cyan transition-colors">
                    {label}
                  </Link>
                ))}
              </div>
            </div>

          </div>

          {/* Bottom bar */}
          <div className="mt-14 pt-8 border-t border-surface-700/30 flex flex-col sm:flex-row items-center justify-between text-xs text-surface-500 gap-4">
            <span>&copy; 2026 FixitLab. All rights reserved.</span>
            <span>Built with passion for engineers and developers worldwide.</span>
          </div>
        </div>
      </footer>

    </div>
  )
}
