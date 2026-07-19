/**
 * Lazy-loaded lab consoles — keeps LabRunner chunk small until a console is needed.
 *
 * Use lazyWithRetry (NOT plain React.lazy): a returning user with a cached
 * index.html references the PREVIOUS deploy's hashed chunks, so opening a lab
 * 404s the console chunk. Plain lazy() throws ChunkLoadError straight into
 * SimErrorBoundary ("Lab environment error") — which no store reset can fix.
 * lazyWithRetry retries, then does ONE hard reload to fetch the current
 * index.html, exactly like the route chunks in AppRouter.
 */
import { lazyWithRetry } from '../../utils/lazyWithRetry'

export const LazyAwsLabOverlay = lazyWithRetry(() => import('../aws/AwsLabOverlay'))
export const LazyTerraformSimulator = lazyWithRetry(() => import('../terraform/TerraformSimulator'))
export const LazyAwxSimulator = lazyWithRetry(() => import('../awx/AwxSimulator'))
export const LazyMonitoringSimulator = lazyWithRetry(() => import('../monitoring/MonitoringSimulator'))
export const LazyWindowsServerSimulator = lazyWithRetry(() => import('../windows/WindowsServerSimulator'))
export const LazyPeopleSoftSimulator = lazyWithRetry(() => import('../peoplesoft/PeopleSoftSimulator'))
export const LazyBaremetalSimulator = lazyWithRetry(() => import('../baremetal/BaremetalSimulator'))
export const LazyDataDashboardSimulator = lazyWithRetry(() => import('../datascience/DataDashboardSimulator'))
export const LazyAgentWorkflowSimulator = lazyWithRetry(() => import('../aiml/AgentWorkflowSimulator'))
export const LazyNmapSimulator = lazyWithRetry(() => import('../nmap/NmapSimulator'))
export const LazyWiresharkSimulator = lazyWithRetry(() => import('../wireshark/WiresharkSimulator'))
export const LazyCicdPipelineSim = lazyWithRetry(() => import('../devops/CicdPipelineSim'))
export const LazyCodingIDE = lazyWithRetry(() => import('../ide/CodingIDE'))
export const LazyPromptPlayground = lazyWithRetry(() => import('../promptlab/PromptPlayground'))
export const LazyCommvaultSimulator = lazyWithRetry(() => import('../commvault/CommvaultSimulator'))
export const LazyNetAppSimulator = lazyWithRetry(() => import('../netapp/NetAppSimulator'))
export const LazyDellEmcSimulator = lazyWithRetry(() => import('../dellemc/DellEmcSimulator'))
export const LazyDatacenterSimulator = lazyWithRetry(() => import('../datacenter/DatacenterSimulator'))
export const LazySocSimulator = lazyWithRetry(() => import('../soc/SocSimulator'))
export const LazyAzureConsole = lazyWithRetry(() => import('../azure/AzureConsole'))
export const LazyGcpConsole = lazyWithRetry(() => import('../gcp/GcpConsole'))
export const LazyOpenStackConsole = lazyWithRetry(() => import('../openstack/OpenStackConsole'))

export const PRIMARY_SIM_COMPONENTS = {
  aws: LazyAwsLabOverlay,
  terraform: LazyTerraformSimulator,
  awx: LazyAwxSimulator,
  monitoring: LazyMonitoringSimulator,
  windows: LazyWindowsServerSimulator,
  peoplesoft: LazyPeopleSoftSimulator,
  baremetal: LazyBaremetalSimulator,
  datadashboard: LazyDataDashboardSimulator,
  agent: LazyAgentWorkflowSimulator,
  nmap: LazyNmapSimulator,
  wireshark: LazyWiresharkSimulator,
  cicd: LazyCicdPipelineSim,
  commvault: LazyCommvaultSimulator,
  netapp: LazyNetAppSimulator,
  dellemc: LazyDellEmcSimulator,
  datacenter: LazyDatacenterSimulator,
  soc: LazySocSimulator,
  azure: LazyAzureConsole,
  gcp: LazyGcpConsole,
  openstack: LazyOpenStackConsole,
}
