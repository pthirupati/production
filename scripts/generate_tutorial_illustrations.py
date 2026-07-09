#!/usr/bin/env python3
"""Generate topic SVG illustrations for tutorial hero images."""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "tutorials" / "illustrations"

TOPICS = {
    "general": ("Platform overview", "#22d3ee", "#a78bfa"),
    "linux": ("Linux host", "#4ade80", "#22d3ee"),
    "kubernetes": ("Kubernetes cluster", "#60a5fa", "#a78bfa"),
    "docker": ("Containers", "#38bdf8", "#22d3ee"),
    "aws": ("AWS cloud", "#f59e0b", "#f97316"),
    "terraform": ("Infrastructure as code", "#a78bfa", "#818cf8"),
    "ansible": ("Automation", "#f472b6", "#fb7185"),
    "devops": ("CI/CD pipeline", "#34d399", "#22d3ee"),
    "python": ("Python runtime", "#fbbf24", "#f59e0b"),
    "database": ("Data store", "#94a3b8", "#64748b"),
    "monitoring": ("Observability", "#f97316", "#fb923c"),
    "networking": ("Network fabric", "#2dd4bf", "#14b8a6"),
    "security": ("Security controls", "#f87171", "#ef4444"),
    "windows": ("Windows server", "#60a5fa", "#3b82f6"),
    "vmware": ("Virtualization", "#818cf8", "#6366f1"),
    "shell": ("Shell scripting", "#4ade80", "#22c55e"),
    "javascript": ("JavaScript", "#facc15", "#eab308"),
    "react": ("React UI", "#22d3ee", "#06b6d4"),
    "java": ("JVM platform", "#f87171", "#dc2626"),
    "html": ("Web foundations", "#fb923c", "#f97316"),
    "nodejs": ("Node.js", "#4ade80", "#16a34a"),
    "gpu": ("GPU compute", "#a78bfa", "#8b5cf6"),
    "ai": ("AI / ML stack", "#c084fc", "#a855f7"),
}


def svg(title: str, c1: str, c2: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 420" role="img" aria-label="{title}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#1e293b"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="{c1}"/>
      <stop offset="100%" stop-color="{c2}"/>
    </linearGradient>
  </defs>
  <rect width="800" height="420" rx="16" fill="url(#bg)"/>
  <text x="400" y="52" text-anchor="middle" fill="#e2e8f0" font-family="system-ui,sans-serif" font-size="28" font-weight="700">{title}</text>
  <text x="400" y="82" text-anchor="middle" fill="#94a3b8" font-family="system-ui,sans-serif" font-size="14">Architecture overview — study before hands-on labs</text>
  <rect x="80" y="120" width="180" height="90" rx="10" fill="#1e293b" stroke="url(#accent)" stroke-width="2"/>
  <text x="170" y="158" text-anchor="middle" fill="#cbd5e1" font-family="system-ui,sans-serif" font-size="13" font-weight="600">Control plane</text>
  <text x="170" y="182" text-anchor="middle" fill="#64748b" font-family="system-ui,sans-serif" font-size="11">config · policy</text>
  <rect x="310" y="120" width="180" height="90" rx="10" fill="#1e293b" stroke="url(#accent)" stroke-width="2"/>
  <text x="400" y="158" text-anchor="middle" fill="#cbd5e1" font-family="system-ui,sans-serif" font-size="13" font-weight="600">Runtime</text>
  <text x="400" y="182" text-anchor="middle" fill="#64748b" font-family="system-ui,sans-serif" font-size="11">services · workloads</text>
  <rect x="540" y="120" width="180" height="90" rx="10" fill="#1e293b" stroke="url(#accent)" stroke-width="2"/>
  <text x="630" y="158" text-anchor="middle" fill="#cbd5e1" font-family="system-ui,sans-serif" font-size="13" font-weight="600">Data plane</text>
  <text x="630" y="182" text-anchor="middle" fill="#64748b" font-family="system-ui,sans-serif" font-size="11">storage · network</text>
  <path d="M260 165 H310 M490 165 H540" stroke="url(#accent)" stroke-width="2" marker-end="url(#arrow)"/>
  <rect x="140" y="260" width="520" height="110" rx="12" fill="#0f172a" stroke="#334155" stroke-width="1.5"/>
  <text x="400" y="295" text-anchor="middle" fill="#94a3b8" font-family="system-ui,sans-serif" font-size="12">Operator workflow</text>
  <circle cx="200" cy="325" r="8" fill="url(#accent)"/>
  <text x="220" y="329" fill="#e2e8f0" font-family="system-ui,sans-serif" font-size="12">Inspect baseline</text>
  <circle cx="360" cy="325" r="8" fill="url(#accent)"/>
  <text x="380" y="329" fill="#e2e8f0" font-family="system-ui,sans-serif" font-size="12">Apply change</text>
  <circle cx="520" cy="325" r="8" fill="url(#accent)"/>
  <text x="540" y="329" fill="#e2e8f0" font-family="system-ui,sans-serif" font-size="12">Verify &amp; document</text>
</svg>
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for key, (title, c1, c2) in TOPICS.items():
        (OUT / f"{key}.svg").write_text(svg(title, c1, c2), encoding="utf-8")
    print(f"Wrote {len(TOPICS)} illustrations to {OUT}")


if __name__ == "__main__":
    main()
