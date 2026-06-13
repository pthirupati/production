import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { scenarioApi } from '../api/scenarios'
import api from '../api/client'
import { PlatformBanners } from '../components/PlatformBanners'
import {
  Terminal, Shield, Clock, Trophy, Zap, Server,
  Cloud, Lock, Cpu, ArrowRight, CheckCircle2,
  Users, Award, BookOpen, Wrench, Skull, Play,
  Star, ChevronRight, Monitor, Globe, Sun, Moon,
  Sparkles, Code2, Rocket, GraduationCap, Layers,
  Activity, GitBranch, Database, Target, Flame, Menu, X
} from 'lucide-react'

const features = [
  { icon: Terminal, title: 'Real Terminal', desc: 'Full interactive bash shell in your browser \u2014 connected to a real Linux environment via WebSocket', color: 'cyan' },
  { icon: Shield, title: 'Isolated Sandbox', desc: 'Every challenge runs in its own Docker container with security constraints. Break anything safely.', color: 'purple' },
  { icon: Clock, title: 'Timed Challenges', desc: 'Race against the clock. Faster solves earn bonus points \u2014 just like real incident response.', color: 'amber' },
  { icon: Trophy, title: 'Leaderboard & Scoring', desc: 'Compete globally, track rankings per technology, and earn achievements for milestones.', color: 'green' },
  { icon: Zap, title: 'Auto-Validation', desc: 'Click "Check Solution" and our validation engine runs inside your container to verify the fix.', color: 'cyan' },
  { icon: Lock, title: 'Progressive Hints', desc: 'Stuck? Reveal hints one by one with transparent score penalties. Learn without the frustration.', color: 'purple' },
  { icon: Award, title: 'Achievements & Badges', desc: 'Earn badges for speed, streaks, perfect scores, and solving without hints.', color: 'amber' },
  { icon: BookOpen, title: 'Solution Explanations', desc: 'After solving, review the detailed explanation to deepen your understanding.', color: 'green' },
]

const scenarioTypes = [
  { type: 'fix', icon: Wrench, label: 'Fix It', desc: 'Something is broken \u2014 diagnose the issue and repair it before time runs out', color: 'cyan', gradient: 'from-accent-cyan/20 to-accent-blue/10' },
  { type: 'do', icon: Play, label: 'Build It', desc: 'Complete a task from scratch \u2014 configure services, set up infrastructure', color: 'green', gradient: 'from-accent-green/20 to-emerald-400/10' },
  { type: 'hack', icon: Skull, label: 'Hack It', desc: 'Exploit a vulnerability, find a hidden flag, or break into a misconfigured system', color: 'red', gradient: 'from-accent-red/20 to-rose-400/10' },
]

const testimonials = [
  { name: 'Arun Kumar', role: 'Senior DevOps Engineer', company: 'Infosys', text: 'FixitLab is the closest thing to real incident response practice. Way better than reading docs. The timed challenges really simulate production pressure.' },
  { name: 'Ravi Patel', role: 'Site Reliability Engineer', company: 'Google', text: 'I use this to prep for interviews. The container-based labs are incredibly realistic \u2014 feels like SSHing into a real broken server.' },
  { name: 'Maria Lee', role: 'Junior SysAdmin', company: 'DigitalOcean', text: 'Finally a platform that teaches Linux the right way \u2014 by breaking things and fixing them. The hint system is brilliant.' },
  { name: 'Erik Volkov', role: 'Cloud Architect', company: 'AWS', text: 'The progressive difficulty and achievement system keeps me coming back. I learn something new every time, even on easy challenges.' },
]

const trustedBy = [
  { name: 'Linux', icon: Server },
  { name: 'Docker', icon: Monitor },
  { name: 'Networking', icon: Globe },
  { name: 'AWS', icon: Cloud },
  { name: 'Kubernetes', icon: Cpu },
  { name: 'Database', icon: Database },
]

