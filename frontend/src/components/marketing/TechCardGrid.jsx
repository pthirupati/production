import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import TechIcon from './TechIcon'
import { sortTechnologies } from '../../constants/techCatalog'

function TechCard({ tech, index, linkTo }) {
  const color = tech.color || '#6d78ff'
  const href = linkTo(tech)
  const soon = Boolean(tech.coming_soon)
  const delay = Math.min(index * 0.06, 0.4)

  const cardStyle = soon
    ? { opacity: 0.55, animationDelay: `${delay}s` }
    : { animationDelay: `${delay}s` }

  const inner = (
    <>
      <div
        className="fx-tech-icon"
        style={{
          background: `${color}1f`,
          borderColor: `${color}3d`,
          color,
        }}
      >
        <TechIcon slug={tech.slug} name={tech.name} />
      </div>
      <h3 className="fx-tech-name" style={{ color: soon ? 'rgba(255,255,255,.6)' : '#fff' }}>
        {tech.name}
      </h3>
      {soon ? (
        <span className="fx-tech-soon">
          <span className="fx-tech-soon-dot" />
          Coming soon
        </span>
      ) : (
        <>
          <p className="fx-tech-tag">
            {tech.scenario_count > 0
              ? `${tech.scenario_count} scenario${tech.scenario_count !== 1 ? 's' : ''}`
              : (tech.tag || 'Hands-on labs')}
          </p>
          <ArrowRight size={15} className="fx-tech-arrow" style={{ color }} />
        </>
      )}
    </>
  )

  const hoverHandlers = soon ? {} : {
    onMouseEnter: (e) => {
      e.currentTarget.style.borderColor = `${color}55`
      e.currentTarget.style.boxShadow = `0 26px 50px -28px ${color}66`
      e.currentTarget.style.background = `linear-gradient(165deg, ${color}14, rgba(255,255,255,.02))`
    },
    onMouseLeave: (e) => {
      e.currentTarget.style.borderColor = 'rgba(255,255,255,.08)'
      e.currentTarget.style.boxShadow = 'none'
      e.currentTarget.style.background = 'rgba(255,255,255,.025)'
    },
  }

  const className = `fx-tech-card ${soon ? 'fx-tech-card-soon' : ''}`

  if (soon) {
    return (
      <div className={className} style={cardStyle}>
        {inner}
      </div>
    )
  }

  if (href.startsWith('http')) {
    return (
      <a href={href} className={className} style={cardStyle} {...hoverHandlers}>
        {inner}
      </a>
    )
  }

  return (
    <Link to={href} className={className} style={cardStyle} data-magnetic {...hoverHandlers}>
      {inner}
    </Link>
  )
}

export default function TechCardGrid({
  technologies,
  linkTo = (t) => `/technologies/${t.slug}`,
  className = '',
}) {
  const sorted = sortTechnologies(technologies)

  return (
    <div className={`fx-tech-grid ${className}`}>
      {sorted.map((tech, i) => (
        <TechCard key={tech.id || tech.slug} tech={tech} index={i} linkTo={linkTo} />
      ))}
    </div>
  )
}
