import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { GraduationCap, ChevronDown, ArrowRight, ExternalLink, Search } from 'lucide-react'
import { scenarioApi } from '../../../api/scenarios'
import { scenarioTagHaystack } from '../../../utils/scenarioTags'

// AWS Labs launcher for the console TopNav.
//
// Real learners open the AWS console to *practice* — so the console must expose
// the AWS hands-on scenarios directly. This dropdown lists AWS scenarios grouped
// by service/category, lets the user jump straight into a guided lab
// (/scenarios/:slug), and links to the full AWS catalog (/technologies/aws).
export default function AwsLabsMenu() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [scenarios, setScenarios] = useState([])
  const [loading, setLoading] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [q, setQ] = useState('')
  const ref = useRef(null)

  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  useEffect(() => {
    if (!open || loaded) return
    setLoading(true)
    scenarioApi
      .getScenarios({ technology_slug: 'aws', page: 1 })
      .then((data) => {
        const list = Array.isArray(data) ? data : data?.results || []
        setScenarios(list)
        setLoaded(true)
      })
      .catch(() => setScenarios([]))
      .finally(() => setLoading(false))
  }, [open, loaded])

  const filtered = q
    ? scenarios.filter((s) => scenarioTagHaystack(s).includes(q.toLowerCase()))
    : scenarios

  return (
    <div style={{ position: 'relative' }} ref={ref}>
      <button className="aws-topnav-btn" onClick={() => setOpen((o) => !o)} title="AWS hands-on labs">
        <GraduationCap size={15} /> Labs <ChevronDown size={13} />
      </button>
      {open && (
        <div
          style={{
            position: 'absolute', top: 38, left: 0, width: 420, maxHeight: 480, overflowY: 'auto',
            background: '#fff', borderRadius: 6, boxShadow: 'var(--aws-shadow-lg)', color: 'var(--aws-text-primary)', zIndex: 300,
          }}
        >
          <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--aws-border-light)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <strong style={{ fontSize: 13 }}>AWS hands-on labs</strong>
              <button
                onClick={() => { setOpen(false); navigate('/technologies/aws') }}
                style={{ fontSize: 12, color: 'var(--aws-text-link)', background: 'none', border: 'none', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4 }}
              >
                All AWS labs <ArrowRight size={12} />
              </button>
            </div>
            <div style={{ position: 'relative' }}>
              <Search size={13} style={{ position: 'absolute', left: 8, top: 8, color: '#8b96a5' }} />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search AWS labs (EC2, S3, IAM, VPC, EKS…)"
                style={{ width: '100%', height: 30, border: '1px solid var(--aws-border)', borderRadius: 4, padding: '0 8px 0 26px', fontSize: 12.5 }}
              />
            </div>
          </div>
          {loading && <div style={{ padding: 16, fontSize: 12.5, color: 'var(--aws-text-secondary)' }}>Loading AWS labs…</div>}
          {!loading && filtered.length === 0 && (
            <div style={{ padding: 16, fontSize: 12.5, color: 'var(--aws-text-secondary)' }}>No AWS labs matched.</div>
          )}
          {!loading && filtered.slice(0, 60).map((s) => (
            <div
              key={s.slug}
              onClick={() => { setOpen(false); navigate(`/scenarios/${s.slug}`) }}
              style={{ padding: '9px 14px', cursor: 'pointer', borderBottom: '1px solid var(--aws-border-light)' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--aws-sidebar-active-bg)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <div style={{ fontWeight: 600, color: 'var(--aws-text-link)', fontSize: 12.5 }}>{s.title}</div>
              <div style={{ fontSize: 11.5, color: 'var(--aws-text-secondary)', display: 'flex', gap: 8, marginTop: 2 }}>
                <span style={{ textTransform: 'capitalize' }}>{s.difficulty || 'lab'}</span>
                {s.category && <span>· {s.category}</span>}
                {s.is_free && <span style={{ color: 'var(--aws-success, #1a7f37)' }}>· Free</span>}
              </div>
            </div>
          ))}
          <div
            onClick={() => { setOpen(false); navigate('/technologies/aws') }}
            style={{ padding: '10px 14px', cursor: 'pointer', color: 'var(--aws-text-link)', fontSize: 12.5, display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            <ExternalLink size={13} /> Open the full AWS lab catalog
          </div>
        </div>
      )}
    </div>
  )
}
