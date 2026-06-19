import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Layers, ArrowRight } from 'lucide-react'
import toast from 'react-hot-toast'
import { useDataStore } from '../store/dataStore'
import { mergeTechnologies } from '../constants/techCatalog'
import { TechCardGrid } from '../components/marketing'
import { PageHeader } from '../components/design'
import ScrollReveal from '../ui/ScrollReveal'
import { fadeUp, staggerContainer } from '../ui/motion'

export default function Technologies() {
  const getTechnologies = useDataStore(s => s.getTechnologies)
  const [technologies, setTechnologies] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getTechnologies()
      .then(data => setTechnologies(mergeTechnologies(data)))
      .catch(() => {
        setTechnologies(mergeTechnologies([]))
        toast.error('Could not load technologies — showing catalog')
      })
      .finally(() => setLoading(false))
  }, [getTechnologies])

  const linkTo = (tech) => {
    if (tech.coming_soon) return '#'
    return `/technologies/${tech.slug}`
  }

  return (
    <motion.div
      className="flex flex-col gap-6 pb-8"
      initial="hidden"
      animate="visible"
      variants={staggerContainer}
    >
      <PageHeader
        eyebrow="Learning paths"
        title="Technologies"
        subtitle="Choose a technology to explore scenarios, track progress, and earn certificates."
        actions={(
          <Link
            to="/scenarios"
            className="inline-flex items-center gap-1.5 text-sm font-semibold text-white/60 hover:text-accent-cyan transition-colors shrink-0"
          >
            View all scenarios <ArrowRight size={14} />
          </Link>
        )}
      />

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <div key={i} className="h-44 rounded-2xl bg-white/[0.04] animate-pulse" />
          ))}
        </div>
      ) : (
        <ScrollReveal variants={fadeUp}>
          <TechCardGrid technologies={technologies} linkTo={linkTo} className="!grid-cols-1 sm:!grid-cols-2 xl:!grid-cols-3" />
        </ScrollReveal>
      )}

      <ScrollReveal>
        <div className="relative overflow-hidden rounded-[18px] p-6 sm:p-8 border border-white/[0.08] bg-gradient-to-br from-accent-cyan/[0.06] via-transparent to-accent-purple/[0.05]">
          <div className="relative flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="font-display font-bold text-lg text-white m-0">Not sure where to start?</h2>
              <p className="text-sm text-white/50 mt-1 mb-0">Browse the full challenge library and filter by technology, difficulty, and type.</p>
            </div>
            <Link
              to="/scenarios"
              className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-[11px] text-sm font-semibold text-white bg-gradient-to-br from-accent-cyan to-accent-purple shrink-0 hover:opacity-95 transition-opacity"
            >
              Browse scenarios <ArrowRight size={15} />
            </Link>
          </div>
        </div>
      </ScrollReveal>
    </motion.div>
  )
}
