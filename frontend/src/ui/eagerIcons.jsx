/** Tiny SVG icon set for the eager entry graph.
 * Do NOT import lucide-react from modules reachable from main.jsx —
 * that pulls the whole `icons` manual chunk (~155kB gzip) onto first paint.
 * Paths copied from lucide-react v0.577.0 (ISC).
 * Regenerate: node frontend/scripts/gen-eager-icons.mjs
 */
import { forwardRef } from 'react'

function createIcon(name, children) {
  const Icon = forwardRef(function Icon(
    { size = 24, color = 'currentColor', strokeWidth = 2, className, ...props },
    ref,
  ) {
    return (
      <svg
        ref={ref}
        xmlns="http://www.w3.org/2000/svg"
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
        aria-hidden={props['aria-hidden'] ?? true}
        {...props}
      >
        {children}
      </svg>
    )
  })
  Icon.displayName = name
  return Icon
}

export const Activity = createIcon('Activity', (
  <>
    <path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2" key="169zse" />
  </>
))

export const AlertCircle = createIcon('AlertCircle', (
  <>
    <circle cx="12" cy="12" r="10" key="1mglay" />
    <line x1="12" x2="12" y1="8" y2="12" key="1pkeuh" />
    <line x1="12" x2="12.01" y1="16" y2="16" key="4dfq90" />
  </>
))

export const AlertTriangle = createIcon('AlertTriangle', (
  <>
    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" key="wmoenq" />
    <path d="M12 9v4" key="juzpu7" />
    <path d="M12 17h.01" key="p32p05" />
  </>
))

export const ArrowLeft = createIcon('ArrowLeft', (
  <>
    <path d="m12 19-7-7 7-7" key="1l729n" />
    <path d="M19 12H5" key="x3x0zl" />
  </>
))

export const ArrowRight = createIcon('ArrowRight', (
  <>
    <path d="M5 12h14" key="1ays0h" />
    <path d="m12 5 7 7-7 7" key="xquz4c" />
  </>
))

export const ArrowUp = createIcon('ArrowUp', (
  <>
    <path d="m5 12 7-7 7 7" key="hav0vg" />
    <path d="M12 19V5" key="x0mq9r" />
  </>
))

export const Award = createIcon('Award', (
  <>
    <path d="m15.477 12.89 1.515 8.526a.5.5 0 0 1-.81.47l-3.58-2.687a1 1 0 0 0-1.197 0l-3.586 2.686a.5.5 0 0 1-.81-.469l1.514-8.526" key="1yiouv" />
    <circle cx="12" cy="8" r="6" key="1vp47v" />
  </>
))

export const BarChart3 = createIcon('BarChart3', (
  <>
    <path d="M3 3v16a2 2 0 0 0 2 2h16" key="c24i48" />
    <path d="M18 17V9" key="2bz60n" />
    <path d="M13 17V5" key="1frdt8" />
    <path d="M8 17v-3" key="17ska0" />
  </>
))

export const Bell = createIcon('Bell', (
  <>
    <path d="M10.268 21a2 2 0 0 0 3.464 0" key="vwvbt9" />
    <path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326" key="11g9vi" />
  </>
))

export const BookOpen = createIcon('BookOpen', (
  <>
    <path d="M12 7v14" key="1akyts" />
    <path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z" key="ruj8y" />
  </>
))

export const Bookmark = createIcon('Bookmark', (
  <>
    <path d="M17 3a2 2 0 0 1 2 2v15a1 1 0 0 1-1.496.868l-4.512-2.578a2 2 0 0 0-1.984 0l-4.512 2.578A1 1 0 0 1 5 20V5a2 2 0 0 1 2-2z" key="oz39mx" />
  </>
))

export const Bot = createIcon('Bot', (
  <>
    <path d="M12 8V4H8" key="hb8ula" />
    <rect width="16" height="12" x="4" y="8" rx="2" key="enze0r" />
    <path d="M2 14h2" key="vft8re" />
    <path d="M20 14h2" key="4cs60a" />
    <path d="M15 13v2" key="1xurst" />
    <path d="M9 13v2" key="rq6x2g" />
  </>
))

