const ICONS = {
  linux: (
    <>
      <rect x="2" y="3" width="20" height="7" rx="1.5" />
      <rect x="2" y="14" width="20" height="7" rx="1.5" />
      <line x1="6" y1="6.5" x2="6.01" y2="6.5" />
      <line x1="6" y1="17.5" x2="6.01" y2="17.5" />
    </>
  ),
  docker: (
    <>
      <rect x="2" y="3" width="20" height="14" rx="2" />
      <line x1="8" y1="21" x2="16" y2="21" />
      <line x1="12" y1="17" x2="12" y2="21" />
    </>
  ),
  kubernetes: (
    <>
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <rect x="9" y="9" width="6" height="6" />
      <path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3" />
    </>
  ),
  aws: <path d="M17.5 19a4.5 4.5 0 0 0 0-9 6 6 0 0 0-11.6 1.5A4 4 0 0 0 6 19z" />,
  networking: (
    <>
      <circle cx="12" cy="12" r="9" />
      <line x1="3" y1="12" x2="21" y2="12" />
      <path d="M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18" />
    </>
  ),
  database: (
    <>
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5" />
      <path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
    </>
  ),
  vmware: (
    <>
      <rect x="3" y="4" width="18" height="12" rx="2" />
      <path d="M7 20h10M12 16v4" />
    </>
  ),
  security: <path d="M12 2 4 5v6c0 5 3.4 8.5 8 10 4.6-1.5 8-5 8-10V5z" />,
  gpu: (
    <>
      <rect x="2" y="6" width="20" height="12" rx="2" />
      <rect x="6" y="10" width="5" height="4" rx="1" />
      <circle cx="16" cy="12" r="2" />
    </>
  ),
  ansible: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7l3.5 8-5-3z" />
    </>
  ),
  python: (
    <>
      <path d="M12 3c-3 0-4 1.2-4 3v2h4v1H6c-1.8 0-3 1-3 4s1.2 4 3 4h2v-2.5c0-1.8 1.2-2.5 3-2.5h3" />
      <path d="M12 21c3 0 4-1.2 4-3v-2h-4v-1h6c1.8 0 3-1 3-4s-1.2-4-3-4h-2v2.5c0 1.8-1.2 2.5-3 2.5H10" />
    </>
  ),
  java: (
    <>
      <path d="M9 18c-1.5.7-2 1.3 0 2 3 1 8 1 11 0" />
      <path d="M10 14c-1 .6-1.5 1.2 0 1.8 2.2.9 6.5.9 9 0" />
      <path d="M12 3c2 2 2 3 0 5s-2 3 0 5" />
      <path d="M16 4c1.5 1.5 1 3-1 4.5" />
    </>
  ),
  'shell-script': (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M7 9l3 3-3 3M13 15h4" />
    </>
  ),
  html: (
    <>
      <path d="M4 3l1.6 18L12 23l6.4-2L20 3z" />
      <path d="M8 8h8l-.5 4-3.5 1-3.5-1" />
    </>
  ),
  devops: (
    <>
      <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
      <path d="M3 21v-5h5" />
    </>
  ),
  baremetal: (
    <>
      <rect x="3" y="4" width="18" height="6" rx="1.5" />
      <rect x="3" y="14" width="18" height="6" rx="1.5" />
      <line x1="7" y1="7" x2="7.01" y2="7" />
      <line x1="7" y1="17" x2="7.01" y2="17" />
      <line x1="17" y1="7" x2="11" y2="7" />
      <line x1="17" y1="17" x2="11" y2="17" />
    </>
  ),
  'prompt-engineering': (
    <>
      <path d="M5 3v4M3 5h4M6 17v4M4 19h4" />
      <path d="M13 4l2.5 6.5L22 13l-6.5 2.5L13 22l-2.5-6.5L4 13l6.5-2.5z" />
    </>
  ),
}

/** Map alternative / legacy slugs to a canonical icon key. */
const SLUG_ALIASES = {
  databases: 'database',
  'gpu-nvidia': 'gpu',
  nvidia: 'gpu',
  terraform: 'devops',
  'web-servers': 'html',
  webservers: 'html',
  nginx: 'html',
  bash: 'shell-script',
  shell: 'shell-script',
  'shell-scripting': 'shell-script',
  'prompt': 'prompt-engineering',
}

export default function TechIcon({ slug, name, size = 26, className = '' }) {
  const key = slug || (name || '').toLowerCase().replace(/\s+/g, '-').replace('&', '')
  const inner = ICONS[key] || ICONS[SLUG_ALIASES[key]] || ICONS.linux
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {inner}
    </svg>
  )
}
