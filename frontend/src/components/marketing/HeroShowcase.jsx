import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, Clock, Mic2 } from 'lucide-react'

const PANELS = [
  { id: 0, badge: 'Linux lab · live', badgeColor: '#56e0b0', borderColor: 'rgba(86,224,176,.35)' },
  { id: 1, badge: 'AI Interview · live', badgeColor: '#d6a8ee', borderColor: 'rgba(178,102,224,.35)' },
  { id: 2, badge: 'VMware · vSphere', badgeColor: '#7cc0f0', borderColor: 'rgba(124,192,240,.35)' },
]

export default function HeroShowcase() {
  const [panel, setPanel] = useState(0)
  const termRef = useRef(null)

  useEffect(() => {
    const t = setInterval(() => setPanel(p => (p + 1) % PANELS.length), 5200)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    const el = termRef.current
    if (!el) return undefined
    const onMove = (e) => {
      const r = el.getBoundingClientRect()
      const x = (e.clientX - r.left) / r.width - 0.5
      const y = (e.clientY - r.top) / r.height - 0.5
      el.style.transform = `perspective(900px) rotateY(${x * 6}deg) rotateX(${-y * 5}deg)`
    }
    const onLeave = () => { el.style.transform = 'none' }
    el.addEventListener('mousemove', onMove)
    el.addEventListener('mouseleave', onLeave)
    return () => {
      el.removeEventListener('mousemove', onMove)
      el.removeEventListener('mouseleave', onLeave)
    }
  }, [])

  const meta = PANELS[panel]

  return (
    <div className="fx-hero-showcase-wrap animate-fx-rise">
      <div className="fx-hero-showcase-glow" aria-hidden="true" />
      <div ref={termRef} className="fx-hero-showcase">
        <div
          className="fx-hero-badge fx-hero-badge-left"
          style={{ borderColor: meta.borderColor, color: meta.badgeColor }}
        >
          <span className="fx-pulse-dot" style={{ background: 'currentColor' }} />
          {meta.badge}
        </div>
        <div className="fx-hero-badge fx-hero-badge-right">
          <Clock size={12} /> 12:34
        </div>

        <div className="fx-hero-panel-stack">
          {/* Terminal */}
          <div className={`fx-hero-panel ${panel === 0 ? 'fx-hero-panel-active' : ''}`}>
            <div className="fx-term-chrome">
              <span className="fx-dot fx-dot-red" />
              <span className="fx-dot fx-dot-yellow" />
              <span className="fx-dot fx-dot-green" />
              <span className="fx-term-title">root@fixitlab: ~/broken-nginx</span>
            </div>
            <div className="fx-term-body">
              <p><span className="fx-term-prompt">root@lab</span><span className="fx-term-dim">:</span><span className="fx-term-path">~</span># systemctl status nginx</p>
              <p className="fx-term-err">● nginx.service — failed (Result: exit-code)</p>
              <p><span className="fx-term-prompt">root@lab</span><span className="fx-term-dim">:</span><span className="fx-term-path">~</span># nginx -t</p>
              <p className="fx-term-err">nginx: [emerg] unknown directive &quot;listn&quot;</p>
              <p><span className="fx-term-prompt">root@lab</span><span className="fx-term-dim">:</span><span className="fx-term-path">~</span># <span className="fx-term-cmd">sed -i &apos;s/listn/listen/&apos; /etc/nginx/sites-available/default</span></p>
              <p><span className="fx-term-prompt">root@lab</span><span className="fx-term-dim">:</span><span className="fx-term-path">~</span># systemctl restart nginx</p>
              <p className="fx-term-ok">● nginx.service — active (running)</p>
              <p className="fx-term-success">
                <CheckCircle2 size={16} /> Challenge solved · Score 185/200
                <span className="fx-term-cursor" />
              </p>
            </div>
          </div>

          {/* AI Interview */}
          <div className={`fx-hero-panel fx-hero-panel-overlay ${panel === 1 ? 'fx-hero-panel-active' : ''}`}>
            <div className="fx-term-chrome">
              <div className="fx-rec-label"><span className="fx-rec-dot" /> REC · AI Interview</div>
              <span className="fx-interview-type">System Design</span>
            </div>
            <div className="fx-interview-stage">
              <div className="fx-interview-avatar">
                <Mic2 size={32} strokeWidth={1.6} />
              </div>
              <div className="fx-wave-bars" aria-hidden="true">
                {[0, 0.08, 0.16, 0.24, 0.04, 0.12, 0.2].map((d, i) => (
                  <span key={i} style={{ animationDelay: `${d}s` }} />
                ))}
              </div>
            </div>
            <div className="fx-interview-copy">
              <div className="fx-interview-label">AI INTERVIEWER</div>
              <p>&quot;How would you design a rate limiter for 1M requests/sec across a distributed fleet?&quot;</p>
            </div>
          </div>

          {/* VMware */}
          <div className={`fx-hero-panel fx-hero-panel-overlay ${panel === 2 ? 'fx-hero-panel-active' : ''}`}>
            <div className="fx-term-chrome">
              <span className="fx-term-title">vSphere Client · web-prod-01</span>
            </div>
            <div className="fx-vmware-stage">
              <div className="fx-vmware-vm">
                <div className="fx-vmware-screen" />
                <span>web-prod-01</span>
              </div>
              <div className="fx-vmware-progress">
                <div className="fx-vmware-bar" />
              </div>
              <p className="fx-vmware-hint">Guest OS hung — reboot required after customer approval</p>
            </div>
          </div>
        </div>

        <div className="fx-hero-dots">
          {PANELS.map(p => (
            <button
              key={p.id}
              type="button"
              aria-label={`Show panel ${p.id + 1}`}
              className={`fx-hero-dot ${panel === p.id ? 'fx-hero-dot-active' : ''}`}
              onClick={() => setPanel(p.id)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
