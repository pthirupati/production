import { Link } from 'react-router-dom'
import { Shield, Cpu, Zap } from 'lucide-react'
import FixitLogo from './FixitLogo'

function DefaultIllustration() {
  return (
    <div className="relative w-full h-full flex items-center justify-center overflow-hidden">
      <div
        className="absolute inset-0 opacity-[0.06]"
        style={{
          backgroundImage: 'linear-gradient(rgb(var(--a-blue)) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--a-blue)) 1px, transparent 1px)',
          backgroundSize: '42px 42px',
          maskImage: 'radial-gradient(120% 90% at 50% 40%, #000 30%, transparent 78%)',
        }}
      />
      <div className="absolute top-[18%] left-[24%] w-[280px] h-[280px] rounded-full bg-accent-blue/15 blur-[40px] animate-[fxFloat_13s_ease-in-out_infinite]" />
      <div className="absolute bottom-[24%] right-[22%] w-[240px] h-[240px] rounded-full bg-accent-purple/15 blur-[40px] animate-[fxFloatX_16s_ease-in-out_infinite]" />

      <div className="relative z-10 w-[300px]">
        <div className="rounded-[20px] p-[18px] bg-[rgba(12,16,32,.7)] border border-white/10 shadow-[0_40px_90px_-30px_rgba(0,0,0,.7)]">
          {[0, 1, 2, 3, 4].map(i => (
            <div key={i} className="flex items-center gap-2 px-3.5 py-3 mb-2.5 last:mb-0 rounded-[11px] bg-white/[0.03] border border-white/[0.07]">
              <span
                className={`w-2 h-2 rounded-full shrink-0 ${i < 3 ? 'bg-accent-green' : i === 3 ? 'bg-accent-amber' : 'bg-accent-red'}`}
                style={{ boxShadow: `0 0 8px currentColor`, animation: `fxLed ${1.5 + i * 0.3}s ease-in-out infinite` }}
              />
              <div className="flex gap-1 flex-1">
                {[0, 1, 2, 3, 4, 5].map(j => (
                  <span key={j} className="flex-1 h-[22px] rounded-[3px] bg-white/[0.06] border border-white/[0.05]" />
                ))}
              </div>
              <span className="w-[5px] h-[5px] rounded-full bg-accent-blue animate-[fxLed_0.8s_ease-in-out_infinite]" />
            </div>
          ))}
        </div>

        <div className="absolute -top-4 -right-[26px] flex items-center gap-1.5 px-3 py-2 rounded-[11px] bg-[rgba(16,20,38,.92)] border border-accent-green/35 text-xs font-semibold text-accent-green shadow-lg animate-[fxBob_3s_ease-in-out_infinite]">
          <Shield size={13} /> Secure
        </div>
        <div className="absolute top-[42%] -left-10 flex items-center gap-1.5 px-3 py-2 rounded-[11px] bg-[rgba(16,20,38,.92)] border border-accent-blue/35 text-xs font-semibold text-accent-blue shadow-lg animate-[fxBob_4s_ease-in-out_.8s_infinite]">
          <Cpu size={13} /> 99.9% Uptime
        </div>
        <div className="absolute bottom-[14%] -right-[30px] flex items-center gap-1.5 px-3 py-2 rounded-[11px] bg-[rgba(16,20,38,.92)] border border-accent-amber/35 text-xs font-semibold text-accent-amber shadow-lg animate-[fxBob_3.4s_ease-in-out_.4s_infinite]">
          <Zap size={13} /> Live Labs
        </div>
      </div>

      <div className="absolute bottom-9 left-9 right-9 z-[3] rounded-[14px] p-4 bg-[rgba(10,12,24,.9)] border border-white/8 backdrop-blur-sm">
        <div className="flex items-center gap-1.5 mb-2.5">
          <span className="w-[9px] h-[9px] rounded-full bg-[#ec6a5e]" />
          <span className="w-[9px] h-[9px] rounded-full bg-[#f4bf4f]" />
          <span className="w-[9px] h-[9px] rounded-full bg-[#61c554]" />
          <span className="ml-2 font-mono text-[11px] text-white/35">terminal</span>
        </div>
        <div className="font-mono text-[12.5px] leading-relaxed">
          <p className="m-0"><span className="text-accent-green">$</span> <span className="text-white/75">ssh lab@fixitlab.in</span></p>
          <p className="m-0 text-white/45">Connected to scenario: <span className="text-accent-blue">broken-nginx</span></p>
          <p className="m-0"><span className="text-accent-green">root@lab</span><span className="text-white/40">:</span><span className="text-accent-blue">~</span># <span className="inline-block w-2 h-3.5 bg-accent-green align-[-2px] animate-[fxBlink_1s_step-end_infinite]" /></p>
        </div>
      </div>
    </div>
  )
}

/** Auth layout — Claude FixitLab Auth.dc.html split panel. */
export default function AuthShell({
  title,
  subtitle,
  children,
  footer,
  illustration,
  compact = false,
  trustBadges,
}) {
  if (compact) {
    return (
      <div className="min-h-screen bg-surface-950 flex items-center justify-center px-4 py-8 relative overflow-hidden">
        <div className="fixed inset-0 pointer-events-none">
          <div className="absolute inset-0 hero-grid opacity-40" />
          <div className="glow-orb-cyan absolute top-1/4 left-1/4" />
          <div className="glow-orb-purple absolute bottom-1/4 right-1/4" />
        </div>
        <div className="w-full max-w-md relative animate-fx-rise">
          <div className="text-center mb-8">
            <FixitLogo size="lg" className="inline-flex mb-6" />
            {title && <h1 className="text-2xl font-display font-extrabold text-white mb-2">{title}</h1>}
            {subtitle && <p className="text-surface-400">{subtitle}</p>}
          </div>
          <div className="fx-panel p-8">{children}</div>
          {footer}
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-surface-950 flex">
      <div className="hidden lg:flex lg:w-[52%] xl:w-[55%] relative overflow-hidden bg-gradient-to-br from-[#11193c] via-[#0a0a1a] to-[#0c1430] items-center justify-center">
        <FixitLogo className="absolute top-7 left-8 z-[5]" size="lg" />
        {illustration || <DefaultIllustration />}
      </div>

      <div className="flex-1 flex items-center justify-center px-6 py-8 relative overflow-y-auto">
        <div className="lg:hidden fixed inset-0 pointer-events-none">
          <div className="absolute inset-0 hero-grid" />
          <div className="glow-orb-cyan absolute top-1/4 left-1/4" />
          <div className="glow-orb-purple absolute bottom-1/4 right-1/4" />
        </div>

        <div className="w-full max-w-lg relative animate-fx-rise">
          <div className="text-center mb-8 lg:mb-10">
            <FixitLogo size="lg" className="lg:hidden inline-flex mb-6" />
            {title && <h1 className="text-3xl font-display font-extrabold text-white mb-2">{title}</h1>}
            {subtitle && <p className="text-surface-400">{subtitle}</p>}
          </div>
          <div className="fx-panel p-8">{children}</div>
          {footer}
          {trustBadges}
        </div>
      </div>
    </div>
  )
}
