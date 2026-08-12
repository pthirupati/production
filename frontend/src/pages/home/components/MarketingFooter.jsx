import { Link } from 'react-router-dom'
import { Terminal } from '../../../ui/eagerIcons'
import { footerColumns } from '../data/homeContent'

export default function MarketingFooter() {
  return (
    <footer className="fx-marketing-footer">
      <div className="fx-marketing-footer-grid">
        <div>
          <Link to="/" className="flex items-center gap-[11px] no-underline mb-[18px] w-fit">
            <span className="w-9 h-9 rounded-[10px] flex items-center justify-center bg-gradient-to-br from-[var(--fx-ac)] to-[var(--fx-ac2)]">
              <Terminal size={19} className="text-white" strokeWidth={2} />
            </span>
            <span className="font-display font-extrabold text-[19px] text-white">FixitLab</span>
          </Link>
          <p className="text-sm leading-relaxed text-white/45 max-w-[280px] m-0">
            Break things. Fix them. Get hired. Hands-on labs and AI interviews for the next generation of engineers.
          </p>
        </div>

        {footerColumns.map(({ title, links }) => (
          <div key={title}>
            <p className="fx-marketing-footer-col-title">{title}</p>
            <div className="flex flex-col gap-[11px]">
              {links.map(({ label, to }) => (
                <Link key={to} to={to} className="fx-marketing-footer-link">
                  {label}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="fx-marketing-footer-bottom">
        <p className="m-0">&copy; 2026 FixitLab. All rights reserved.</p>
        <div className="flex gap-[22px]">
          <Link to="/privacy" className="fx-marketing-footer-link">Privacy</Link>
          <Link to="/terms" className="fx-marketing-footer-link">Terms</Link>
          <Link to="/refunds" className="fx-marketing-footer-link">Refunds</Link>
          <Link to="/acceptable-use" className="fx-marketing-footer-link">Acceptable use</Link>
          <Link to="/contact" className="fx-marketing-footer-link">Contact</Link>
        </div>
      </div>
    </footer>
  )
}