export default function Home() {
  const { isAuthenticated } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const [technologies, setTechnologies] = useState([])
  const [stats, setStats] = useState({})
  const [platformConfig, setPlatformConfig] = useState(null)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [activeTestimonial, setActiveTestimonial] = useState(0)

  useEffect(() => {
    scenarioApi.getTechnologies().then(setTechnologies).catch(() => {})
    scenarioApi.getPlatformStats().then(setStats).catch(() => {})
    api.get('/config/').then(res => setPlatformConfig(res.data)).catch(() => {})
  }, [])

  useEffect(() => {
    const timer = setInterval(() => {
      setActiveTestimonial(prev => (prev + 1) % testimonials.length)
    }, 5000)
    return () => clearInterval(timer)
  }, [])

  const techIcons = { Linux: Server, AWS: Cloud, Kubernetes: Cpu, Docker: Monitor, Networking: Globe }

  return (
    <div className="min-h-screen bg-surface-950">
      <PlatformBanners config={platformConfig} showMaintenance showPromo />
      {/* Navbar */}
      <nav className="border-b border-surface-700/30 backdrop-blur-2xl sticky top-0 z-50 bg-surface-950/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-accent-cyan to-accent-blue flex items-center justify-center shadow-lg shadow-accent-cyan/25 group-hover:shadow-accent-cyan/40 transition-shadow">
              <Terminal size={18} className="text-white" />
            </div>
            <span className="text-xl font-bold text-white tracking-tight">FixitLab</span>
          </Link>
          <div className="hidden md:flex items-center gap-6">
            {[
              { to: '/scenarios', label: 'Scenarios' },
              { to: '/leaderboard', label: 'Leaderboard' },
              { to: '/pricing', label: 'Pricing' },
              { to: '/faq', label: 'FAQ' },
              { to: '/verify-certificate', label: 'Verify Certificate' },
              { to: '/contact', label: 'Contact' },
            ].map(({ to, label }) => (
              <Link key={to} to={to} className="text-sm text-surface-400 hover:text-white transition-colors relative group">
                {label}
                <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-gradient-to-r from-accent-cyan to-accent-purple group-hover:w-full transition-all duration-300" />
              </Link>
            ))}
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <button type="button" className="md:hidden p-2 text-surface-400" onClick={() => setMobileNavOpen(v => !v)} aria-label="Menu">
              {mobileNavOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
            <button onClick={toggleTheme} className="p-2 rounded-lg text-surface-400 hover:text-white hover:bg-surface-800/50 transition-all" aria-label="Toggle theme">
              {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            {isAuthenticated ? (
              <Link to="/dashboard" className="btn-primary text-sm px-5">Dashboard</Link>
            ) : (
              <>
                <Link to="/login" className="text-sm text-surface-300 hover:text-white transition-colors px-3 py-2 hidden sm:block">Sign In</Link>
                <Link to="/register" className="btn-primary text-sm px-5">Get Started Free</Link>
              </>
            )}
          </div>
        </div>
        {mobileNavOpen && (
          <div className="md:hidden border-t border-surface-800 px-4 py-3 flex flex-col gap-2 bg-surface-950/95">
            {['/scenarios', '/leaderboard', '/pricing', '/faq', '/contact'].map(to => (
              <Link key={to} to={to} onClick={() => setMobileNavOpen(false)} className="text-sm text-surface-300 py-2">{to.slice(1).replace('-', ' ')}</Link>
            ))}
          </div>
        )}
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden min-h-[90vh] flex items-center">
        <div className="absolute inset-0">
          <div className="absolute inset-0 hero-gradient" />
          <div className="absolute inset-0 hero-grid" />
          <div className="glow-orb-cyan absolute -top-32 left-1/4 animate-morph" />
          <div className="glow-orb-purple absolute top-1/3 -right-20 animate-float" />
          <div className="glow-orb-blue absolute bottom-0 left-0 animate-float-delayed" />
          <div className="glow-orb-pink absolute -bottom-40 right-1/3 animate-morph" style={{ animationDelay: '3s' }} />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[900px] opacity-[0.06] animate-rotate-slow pointer-events-none">
            <div className="w-full h-full rounded-full border-2 border-dashed border-accent-cyan" />
          </div>
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[650px] h-[650px] opacity-[0.04] animate-rotate-slow pointer-events-none" style={{ animationDirection: 'reverse', animationDuration: '20s' }}>
            <div className="w-full h-full rounded-full border border-dashed border-accent-purple" />
          </div>
          {[...Array(16)].map((_, i) => (
            <div key={i} className="particle" style={{
              width: `${2 + (i % 4) * 2}px`, height: `${2 + (i % 4) * 2}px`,
              background: i % 4 === 0 ? 'rgb(var(--a-cyan) / 0.5)' : i % 4 === 1 ? 'rgb(var(--a-purple) / 0.4)' : i % 4 === 2 ? 'rgb(var(--a-pink) / 0.4)' : 'rgb(var(--a-green) / 0.4)',
              top: `${5 + i * 5.5}%`, left: `${3 + i * 6}%`,
              animationDelay: `${i * 0.5}s`, animationDuration: `${6 + i * 0.5}s`,
            }} />
          ))}
        </div>
        <div className="max-w-7xl mx-auto px-6 py-20 lg:py-28 relative">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <div className="animate-slide-up">
              <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-cyan/10 border border-accent-cyan/20 text-accent-cyan text-sm mb-8 backdrop-blur-sm">
                <Sparkles size={14} className="animate-pulse" /> Build. Break. Fix. Learn.
              </div>
              <h1 className="text-5xl lg:text-6xl xl:text-7xl font-black text-white leading-[1.05] mb-6 tracking-tight">
                Master
                <span className="relative inline-block mx-3">
                  <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-cyan via-accent-blue to-accent-purple animate-text-gradient text-glow-cyan" style={{ backgroundSize: '200% auto' }}>Technology</span>
                  <span className="absolute -bottom-2 left-0 w-full h-1.5 bg-gradient-to-r from-accent-cyan via-accent-purple to-accent-pink rounded-full animate-shimmer" style={{ backgroundSize: '200% 100%' }} />
                </span>
                <br />by breaking things
              </h1>
              <p className="text-lg lg:text-xl text-surface-300 max-w-lg mb-10 leading-relaxed">
                Practice real-world skills on live environments — Linux, Docker, databases, cloud, networking, and more. Timed challenges, auto-validation, hints, and a global leaderboard.
              </p>
              <div className="flex flex-col sm:flex-row gap-4">
                <Link to="/register" className="group btn-primary text-base px-8 py-4 flex items-center justify-center gap-2 shadow-lg shadow-accent-cyan/30 hover:shadow-accent-cyan/50 transition-all">
                  Start Fixing for Free <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
                </Link>
                <Link to="/scenarios" className="btn-secondary text-base px-8 py-4 flex items-center justify-center gap-2">
                  <Play size={16} /> Browse Challenges
                </Link>
              </div>
              {(stats.total_scenarios > 0) && (
                <div className="flex items-center gap-10 mt-12 pt-8 border-t border-surface-700/30">
                  {[
                    { val: `${stats.total_scenarios}+`, label: 'Scenarios', icon: Target },
                    { val: `${stats.total_users?.toLocaleString()}+`, label: 'Engineers', icon: Users },
                    { val: `${stats.total_completions?.toLocaleString()}+`, label: 'Solves', icon: CheckCircle2 },
                  ].map(({ val, label, icon: Icon }) => (
                    <div key={label} className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-accent-cyan/10 flex items-center justify-center"><Icon size={18} className="text-accent-cyan" /></div>
                      <div><p className="text-2xl font-black text-white">{val}</p><p className="text-xs text-surface-400 uppercase tracking-wider">{label}</p></div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            {/* Terminal preview */}
            <div className="hidden lg:block animate-slide-in-right">
              <div className="relative">
                <div className="absolute -inset-8 bg-gradient-to-r from-accent-cyan/15 via-accent-purple/10 to-accent-pink/10 rounded-3xl blur-3xl animate-pulse-glow" />
                <div className="glass-card p-1 card-3d gradient-border relative">
                  <div className="absolute -top-5 -right-5 bg-surface-800/90 backdrop-blur-xl border border-accent-green/30 rounded-xl px-4 py-2 text-xs text-accent-green font-semibold flex items-center gap-2 z-10 shadow-lg shadow-accent-green/10">
                    <div className="w-2.5 h-2.5 rounded-full bg-accent-green animate-pulse" /> Live Session
                  </div>
                  <div className="bg-surface-950 rounded-lg overflow-hidden">
                    <div className="flex items-center gap-2 px-4 py-3 bg-surface-900/80 border-b border-surface-700/50">
                      <div className="w-3 h-3 rounded-full bg-accent-red/80" />
                      <div className="w-3 h-3 rounded-full bg-accent-amber/80" />
                      <div className="w-3 h-3 rounded-full bg-accent-green/80" />
                      <span className="ml-3 text-xs text-surface-500 font-mono">root@fixitlab ~ broken-nginx</span>
                      <span className="ml-auto text-xs text-accent-amber font-mono flex items-center gap-1"><Clock size={10} /> 12:34</span>
                    </div>
                    <div className="p-5 font-mono text-sm leading-loose text-left">
                      <p><span className="text-accent-green">root@lab</span>:<span className="text-accent-blue">~</span># <span className="text-surface-200">systemctl status nginx</span></p>
                      <p className="text-accent-red">{'\u25cf'} nginx.service - A high performance web server</p>
                      <p className="text-surface-500">   Active: <span className="text-accent-red font-semibold">failed</span> (Result: exit-code)</p>
                      <p className="mt-2"><span className="text-accent-green">root@lab</span>:<span className="text-accent-blue">~</span># <span className="text-surface-200">nginx -t</span></p>
                      <p className="text-accent-red">nginx: [emerg] unknown directive &quot;listn&quot;</p>
                      <p className="mt-2"><span className="text-accent-green">root@lab</span>:<span className="text-accent-blue">~</span># <span className="text-accent-amber">vim /etc/nginx/sites-available/default</span></p>
                      <p><span className="text-accent-green">root@lab</span>:<span className="text-accent-blue">~</span># <span className="text-surface-200">systemctl restart nginx</span></p>
                      <p className="text-accent-green mt-2">{'\u25cf'} nginx.service - Active: <span className="font-semibold">active (running)</span></p>
                      <p className="text-accent-green mt-3 font-bold flex items-center gap-2"><CheckCircle2 size={14} /> Challenge solved! Score: 185/200</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="bg-gradient-stripe" />

      {/* Technology Ribbon */}
      <section className="py-12 relative overflow-hidden">
        <div className="absolute inset-0 section-dark" />
        <div className="max-w-7xl mx-auto px-6 relative">
          <p className="text-center text-sm text-surface-500 uppercase tracking-widest mb-8 font-semibold">Technologies You Can Master</p>
          <div className="flex items-center justify-center gap-10 flex-wrap">
            {trustedBy.map(({ name, icon: Icon }) => (
              <div key={name} className="flex items-center gap-2.5 text-surface-400 hover:text-accent-cyan transition-all duration-300 group cursor-default">
                <Icon size={24} className="group-hover:scale-110 transition-transform" />
                <span className="text-sm font-medium">{name}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="bg-gradient-stripe" />

      {/* Challenge Modes */}
      <section className="relative overflow-hidden py-24">
        <div className="absolute inset-0 bg-mesh-gradient" />
        <div className="absolute inset-0 bg-dots-pattern opacity-30 pointer-events-none" />
        <div className="glow-orb-purple absolute -left-40 top-1/3" />
        <div className="max-w-7xl mx-auto px-6 relative">
          <div className="text-center mb-14">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-purple/10 border border-accent-purple/20 text-accent-purple text-xs font-bold uppercase tracking-widest mb-5">
              <Code2 size={13} /> Challenge Modes
            </div>
            <h2 className="text-4xl lg:text-5xl font-black text-white mb-4">Three Ways to <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-cyan to-accent-purple">Prove Yourself</span></h2>
            <p className="text-surface-400 max-w-2xl mx-auto text-lg">Each scenario tests a different skill.</p>
          </div>
          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {scenarioTypes.map(({ type, icon: Icon, label, desc, color, gradient }) => (
              <Link to={`/scenarios?type=${type}`} key={type} className="glass-card-hover card-3d card-shine p-8 text-center group relative overflow-hidden">
                <div className={`absolute inset-0 bg-gradient-to-br ${gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-500`} />
                <div className="relative">
                  <div className={`w-20 h-20 rounded-2xl bg-gradient-to-br ${gradient} flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-all duration-300`}>
                    <Icon size={36} className={`text-accent-${color}`} />
                  </div>
                  <h3 className="text-2xl font-bold text-white mb-3">{label}</h3>
                  <p className="text-sm text-surface-400 leading-relaxed">{desc}</p>
                  <div className="mt-6 flex items-center justify-center gap-1.5 text-sm text-accent-cyan opacity-0 group-hover:opacity-100 transition-all duration-300 font-medium">Try now <ChevronRight size={14} /></div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <div className="bg-gradient-stripe" />

      {/* Technologies */}
      <section className="relative overflow-hidden py-24">
        <div className="absolute inset-0 section-gradient" />
        <div className="glow-orb-cyan absolute -right-40 top-1/2 -translate-y-1/2" />
        <div className="glow-orb-green absolute -left-40 bottom-0" />
        <div className="max-w-7xl mx-auto px-6 relative">
          <div className="text-center mb-14">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-green/10 border border-accent-green/20 text-accent-green text-xs font-bold uppercase tracking-widest mb-5">
              <Layers size={13} /> Technologies
            </div>
            <h2 className="text-4xl lg:text-5xl font-black text-white mb-4">Choose Your <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-green to-accent-cyan">Technology</span></h2>
            <p className="text-surface-400 max-w-2xl mx-auto text-lg">Subscribe to the technologies you want to master.</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6 max-w-5xl mx-auto">
            {technologies.map((tech) => {
              const Icon = techIcons[tech.name] || Server
              return (
                <Link to={isAuthenticated ? '/technologies' : '/register'} key={tech.id} className="glass-card-hover card-3d card-shine p-8 text-center group">
                  <div className="w-[72px] h-[72px] rounded-2xl bg-gradient-to-br from-accent-cyan/15 to-accent-purple/15 border border-accent-cyan/20 flex items-center justify-center mx-auto mb-5 group-hover:scale-110 group-hover:border-accent-cyan/40 transition-all duration-300">
                    <Icon size={34} className="text-accent-cyan group-hover:text-white transition-colors" />
                  </div>
                  <h3 className="text-lg font-bold text-white mb-1.5">{tech.name}</h3>
                  <p className="text-sm text-surface-500">{tech.scenario_count || 0} scenario{tech.scenario_count !== 1 && 's'}</p>
                  <div className="mt-5 flex items-center justify-center gap-1 text-xs text-accent-cyan opacity-0 group-hover:opacity-100 transition-all duration-300 font-medium">Explore <ChevronRight size={12} /></div>
                </Link>
              )
            })}
            {['AWS', 'Kubernetes'].filter(n => !technologies.find(t => t.name === n)).map(name => (
              <div key={name} className="glass-card p-8 text-center opacity-40">
                <div className="w-[72px] h-[72px] rounded-2xl bg-surface-800 border border-surface-700 flex items-center justify-center mx-auto mb-5">
                  {name === 'AWS' ? <Cloud size={34} className="text-surface-600" /> : <Cpu size={34} className="text-surface-600" />}
                </div>
                <h3 className="text-lg font-bold text-surface-500 mb-1.5">{name}</h3>
                <p className="text-sm text-surface-600">Coming soon</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="bg-gradient-stripe" />

      {/* Features Grid */}
      <section className="relative overflow-hidden py-24">
        <div className="absolute inset-0 section-accent" />
        <div className="absolute inset-0 bg-mesh-gradient-intense opacity-40" />
        <div className="glow-orb-blue absolute left-1/4 top-0" />
        <div className="glow-orb-pink absolute right-0 bottom-0" />
        <div className="max-w-7xl mx-auto px-6 relative">
          <div className="text-center mb-14">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-cyan/10 border border-accent-cyan/20 text-accent-cyan text-xs font-bold uppercase tracking-widest mb-5">
              <Rocket size={13} /> Platform Features
            </div>
            <h2 className="text-4xl lg:text-5xl font-black text-white mb-4">Built for <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-cyan to-accent-blue">Serious Engineers</span></h2>
            <p className="text-surface-400 max-w-2xl mx-auto text-lg">Everything you need to master any technology.</p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map(({ icon: Icon, title, desc, color }, idx) => (
              <div key={title} className="glass-card-hover card-shine p-7 group" style={{ animationDelay: `${idx * 0.1}s` }}>
                <div className={`w-14 h-14 rounded-xl bg-gradient-to-br from-accent-${color}/20 to-accent-${color}/5 border border-accent-${color}/20 flex items-center justify-center mb-5 group-hover:scale-110 transition-all duration-300`}>
                  <Icon size={24} className={`text-accent-${color}`} />
                </div>
                <h3 className="text-base font-bold text-white mb-2">{title}</h3>
                <p className="text-sm text-surface-400 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="bg-gradient-stripe" />

      {/* How it works */}
      <section className="relative overflow-hidden py-24">
        <div className="absolute inset-0 section-dark" />
        <div className="glow-orb-purple absolute left-1/4 top-0" />
        <div className="glow-orb-cyan absolute right-0 bottom-1/4" />
        <div className="max-w-7xl mx-auto px-6 relative">
          <div className="text-center mb-14">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-amber/10 border border-accent-amber/20 text-accent-amber text-xs font-bold uppercase tracking-widest mb-5">
              <GraduationCap size={13} /> How It Works
            </div>
            <h2 className="text-4xl lg:text-5xl font-black text-white mb-4">Four Simple <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-amber to-accent-red">Steps</span></h2>
          </div>
          <div className="grid md:grid-cols-4 gap-8 max-w-5xl mx-auto">
            {[
              { step: '01', title: 'Pick a Challenge', desc: 'Browse by technology, difficulty, type, or tags', icon: BookOpen, color: 'cyan' },
              { step: '02', title: 'Launch the Lab', desc: 'An isolated container spins up in seconds', icon: Monitor, color: 'purple' },
              { step: '03', title: 'Fix the Server', desc: 'Use the real terminal to diagnose and repair', icon: Terminal, color: 'green' },
              { step: '04', title: 'Validate & Score', desc: 'One-click validation, earn points, see the solution', icon: CheckCircle2, color: 'amber' },
            ].map(({ step, title, desc, icon: Icon, color }, idx) => (
              <div key={step} className="text-center relative group">
                {idx < 3 && <div className="hidden md:block absolute top-10 left-[60%] w-[80%] h-px bg-gradient-to-r from-surface-600 via-accent-cyan/20 to-transparent" />}
                <div className={`w-20 h-20 rounded-2xl bg-gradient-to-br from-accent-${color}/20 to-accent-${color}/5 border border-surface-700/50 flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform duration-300`}>
                  <Icon size={30} className="text-white" />
                </div>
                <div className={`inline-block text-xs text-accent-${color} font-bold bg-accent-${color}/10 border border-accent-${color}/20 rounded-full px-3 py-1 mb-3`}>Step {step}</div>
                <h3 className="text-base font-bold text-white mb-2">{title}</h3>
                <p className="text-sm text-surface-400">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="bg-gradient-stripe" />

      {/* Learn by Doing Section */}
      <section className="relative overflow-hidden py-24">
        <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/8 via-surface-950 to-accent-purple/8" />
        <div className="glow-orb-cyan absolute left-0 top-1/2 -translate-y-1/2" />
        <div className="max-w-7xl mx-auto px-6 relative">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-amber/10 border border-accent-amber/20 text-accent-amber text-xs font-bold uppercase tracking-widest mb-5">
                <Flame size={13} /> Challenge
              </div>
              <h2 className="text-4xl lg:text-5xl font-black text-white mb-6 leading-tight">
                Learn by <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-amber to-accent-red">Doing</span>,<br />Not Watching
              </h2>
              <p className="text-surface-300 text-lg mb-8 leading-relaxed">Break real servers. Fix real problems. Build real skills. FixitLab gives you hands-on practice that no video course can match.</p>
              <div className="space-y-4">
                {[
                  { icon: Terminal, text: 'Real terminal access to live containers' },
                  { icon: Shield, text: 'Production-like isolated environments' },
                  { icon: Activity, text: 'Instant validation and scoring' },
                  { icon: GitBranch, text: 'Progressive difficulty from easy to hard' },
                ].map(({ icon: Icon, text }) => (
                  <div key={text} className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-accent-cyan/10 flex items-center justify-center shrink-0"><Icon size={16} className="text-accent-cyan" /></div>
                    <span className="text-surface-300">{text}</span>
                  </div>
                ))}
              </div>
              <div className="mt-10">
                <Link to="/register" className="btn-primary text-base px-8 py-3.5 inline-flex items-center gap-2 shadow-lg shadow-accent-cyan/25">Start Your Journey <ArrowRight size={16} /></Link>
              </div>
            </div>
            <div className="space-y-4">
              {[
                { label: 'Diagnose the Issue', time: '2 min', status: 'completed' },
                { label: 'Find Root Cause', time: '5 min', status: 'completed' },
                { label: 'Apply the Fix', time: '3 min', status: 'active' },
                { label: 'Validate Solution', time: '1 min', status: 'pending' },
              ].map(({ label, time, status }) => (
                <div key={label} className={`glass-card p-5 flex items-center gap-4 ${status === 'active' ? 'border-accent-cyan/30 glow-border' : ''}`}>
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${status === 'completed' ? 'bg-accent-green/15 text-accent-green' : status === 'active' ? 'bg-accent-cyan/15 text-accent-cyan animate-pulse' : 'bg-surface-700 text-surface-500'}`}>
                    {status === 'completed' ? <CheckCircle2 size={20} /> : status === 'active' ? <Activity size={20} /> : <Clock size={20} />}
                  </div>
                  <div className="flex-1"><p className="text-white font-medium">{label}</p><p className="text-xs text-surface-500">{time}</p></div>
                  {status === 'completed' && <span className="text-xs text-accent-green font-semibold">Done</span>}
                  {status === 'active' && <span className="text-xs text-accent-cyan font-semibold animate-pulse">In Progress</span>}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <div className="bg-gradient-stripe" />

      {/* Testimonials */}
      <section className="relative overflow-hidden py-24">
        <div className="absolute inset-0 section-dark" />
        <div className="absolute inset-0 bg-dots-pattern opacity-20" />
        <div className="glow-orb-pink absolute right-0 top-0" />
        <div className="max-w-7xl mx-auto px-6 relative">
          <div className="text-center mb-14">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-amber/10 border border-accent-amber/20 text-accent-amber text-xs font-bold uppercase tracking-widest mb-5">
              <Star size={13} /> Testimonials
            </div>
            <h2 className="text-4xl lg:text-5xl font-black text-white mb-4">Loved by <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-amber to-accent-red">Engineers</span></h2>
            <p className="text-surface-400 text-lg">Trusted by engineers, developers, and IT professionals worldwide.</p>
          </div>
          <div className="max-w-3xl mx-auto">
            <div className="glass-card p-10 relative overflow-hidden gradient-border">
              <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/5 via-transparent to-accent-purple/5" />
              <div className="relative">
                <div className="flex mb-4">{[...Array(5)].map((_, i) => <Star key={i} size={18} className="text-accent-amber fill-accent-amber" />)}</div>
                <blockquote className="text-xl text-surface-200 leading-relaxed mb-8 italic font-light">&ldquo;{testimonials[activeTestimonial].text}&rdquo;</blockquote>
                <div className="flex items-center gap-4">
                  <div className="w-14 h-14 rounded-full bg-gradient-to-br from-accent-cyan to-accent-purple flex items-center justify-center text-lg font-bold text-white shadow-lg shadow-accent-cyan/20">
                    {testimonials[activeTestimonial].name.split(' ').map(n => n[0]).join('')}
                  </div>
                  <div>
                    <p className="text-lg font-bold text-white">{testimonials[activeTestimonial].name}</p>
                    <p className="text-sm text-surface-400">{testimonials[activeTestimonial].role} &middot; {testimonials[activeTestimonial].company}</p>
                  </div>
                </div>
              </div>
            </div>
            <div className="flex justify-center gap-2 mt-6">
              {testimonials.map((_, i) => (
                <button key={i} onClick={() => setActiveTestimonial(i)} className={`w-2.5 h-2.5 rounded-full transition-all duration-300 ${i === activeTestimonial ? 'bg-accent-cyan w-8' : 'bg-surface-600 hover:bg-surface-500'}`} />
              ))}
            </div>
          </div>
        </div>
      </section>

      <div className="bg-gradient-stripe" />

      {/* CTA */}
      <section className="max-w-5xl mx-auto px-6 py-24 text-center relative">
        <div className="glow-orb-cyan absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2" />
        <div className="glow-orb-purple absolute -right-20 top-0" />
        <div className="glass-card p-14 relative overflow-hidden gradient-border">
          <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/8 via-transparent to-accent-purple/8" />
          <div className="absolute inset-0 bg-grid-pattern opacity-20" />
          <div className="relative">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-accent-cyan/10 border border-accent-cyan/20 text-accent-cyan text-xs font-bold uppercase tracking-widest mb-6">
              <Sparkles size={13} /> Get Started Today
            </div>
            <h2 className="text-4xl lg:text-5xl font-black text-white mb-6">Ready to prove your <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-cyan to-accent-purple">skills</span>?</h2>
            <p className="text-surface-400 mb-10 max-w-lg mx-auto text-lg">Free demo included. Subscribe per technology. Start troubleshooting in under 30 seconds.</p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link to="/register" className="group btn-primary text-lg px-10 py-4 inline-flex items-center gap-2 shadow-lg shadow-accent-cyan/30 hover:shadow-accent-cyan/50">Create Free Account <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" /></Link>
              <Link to="/about" className="btn-secondary text-lg px-10 py-4 inline-flex items-center gap-2">Learn More</Link>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-surface-700/30 relative overflow-hidden">
        <div className="absolute inset-0 section-dark" />
        <div className="max-w-7xl mx-auto px-6 py-16 relative">
          <div className="grid md:grid-cols-5 gap-8">
            <div className="md:col-span-2">
              <div className="flex items-center gap-2.5 mb-5">
                <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-accent-cyan to-accent-blue flex items-center justify-center shadow-lg shadow-accent-cyan/20"><Terminal size={18} className="text-white" /></div>
                <span className="text-xl font-bold text-white">FixitLab</span>
              </div>
              <p className="text-sm text-surface-400 leading-relaxed max-w-xs mb-6">Hands-on labs for Linux, Docker, databases, cloud, networking, security, and more. Learn by doing, not reading.</p>
            </div>
            <div>
              <h4 className="text-sm font-bold text-white uppercase tracking-wider mb-4">Product</h4>
              <div className="space-y-3">
                {[['Scenarios', '/scenarios'], ['Pricing', '/pricing'], ['Leaderboard', '/leaderboard'], ['Technologies', '/technologies']].map(([label, to]) => (
                  <Link key={to} to={to} className="block text-sm text-surface-400 hover:text-accent-cyan transition-colors">{label}</Link>
                ))}
              </div>
            </div>
            <div>
              <h4 className="text-sm font-bold text-white uppercase tracking-wider mb-4">Resources</h4>
              <div className="space-y-3">
                {[['Blog', '/blog'], ['FAQ', '/faq'], ['Community', '/community'], ['Verify Certificate', '/verify-certificate']].map(([label, to]) => (
                  <Link key={to} to={to} className="block text-sm text-surface-400 hover:text-accent-cyan transition-colors">{label}</Link>
                ))}
              </div>
            </div>
            <div>
              <h4 className="text-sm font-bold text-white uppercase tracking-wider mb-4">Company</h4>
              <div className="space-y-3">
                {[['About', '/about'], ['Privacy', '/privacy'], ['Terms', '/terms'], ['Contact', '/contact']].map(([label, to]) => (
                  <Link key={to} to={to} className="block text-sm text-surface-400 hover:text-accent-cyan transition-colors">{label}</Link>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-12 pt-8 border-t border-surface-700/30 flex flex-col sm:flex-row items-center justify-between text-xs text-surface-500 gap-4">
            <span>&copy; 2026 FixitLab. All rights reserved.</span>
            <span>Built with passion for engineers and developers worldwide</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
