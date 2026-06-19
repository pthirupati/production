import { Link } from 'react-router-dom'
import TechIcon from '../../../components/marketing/TechIcon'
import { sortTechnologies } from '../../../constants/techCatalog'

function formatCount(tech) {
  if (tech.coming_soon) return 'Coming soon'
  if (tech.scenario_count > 0) {
    return `${tech.scenario_count} scenario${tech.scenario_count !== 1 ? 's' : ''}`
  }
  return tech.tag || 'Hands-on labs'
}

function MarqueePill({ tech }) {
  const href = tech.coming_soon ? '/technologies' : `/scenarios?technology=${tech.slug}`
  return (
    <Link to={href} className="fx-marquee-pill">
      <span className="fx-marquee-pill-icon">
        <TechIcon slug={tech.slug} name={tech.name} size={19} />
      </span>
      <span className="fx-marquee-pill-name">{tech.name}</span>
      <span className="fx-marquee-pill-count">{formatCount(tech)}</span>
    </Link>
  )
}

export default function TechMarqueeSection({ technologies }) {
  const techs = sortTechnologies(technologies).filter(t => !t.coming_soon)
  const pills = techs.length ? techs : technologies

  return (
    <section className="fx-marquee-section">
      <p className="fx-marquee-label">
        Train on real environments across every technology
      </p>
      <div className="fx-marquee-track-wrap">
        <div className="fx-marquee-track">
          {pills.map(tech => (
            <MarqueePill key={tech.id || tech.slug} tech={tech} />
          ))}
        </div>
        <div className="fx-marquee-track" aria-hidden="true">
          {pills.map(tech => (
            <MarqueePill key={`dup-${tech.id || tech.slug}`} tech={tech} />
          ))}
        </div>
      </div>
    </section>
  )
}