export const Boxes = createIcon('Boxes', (
  <>
    <path d="M2.97 12.92A2 2 0 0 0 2 14.63v3.24a2 2 0 0 0 .97 1.71l3 1.8a2 2 0 0 0 2.06 0L12 19v-5.5l-5-3-4.03 2.42Z" key="lc1i9w" />
    <path d="m7 16.5-4.74-2.85" key="1o9zyk" />
    <path d="m7 16.5 5-3" key="va8pkn" />
    <path d="M7 16.5v5.17" key="jnp8gn" />
    <path d="M12 13.5V19l3.97 2.38a2 2 0 0 0 2.06 0l3-1.8a2 2 0 0 0 .97-1.71v-3.24a2 2 0 0 0-.97-1.71L17 10.5l-5 3Z" key="8zsnat" />
    <path d="m17 16.5-5-3" key="8arw3v" />
    <path d="m17 16.5 4.74-2.85" key="8rfmw" />
    <path d="M17 16.5v5.17" key="k6z78m" />
    <path d="M7.97 4.42A2 2 0 0 0 7 6.13v4.37l5 3 5-3V6.13a2 2 0 0 0-.97-1.71l-3-1.8a2 2 0 0 0-2.06 0l-3 1.8Z" key="1xygjf" />
    <path d="M12 8 7.26 5.15" key="1vbdud" />
    <path d="m12 8 4.74-2.85" key="3rx089" />
    <path d="M12 13.5V8" key="1io7kd" />
  </>
))

export const Briefcase = createIcon('Briefcase', (
  <>
    <path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" key="jecpp" />
    <rect width="20" height="14" x="2" y="6" rx="2" key="i6l2r4" />
  </>
))

export const Building2 = createIcon('Building2', (
  <>
    <path d="M10 12h4" key="a56b0p" />
    <path d="M10 8h4" key="1sr2af" />
    <path d="M14 21v-3a2 2 0 0 0-4 0v3" key="1rgiei" />
    <path d="M6 10H4a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2" key="secmi2" />
    <path d="M6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16" key="16ra0t" />
  </>
))

export const Cable = createIcon('Cable', (
  <>
    <path d="M17 19a1 1 0 0 1-1-1v-2a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2a1 1 0 0 1-1 1z" key="trhst0" />
    <path d="M17 21v-2" key="ds4u3f" />
    <path d="M19 14V6.5a1 1 0 0 0-7 0v11a1 1 0 0 1-7 0V10" key="1mo9zo" />
    <path d="M21 21v-2" key="eo0ou" />
    <path d="M3 5V3" key="1k5hjh" />
    <path d="M4 10a2 2 0 0 1-2-2V6a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2a2 2 0 0 1-2 2z" key="1dd30t" />
    <path d="M7 5V3" key="1t1388" />
  </>
))

export const Check = createIcon('Check', (
  <>
    <path d="M20 6 9 17l-5-5" key="1gmf2c" />
  </>
))

export const CheckCheck = createIcon('CheckCheck', (
  <>
    <path d="M18 6 7 17l-5-5" key="116fxf" />
    <path d="m22 10-7.5 7.5L13 16" key="ke71qq" />
  </>
))

export const CheckCircle2 = createIcon('CheckCircle2', (
  <>
    <circle cx="12" cy="12" r="10" key="1mglay" />
    <path d="m9 12 2 2 4-4" key="dzmm74" />
  </>
))

export const ChevronRight = createIcon('ChevronRight', (
  <>
    <path d="m9 18 6-6-6-6" key="mthhwq" />
  </>
))

export const Clock = createIcon('Clock', (
  <>
    <circle cx="12" cy="12" r="10" key="1mglay" />
    <path d="M12 6v6l4 2" key="mmk7yg" />
  </>
))

export const Cloud = createIcon('Cloud', (
  <>
    <path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z" key="p7xjir" />
  </>
))

export const Cpu = createIcon('Cpu', (
  <>
    <path d="M12 20v2" key="1lh1kg" />
    <path d="M12 2v2" key="tus03m" />
    <path d="M17 20v2" key="1rnc9c" />
    <path d="M17 2v2" key="11trls" />
    <path d="M2 12h2" key="1t8f8n" />
    <path d="M2 17h2" key="7oei6x" />
    <path d="M2 7h2" key="asdhe0" />
    <path d="M20 12h2" key="1q8mjw" />
    <path d="M20 17h2" key="1fpfkl" />
    <path d="M20 7h2" key="1o8tra" />
    <path d="M7 20v2" key="4gnj0m" />
    <path d="M7 2v2" key="1i4yhu" />
    <rect x="4" y="4" width="16" height="16" rx="2" key="1vbyd7" />
    <rect x="8" y="8" width="8" height="8" rx="1" key="z9xiuo" />
  </>
))

