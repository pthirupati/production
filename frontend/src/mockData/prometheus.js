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
