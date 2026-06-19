export default function StatusIcon({ status, size = 10 }) {
  const cls = status === 'connected' || status === 'poweredOn' ? 'bg-[#5DB85D]'
    : status === 'disconnected' || status === 'poweredOff' ? 'bg-[#D9534F]'
    : status === 'suspended' ? 'bg-[#F5A623]'
    : status === 'notResponding' ? 'bg-[#D9534F]'
    : 'bg-[#F5A623]'
  return (
    <span className="inline-flex items-center justify-center rounded-full shrink-0" style={{ width: size, height: size }}>
      <span className={`rounded-full ${cls}`} style={{ width: size - 2, height: size - 2 }} />
    </span>
  )
}