export const CreditCard = createIcon('CreditCard', (
  <>
    <rect width="20" height="14" x="2" y="5" rx="2" key="ynyp8z" />
    <line x1="2" x2="22" y1="10" y2="10" key="1b3vmo" />
  </>
))

export const Eye = createIcon('Eye', (
  <>
    <path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0" key="1nclc0" />
    <circle cx="12" cy="12" r="3" key="1v7zrd" />
  </>
))

export const EyeOff = createIcon('EyeOff', (
  <>
    <path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49" key="ct8e1f" />
    <path d="M14.084 14.158a3 3 0 0 1-4.242-4.242" key="151rxh" />
    <path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143" key="13bj9a" />
    <path d="m2 2 20 20" key="1ooewy" />
  </>
))

export const FileText = createIcon('FileText', (
  <>
    <path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z" key="1oefj6" />
    <path d="M14 2v5a1 1 0 0 0 1 1h5" key="wfsgrz" />
    <path d="M10 9H8" key="b1mrlr" />
    <path d="M16 13H8" key="t4e002" />
    <path d="M16 17H8" key="z1uh3a" />
  </>
))

export const Filter = createIcon('Filter', (
  <>
    <path d="M10 20a1 1 0 0 0 .553.895l2 1A1 1 0 0 0 14 21v-7a2 2 0 0 1 .517-1.341L21.74 4.67A1 1 0 0 0 21 3H3a1 1 0 0 0-.742 1.67l7.225 7.989A2 2 0 0 1 10 14z" key="sc7q7i" />
  </>
))

export const FolderKanban = createIcon('FolderKanban', (
  <>
    <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" key="1fr9dc" />
    <path d="M8 10v4" key="tgpxqk" />
    <path d="M12 10v2" key="hh53o1" />
    <path d="M16 10v6" key="1d6xys" />
  </>
))

export const Gauge = createIcon('Gauge', (
  <>
    <path d="m12 14 4-4" key="9kzdfg" />
    <path d="M3.34 19a10 10 0 1 1 17.32 0" key="19p75a" />
  </>
))

export const History = createIcon('History', (
  <>
    <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" key="1357e3" />
    <path d="M3 3v5h5" key="1xhq8a" />
    <path d="M12 7v5l4 2" key="1fdv2h" />
  </>
))

export const Home = createIcon('Home', (
  <>
    <path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8" key="5wwlr5" />
    <path d="M3 10a2 2 0 0 1 .709-1.528l7-6a2 2 0 0 1 2.582 0l7 6A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" key="r6nss1" />
  </>
))

export const Layers = createIcon('Layers', (
  <>
    <path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z" key="zw3jo" />
    <path d="M2 12a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 12" key="1wduqc" />
    <path d="M2 17a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 17" key="kqbvx6" />
  </>
))

export const LayoutDashboard = createIcon('LayoutDashboard', (
  <>
    <rect width="7" height="9" x="3" y="3" rx="1" key="10lvy0" />
    <rect width="7" height="5" x="14" y="3" rx="1" key="16une8" />
    <rect width="7" height="9" x="14" y="12" rx="1" key="1hutg5" />
    <rect width="7" height="5" x="3" y="16" rx="1" key="ldoo1y" />
  </>
))

export const LifeBuoy = createIcon('LifeBuoy', (
  <>
    <circle cx="12" cy="12" r="10" key="1mglay" />
    <path d="m4.93 4.93 4.24 4.24" key="1ymg45" />
    <path d="m14.83 9.17 4.24-4.24" key="1cb5xl" />
    <path d="m14.83 14.83 4.24 4.24" key="q42g0n" />
    <path d="m9.17 14.83-4.24 4.24" key="bqpfvv" />
    <circle cx="12" cy="12" r="4" key="4exip2" />
  </>
))

export const LineChart = createIcon('LineChart', (
  <>
    <path d="M3 3v16a2 2 0 0 0 2 2h16" key="c24i48" />
    <path d="m19 9-5 5-4-4-3 3" key="2osh9i" />
  </>
))

