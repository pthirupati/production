import { motion } from 'framer-motion'
import { scaleIn, viewportOnce } from './motion'

export default function FxStatCard({ value, label, color = '#fff', icon, delay = 0 }) {
  return (
    <motion.div
      variants={scaleIn}
      initial="hidden"
      whileInView="visible"
      viewport={viewportOnce}
      transition={{ delay }}
      whileHover={{ y: -5, borderColor: 'rgba(255,255,255,0.18)' }}
      className="rounded-2xl p-[22px] bg-white/[0.025] border border-white/[0.08] transition-colors"
    >
      {icon && (
        <div className="w-[46px] h-[46px] rounded-[13px] flex items-center justify-center mb-3.5">
          {icon}
        </div>
      )}
      <p className="font-display font-extrabold text-[30px] m-0 leading-none" style={{ color }}>
        {value}
      </p>
      <p className="text-[13px] text-white/50 mt-1 font-medium">{label}</p>
    </motion.div>
  )
}
