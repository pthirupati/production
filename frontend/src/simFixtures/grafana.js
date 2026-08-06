/** Grafana UI seed data for monitoring simulator */

export const GRAFANA_FOLDERS = [
  { id: 'general', name: 'General', dashboards: 3 },
  { id: 'infra', name: 'Infrastructure', dashboards: 5 },
  { id: 'apps', name: 'Applications', dashboards: 4 },
  { id: 'slo', name: 'SLO / SLI', dashboards: 2 },
]

export const GRAFANA_DASHBOARD_BROWSE = [
  { uid: 'infra-nodes', title: 'Node Exporter Full', folder: 'Infrastructure', tags: ['linux', 'prometheus'], updated: '2026-06-24' },
  { uid: 'k8s-cluster', title: 'Kubernetes Cluster', folder: 'Infrastructure', tags: ['k8s'], updated: '2026-06-23' },
  { uid: 'api-latency', title: 'API Latency SLO', folder: 'SLO / SLI', tags: ['http', 'slo'], updated: '2026-06-22' },
  { uid: 'home-overview', title: 'Home Overview', folder: 'General', tags: ['home'], updated: '2026-06-20' },
]

export const GRAFANA_PLAYLISTS = [
  { id: 'pl1', name: 'NOC Rotation', dashboards: 4, interval: '30s' },
  { id: 'pl2', name: 'Executive Summary', dashboards: 2, interval: '60s' },
]

export const GRAFANA_SNAPSHOTS = [
  { id: 'sn1', name: 'Incident 2026-06-20', created: '2026-06-20T14:00:00Z', expires: '2026-07-20' },
]

export const GRAFANA_LIBRARY_PANELS = [
  { id: 'lp1', name: 'CPU Usage Stat', type: 'stat', datasource: 'Prometheus' },
  { id: 'lp2', name: 'Request Rate Graph', type: 'timeseries', datasource: 'Prometheus' },
]

export const GRAFANA_ALERT_RULES_UI = [
  { name: 'HighErrorRate', folder: 'SLO / SLI', state: 'firing', eval: '5m' },
  { name: 'DiskAlmostFull', folder: 'Infrastructure', state: 'pending', eval: '10m' },
]

export const GRAFANA_CONTACT_POINTS = [
  { name: 'Slack #alerts', type: 'slack', default: true },
  { name: 'PagerDuty Platform', type: 'pagerduty', default: false },
]

export const GRAFANA_DATASOURCE_WIZARD = [
  { type: 'Prometheus', icon: '🔥', desc: 'Connect to Prometheus or Mimir' },
  { type: 'Loki', icon: '📜', desc: 'Log aggregation' },
  { type: 'Tempo', icon: '🔍', desc: 'Distributed tracing' },
  { type: 'CloudWatch', icon: '☁️', desc: 'AWS metrics and logs' },
]