export const Loader2 = createIcon('Loader2', (
  <>
    <path d="M21 12a9 9 0 1 1-6.219-8.56" key="13zald" />
  </>
))

export const Lock = createIcon('Lock', (
  <>
    <rect width="18" height="11" x="3" y="11" rx="2" ry="2" key="1w4ew1" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" key="fwvmzm" />
  </>
))

export const LogOut = createIcon('LogOut', (
  <>
    <path d="m16 17 5-5-5-5" key="1bji2h" />
    <path d="M21 12H9" key="dn1m92" />
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" key="1uf3rs" />
  </>
))

export const Mail = createIcon('Mail', (
  <>
    <path d="m22 7-8.991 5.727a2 2 0 0 1-2.009 0L2 7" key="132q7q" />
    <rect x="2" y="4" width="20" height="16" rx="2" key="izxlao" />
  </>
))

export const Megaphone = createIcon('Megaphone', (
  <>
    <path d="M11 6a13 13 0 0 0 8.4-2.8A1 1 0 0 1 21 4v12a1 1 0 0 1-1.6.8A13 13 0 0 0 11 14H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z" key="q8bfy3" />
    <path d="M6 14a12 12 0 0 0 2.4 7.2 2 2 0 0 0 3.2-2.4A8 8 0 0 1 10 14" key="1853fq" />
    <path d="M8 6v8" key="15ugcq" />
  </>
))

export const Menu = createIcon('Menu', (
  <>
    <path d="M4 5h16" key="1tepv9" />
    <path d="M4 12h16" key="1lakjw" />
    <path d="M4 19h16" key="1djgab" />
  </>
))

export const MessageCircle = createIcon('MessageCircle', (
  <>
    <path d="M2.992 16.342a2 2 0 0 1 .094 1.167l-1.065 3.29a1 1 0 0 0 1.236 1.168l3.413-.998a2 2 0 0 1 1.099.092 10 10 0 1 0-4.777-4.719" key="1sd12s" />
  </>
))

export const MessageSquare = createIcon('MessageSquare', (
  <>
    <path d="M22 17a2 2 0 0 1-2 2H6.828a2 2 0 0 0-1.414.586l-2.202 2.202A.71.71 0 0 1 2 21.286V5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2z" key="18887p" />
  </>
))

export const Mic2 = createIcon('Mic2', (
  <>
    <path d="m11 7.601-5.994 8.19a1 1 0 0 0 .1 1.298l.817.818a1 1 0 0 0 1.314.087L15.09 12" key="80a601" />
    <path d="M16.5 21.174C15.5 20.5 14.372 20 13 20c-2.058 0-3.928 2.356-6 2-2.072-.356-2.775-3.369-1.5-4.5" key="j0ngtp" />
    <circle cx="16" cy="7" r="5" key="d08jfb" />
  </>
))

export const Minimize2 = createIcon('Minimize2', (
  <>
    <path d="m14 10 7-7" key="oa77jy" />
    <path d="M20 10h-6V4" key="mjg0md" />
    <path d="m3 21 7-7" key="tjx5ai" />
    <path d="M4 14h6v6" key="rmj7iw" />
  </>
))

export const Monitor = createIcon('Monitor', (
  <>
    <rect width="20" height="14" x="2" y="3" rx="2" key="48i651" />
    <line x1="8" x2="16" y1="21" y2="21" key="1svkeh" />
    <line x1="12" x2="12" y1="17" y2="21" key="vw1qmm" />
  </>
))

export const MonitorPlay = createIcon('MonitorPlay', (
  <>
    <path d="M15.033 9.44a.647.647 0 0 1 0 1.12l-4.065 2.352a.645.645 0 0 1-.968-.56V7.648a.645.645 0 0 1 .967-.56z" key="vbtd3f" />
    <path d="M12 17v4" key="1riwvh" />
    <path d="M8 21h8" key="1ev6f3" />
    <rect x="2" y="3" width="20" height="14" rx="2" key="x3v2xh" />
  </>
))

export const Moon = createIcon('Moon', (
  <>
    <path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401" key="kfwtm" />
  </>
))

export const Phone = createIcon('Phone', (
  <>
    <path d="M13.832 16.568a1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 6.392 6.384" key="9njp5v" />
  </>
))

