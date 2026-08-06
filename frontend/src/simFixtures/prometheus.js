export const PROMETHEUS_CONFIG_YAML = `global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: fixitlab-training
    replica: prom-01

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - /etc/prometheus/rules/*.yml

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets: ['localhost:9090']

  - job_name: node
    static_configs:
      - targets: ['node-exporter:9100', 'web01:9100', 'db01:9100']

  - job_name: kubernetes-apiservers
    kubernetes_sd_configs:
      - role: endpoints
    scheme: https
    tls_config:
      insecure_skip_verify: true
`

export const PROMETHEUS_ALERT_GROUPS = [
  {
    name: 'instance-health',
    rules: [
      { name: 'InstanceDown', state: 'firing', expr: 'up == 0', for: '5m', labels: { severity: 'critical' }, annotations: { summary: 'Instance {{ $labels.instance }} down' } },
      { name: 'HighMemoryUsage', state: 'pending', expr: 'node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes < 0.1', for: '10m', labels: { severity: 'warning' }, annotations: { summary: 'Memory pressure on {{ $labels.instance }}' } },
    ],
  },
  {
    name: 'http-slo',
    rules: [
      { name: 'HighErrorRate', state: 'inactive', expr: 'sum(rate(http_requests_total{code=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > 0.05', for: '15m', labels: { severity: 'warning' }, annotations: { summary: '5xx error rate above 5%' } },
    ],
  },
]

export const PROMETHEUS_SERVICE_DISCOVERY = [
  { job: 'kubernetes-nodes', discovered: 12, labels: ['__meta_kubernetes_node_name', '__address__'] },
  { job: 'consul', discovered: 8, labels: ['__meta_consul_service', '__meta_consul_node'] },
]

// Status → TSDB Status: top cardinality tables (Element | Count)
export const PROM_TSDB_TOP_METRICS = [
  ['node_cpu_seconds_total', 18432],
  ['http_request_duration_seconds_bucket', 14021],
  ['node_filesystem_avail_bytes', 9120],
  ['node_network_receive_bytes_total', 7344],
  ['container_memory_usage_bytes', 6890],
  ['apiserver_request_total', 5210],
  ['node_disk_io_time_seconds_total', 4102],
  ['prometheus_http_requests_total', 3380],
  ['go_gc_duration_seconds', 2240],
  ['up', 312],
]

export const PROM_TSDB_TOP_LABELS = [
  ['__name__', 1284],
  ['instance', 312],
  ['le', 144],
  ['job', 41],
  ['mountpoint', 38],
  ['device', 33],
  ['mode', 8],
  ['code', 7],
  ['method', 6],
  ['quantile', 4],
]

// Status → Flags: command-line flags table (flag | value)
export const PROMETHEUS_FLAGS = [
  ['config.file', '/etc/prometheus/prometheus.yml'],
  ['storage.tsdb.path', '/prometheus'],
  ['storage.tsdb.retention.time', '15d'],
  ['storage.tsdb.retention.size', '0B'],
  ['storage.tsdb.wal-compression', 'true'],
  ['web.listen-address', '0.0.0.0:9090'],
  ['web.external-url', ''],
  ['web.enable-lifecycle', 'true'],
  ['web.enable-admin-api', 'false'],
  ['web.max-connections', '512'],
  ['web.read-timeout', '5m'],
  ['query.max-concurrency', '20'],
  ['query.max-samples', '50000000'],
  ['query.timeout', '2m'],
  ['query.lookback-delta', '5m'],
  ['scrape.adjust-timestamps', 'true'],
  ['rules.alert.for-outage-tolerance', '1h'],
  ['rules.alert.for-grace-period', '10m'],
  ['rules.alert.resend-delay', '1m'],
  ['alertmanager.notification-queue-capacity', '10000'],
  ['log.level', 'info'],
  ['log.format', 'logfmt'],
]
