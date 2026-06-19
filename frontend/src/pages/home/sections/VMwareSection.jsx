import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, Server, Layers, Zap, Wrench, LineChart } from 'lucide-react'
import VMwareShowcase from '../components/VMwareShowcase'
import { fadeLeft, fadeRight, viewportOnce } from '../../../ui/motion'

const bulletIcons = [Layers, Zap, Wrench, LineChart]

export default function VMwareSection({ isAuthenticated }) {
  return (
    <section id="vmware" className="fx-home-section overflow-hidden" style={{ paddingTop: 0 }}>
      <div
        className="absolute right-[-120px] top-[8%] w-[460px] h-[460px] rounded-full pointer-events-none"
        aria-hidden="true"
        style={{ background: 'radial-gradient(circle, #5b9bd5 0%, transparent 65%)', opacity: 0.16, filter: 'blur(34px)', animation: 'fxFloat 17s ease-in-out infinite' }}
      />

      <div className="fx-home-section-inner grid lg:grid-cols-[1.05fr_0.95fr] gap-[60px] items-center relative">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={fadeLeft}
        >
          <VMwareShowcase />
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={viewportOnce}
          variants={fadeRight}
        >
          <div
            className="fx-home-eyebrow"
            style={{ background: 'rgba(91,155,213,.14)', border: '1px solid rgba(91,155,213,.3)', color: '#7cc0f0' }}
          >
            <Server size={13} className="inline mr-1" /> VMware vCenter AI Lab
          </div>
          <h2 className="fx-home-title">Master VMware vSphere in a live AI lab</h2>
          <p className="fx-home-sub mb-[34px]">
            Practice real vCenter and ESXi operations in a fully-featured, AI-powered environment — no expensive lab hardware. Fix HA failures, run vMotion migrations, resolve datastore alerts and more.
          </p>

          <div className="flex flex-col gap-4 mb-9">
            {[
              'Full vCenter UI — hosts, VMs, storage & networking',
              'Live vMotion, HA, DRS, snapshots & maintenance mode',
              'Realistic faults: disconnected hosts, full datastores',
              'Real-time performance charts & recent-tasks panel',
            ].map((text, i) => {
              const Icon = bulletIcons[i]
              return (
                <div key={text} className="flex items-center gap-[13px]">
                  <span
                    className="w-[34px] h-[34px] rounded-[9px] shrink-0 flex items-center justify-center"
                    style={{ background: 'rgba(91,155,213,.12)', border: '1px solid rgba(91,155,213,.25)', color: '#7cc0f0' }}
                  >
                    <Icon size={16} strokeWidth={1.8} />
                  </span>
                  <span className="text-[15px] text-white/78">{text}</span>
                </div>
              )
            })}
          </div>

          <Link
            to={isAuthenticated ? '/scenarios?technology=vmware' : '/register'}
            data-magnetic
            className="fx-btn-primary inline-flex"
            style={{ background: 'linear-gradient(135deg, #2a6ab5, #5b9bd5)', boxShadow: '0 10px 34px rgba(91,155,213,.4)' }}
          >
            Try VMware scenarios <ArrowRight size={16} />
          </Link>
        </motion.div>
      </div>
    </section>
  )
}