export const Play = createIcon('Play', (
  <>
    <path d="M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z" key="10ikf1" />
  </>
))

export const RefreshCw = createIcon('RefreshCw', (
  <>
    <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" key="v9h5vc" />
    <path d="M21 3v5h-5" key="1q7to0" />
    <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" key="3uifl3" />
    <path d="M8 16H3v5" key="1cv678" />
  </>
))

export const RotateCcw = createIcon('RotateCcw', (
  <>
    <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" key="1357e3" />
    <path d="M3 3v5h5" key="1xhq8a" />
  </>
))

export const Route = createIcon('Route', (
  <>
    <circle cx="6" cy="19" r="3" key="1kj8tv" />
    <path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15" key="1d8sl" />
    <circle cx="18" cy="5" r="3" key="gq8acd" />
  </>
))

export const ScrollText = createIcon('ScrollText', (
  <>
    <path d="M15 12h-5" key="r7krc0" />
    <path d="M15 8h-5" key="1khuty" />
    <path d="M19 17V5a2 2 0 0 0-2-2H4" key="zz82l3" />
    <path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3" key="1ph1d7" />
  </>
))

export const Search = createIcon('Search', (
  <>
    <path d="m21 21-4.34-4.34" key="14j7rj" />
    <circle cx="11" cy="11" r="8" key="4ej97u" />
  </>
))

export const Send = createIcon('Send', (
  <>
    <path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z" key="1ffxy3" />
    <path d="m21.854 2.147-10.94 10.939" key="12cjpa" />
  </>
))

export const Server = createIcon('Server', (
  <>
    <rect width="20" height="8" x="2" y="2" rx="2" ry="2" key="ngkwjq" />
    <rect width="20" height="8" x="2" y="14" rx="2" ry="2" key="iecqi9" />
    <line x1="6" x2="6.01" y1="6" y2="6" key="16zg32" />
    <line x1="6" x2="6.01" y1="18" y2="18" key="nzw8ys" />
  </>
))

export const Shield = createIcon('Shield', (
  <>
    <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" key="oel41y" />
  </>
))

export const ShieldAlert = createIcon('ShieldAlert', (
  <>
    <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" key="oel41y" />
    <path d="M12 8v4" key="1got3b" />
    <path d="M12 16h.01" key="1drbdi" />
  </>
))

export const ShieldCheck = createIcon('ShieldCheck', (
  <>
    <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" key="oel41y" />
    <path d="m9 12 2 2 4-4" key="dzmm74" />
  </>
))

export const Skull = createIcon('Skull', (
  <>
    <path d="m12.5 17-.5-1-.5 1h1z" key="3me087" />
    <path d="M15 22a1 1 0 0 0 1-1v-1a2 2 0 0 0 1.56-3.25 8 8 0 1 0-11.12 0A2 2 0 0 0 8 20v1a1 1 0 0 0 1 1z" key="1o5pge" />
    <circle cx="15" cy="12" r="1" key="1tmaij" />
    <circle cx="9" cy="12" r="1" key="1vctgf" />
  </>
))

export const Sparkles = createIcon('Sparkles', (
  <>
    <path d="M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z" key="1s2grr" />
    <path d="M20 2v4" key="1rf3ol" />
    <path d="M22 4h-4" key="gwowj6" />
    <circle cx="4" cy="20" r="2" key="6kqj1y" />
  </>
))

export const Star = createIcon('Star', (
  <>
    <path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z" key="r04s7s" />
  </>
))

export const Sun = createIcon('Sun', (
  <>
    <circle cx="12" cy="12" r="4" key="4exip2" />
    <path d="M12 2v2" key="tus03m" />
    <path d="M12 20v2" key="1lh1kg" />
    <path d="m4.93 4.93 1.41 1.41" key="149t6j" />
    <path d="m17.66 17.66 1.41 1.41" key="ptbguv" />
    <path d="M2 12h2" key="1t8f8n" />
    <path d="M20 12h2" key="1q8mjw" />
    <path d="m6.34 17.66-1.41 1.41" key="1m8zz5" />
    <path d="m19.07 4.93-1.41 1.41" key="1shlcs" />
  </>
))

