import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, Cpu, Boxes, Thermometer, Cable, Gauge } from 'lucide-react'
import DatacenterWalkAnimation from '../components/DatacenterWalkAnimation'
import { fadeLeft, fadeRight, viewportOnce } from '../../../ui/motion'

const bulletIcons = [Boxes, Thermometer, Cable, Gauge]

const BULLETS = [
  'Walk the hall in first person — WASD, mouse-look, badge-in at the mantrap',
  'Chase real facility physics: CRAC failure, hot aisles, PDU load, breaker trips',
  'Swap failed sleds, reseat cables, trace ToR-to-spine links by hand',
  'GPU fleet ops: XID faults, ECC row-remap, NVLink degradation, MIG, DCGM',
]

/**
 * Home-page showcase for the 3D datacenter walk + the AI-infrastructure/GPU
 * track. Mirrors VMwareSection's layout but flips the column order so the copy
 * leads on the left and the animated hall sits on the right.
 */
export default function DatacenterGpuSection({ isAuthenticated }) {
  return (
    <section id="datacenter" className="fx-home-section overflow-hidden">
      <div
        className="absolute left-[-140px] top-[12%] w-[480px] h-[480px] rounded-full pointer-events-none"
        aria-hidden="true"
        style={{
          background: 'radial-gradient(circle, #76b900 0%, transparent 65%)',
          opacity: 0.14,
          filter: 'blur(36px)',
          animation: 'fxFloatX 19s ease-in-out infinite',
        }}
      />

      <div className="fx-home-section-inner grid lg:grid-cols-[0.95fr_1.05fr] gap-[60px] items-center relative">
        <motion.div initial="hidden" whileInView="visible" viewport={viewportOnce} variants={fadeLeft}>
          <div
            className="fx-home-eyebrow"
            style={{
              background: 'rgba(118,185,0,.14)',
              border: '1px solid rgba(118,185,0,.32)',
              color: '#9ae600',
            }}
          >
            <Cpu size={13} className="inline mr-1" /> 3D Datacenter &amp; GPU / AI Infrastructure
          </div>
          <h2 className="fx-home-title">Walk a real datacenter. Run a real GPU fleet.</h2>
          <p className="fx-home-sub mb-[34px]">
            Most platforms stop at a terminal. Here you put on a badge and walk the floor in 3D — open
            racks, pull a dead PSU, reseat a fibre run, and watch the thermal envelope react. Then take
            the same fleet up the stack: NVIDIA driver and XID diagnostics, DCGM health, MIG
            partitioning, LLM serving and MLOps.
          </p>

          <div className="flex flex-col gap-4 mb-9">
            {BULLETS.map((text, i) => {
              const Icon = bulletIcons[i]
              return (
                <div key={text} className="flex items-center gap-[13px]">
                  <span
                    className="w-[34px] h-[34px] rounded-[9px] shrink-0 flex items-center justify-center"
                    style={{
                      background: 'rgba(118,185,0,.12)',
                      border: '1px solid rgba(118,185,0,.26)',
                      color: '#9ae600',
                    }}
                  >
                    <Icon size={16} strokeWidth={1.8} />
                  </span>
                  <span className="fx-home-bullet-text">{text}</span>
                </div>
              )
            })}
          </div>

          <div className="flex flex-wrap gap-3">
            <Link
              to={isAuthenticated ? '/technologies/datacenter' : '/register'}
              data-magnetic
              className="fx-btn-primary"
            >
              Enter the 3D hall <ArrowRight size={17} />
            </Link>
            <Link to={isAuthenticated ? '/technologies/gpu' : '/register'} className="fx-btn-secondary">
              <Cpu size={16} /> Explore GPU labs
            </Link>
          </div>
        </motion.div>

        <motion.div initial="hidden" whileInView="visible" viewport={viewportOnce} variants={fadeRight}>
          <DatacenterWalkAnimation demoHref={isAuthenticated ? '/technologies/datacenter' : '/register'} />
        </motion.div>
      </div>
    </section>
  )
}
