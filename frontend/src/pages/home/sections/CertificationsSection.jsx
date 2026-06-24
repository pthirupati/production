import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Award, ArrowRight, ShieldCheck } from 'lucide-react'
import { certApi } from '../../../api/certifications'
import { blurIn, scaleIn, staggerContainer, viewportOnce } from '../../../ui/motion'

export default function CertificationsSection({ isAuthenticated }) {
  const [tracks, setTracks] = useState([])

  useEffect(() => {
    certApi.list()
      .then((data) => setTracks((data?.tracks || []).filter((t) => t.is_active !== false).slice(0, 8)))
      .catch(() => setTracks([]))
  }, [])

  if (!tracks.length) return null

  return (
    <section id="certifications" className="fx-home-section">
      <div className="fx-home-section-inner">
        <motion.div
          className="text-center max-w-[640px] mx-auto mb-14"
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={blurIn}
        >
          <div
            className="fx-home-eyebrow mx-auto"
            style={{ background: 'rgba(245,166,35,.1)', border: '1px solid rgba(245,166,35,.25)', color: '#f5a623' }}
          >
            Certification prep
          </div>
          <h2 className="fx-home-title">Vendor-aligned certification labs</h2>
          <p className="fx-home-sub mx-auto">
            RHCSA, CKA, and more — certification scenarios are separate from regular technology labs.
            Your technology subscription includes matching cert labs as an add-on.
          </p>
        </motion.div>

        <motion.div
          className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4"
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={staggerContainer}
        >
          {tracks.map((track) => (
            <motion.div key={track.slug} variants={scaleIn}>
              <Link
                to={isAuthenticated ? `/certifications/${track.slug}` : '/register'}
                className="block h-full p-5 rounded-2xl border border-surface-800 bg-surface-900/40 hover:border-amber-500/40 hover:bg-surface-900/70 transition-all group"
              >
                <div className="flex items-center gap-2 mb-2">
                  <Award size={18} className="text-amber-400" />
                  <span className="text-xs font-mono text-surface-500 uppercase">{track.vendor || 'Cert'}</span>
                </div>
                <h3 className="font-semibold text-white group-hover:text-amber-200 transition-colors">{track.name}</h3>
                <p className="text-xs text-surface-500 mt-2 line-clamp-2">{track.description || track.code}</p>
                <div className="flex items-center gap-3 mt-4 text-[11px] text-surface-400">
                  <span>{track.scenario_count || 0} cert labs</span>
                  {track.is_free && (
                    <span className="text-emerald-400 flex items-center gap-1"><ShieldCheck size={12} /> Free</span>
                  )}
                </div>
              </Link>
            </motion.div>
          ))}
        </motion.div>

        <motion.div className="text-center mt-10" initial="hidden" whileInView="visible" viewport={viewportOnce} variants={scaleIn}>
          <Link to="/certifications" data-magnetic className="fx-btn-secondary inline-flex items-center gap-2">
            View all certifications <ArrowRight size={15} />
          </Link>
        </motion.div>
      </div>
    </section>
  )
}
