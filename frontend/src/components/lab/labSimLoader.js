/**
 * Lazy-loaded lab simulators — keeps LabRunner chunk small until a sim is needed.
 */
import { lazy } from 'react'

export const LazyAwsLabOverlay = lazy(() => import('../aws/AwsLabOverlay'))
export const LazyTerraformSimulator = lazy(() => import('../terraform/TerraformSimulator'))
export const LazyAwxSimulator = lazy(() => import('../awx/AwxSimulator'))
export const LazyMonitoringSimulator = lazy(() => import('../monitoring/MonitoringSimulator'))
export const LazyWindowsServerSimulator = lazy(() => import('../windows/WindowsServerSimulator'))
export const LazyPeopleSoftSimulator = lazy(() => import('../peoplesoft/PeopleSoftSimulator'))
export const LazyBaremetalSimulator = lazy(() => import('../baremetal/BaremetalSimulator'))
export const LazyDataDashboardSimulator = lazy(() => import('../datascience/DataDashboardSimulator'))
export const LazyAgentWorkflowSimulator = lazy(() => import('../aiml/AgentWorkflowSimulator'))
export const LazyNmapSimulator = lazy(() => import('../nmap/NmapSimulator'))
export const LazyWiresharkSimulator = lazy(() => import('../wireshark/WiresharkSimulator'))
export const LazyCicdPipelineSim = lazy(() => import('../devops/CicdPipelineSim'))
export const LazyCodingIDE = lazy(() => import('../ide/CodingIDE'))
export const LazyPromptPlayground = lazy(() => import('../promptlab/PromptPlayground'))

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
}