export const Tag = createIcon('Tag', (
  <>
    <path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z" key="vktsd0" />
    <circle cx="7.5" cy="7.5" r=".5" fill="currentColor" key="kqv944" />
  </>
))

export const Target = createIcon('Target', (
  <>
    <circle cx="12" cy="12" r="10" key="1mglay" />
    <circle cx="12" cy="12" r="6" key="1vlfrh" />
    <circle cx="12" cy="12" r="2" key="1c9p78" />
  </>
))

export const Terminal = createIcon('Terminal', (
  <>
    <path d="M12 19h8" key="baeox8" />
    <path d="m4 17 6-6-6-6" key="1yngyt" />
  </>
))

export const Thermometer = createIcon('Thermometer', (
  <>
    <path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z" key="17jzev" />
  </>
))

export const ThumbsDown = createIcon('ThumbsDown', (
  <>
    <path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z" key="m61m77" />
    <path d="M17 14V2" key="8ymqnk" />
  </>
))

export const ThumbsUp = createIcon('ThumbsUp', (
  <>
    <path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z" key="emmmcr" />
    <path d="M7 10v12" key="1qc93n" />
  </>
))

export const Ticket = createIcon('Ticket', (
  <>
    <path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z" key="qn84l0" />
    <path d="M13 5v2" key="dyzc3o" />
    <path d="M13 17v2" key="1ont0d" />
    <path d="M13 11v2" key="1wjjxi" />
  </>
))

export const Trash2 = createIcon('Trash2', (
  <>
    <path d="M10 11v6" key="nco0om" />
    <path d="M14 11v6" key="outv1u" />
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" key="miytrc" />
    <path d="M3 6h18" key="d0wm0j" />
    <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" key="e791ji" />
  </>
))

export const Trophy = createIcon('Trophy', (
  <>
    <path d="M10 14.66v1.626a2 2 0 0 1-.976 1.696A5 5 0 0 0 7 21.978" key="1n3hpd" />
    <path d="M14 14.66v1.626a2 2 0 0 0 .976 1.696A5 5 0 0 1 17 21.978" key="rfe1zi" />
    <path d="M18 9h1.5a1 1 0 0 0 0-5H18" key="7xy6bh" />
    <path d="M4 22h16" key="57wxv0" />
    <path d="M6 9a6 6 0 0 0 12 0V3a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1z" key="1mhfuq" />
    <path d="M6 9H4.5a1 1 0 0 1 0-5H6" key="tex48p" />
  </>
))

export const User = createIcon('User', (
  <>
    <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" key="975kel" />
    <circle cx="12" cy="7" r="4" key="17ys0d" />
  </>
))

export const Users = createIcon('Users', (
  <>
    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" key="1yyitq" />
    <path d="M16 3.128a4 4 0 0 1 0 7.744" key="16gr8j" />
    <path d="M22 21v-2a4 4 0 0 0-3-3.87" key="kshegd" />
    <circle cx="9" cy="7" r="4" key="nufk8" />
  </>
))

export const WifiOff = createIcon('WifiOff', (
  <>
    <path d="M12 20h.01" key="zekei9" />
    <path d="M8.5 16.429a5 5 0 0 1 7 0" key="1bycff" />
    <path d="M5 12.859a10 10 0 0 1 5.17-2.69" key="1dl1wf" />
    <path d="M19 12.859a10 10 0 0 0-2.007-1.523" key="4k23kn" />
    <path d="M2 8.82a15 15 0 0 1 4.177-2.643" key="1grhjp" />
    <path d="M22 8.82a15 15 0 0 0-11.288-3.764" key="z3jwby" />
    <path d="m2 2 20 20" key="1ooewy" />
  </>
))

export const Wrench = createIcon('Wrench', (
  <>
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.106-3.105c.32-.322.863-.22.983.218a6 6 0 0 1-8.259 7.057l-7.91 7.91a1 1 0 0 1-2.999-3l7.91-7.91a6 6 0 0 1 7.057-8.259c.438.12.54.662.219.984z" key="1ngwbx" />
  </>
))

export const X = createIcon('X', (
  <>
    <path d="M18 6 6 18" key="1bl5f8" />
    <path d="m6 6 12 12" key="d8bk6v" />
  </>
))

export const Zap = createIcon('Zap', (
  <>
    <path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z" key="1xq2db" />
  </>
))

