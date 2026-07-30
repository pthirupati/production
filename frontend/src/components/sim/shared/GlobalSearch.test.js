import { describe, expect, it } from 'vitest'
import {
  filterSearchIndex,
  indexAzureState,
  indexGcpState,
  indexDatacenterState,
  indexSocState,
} from './GlobalSearch'

describe('filterSearchIndex', () => {
  const services = [
    { key: 'vms', label: 'Virtual machines', keywords: 'compute ec2' },
    { key: 'storage', label: 'Storage accounts', keywords: 'blob' },
  ]
  const resources = [
    { type: 'resource', id: 'vm-1', label: 'web-01', sub: 'Virtual machine', navKey: 'vms', hay: 'web-01 vm-1 Virtual machine' },
    { type: 'resource', id: 'sa-1', label: 'stworkloads', sub: 'Storage account', navKey: 'storage', hay: 'stworkloads Storage account' },
  ]

  it('returns empty groups for blank query (except recents)', () => {
    const out = filterSearchIndex({ services, resources, recents: resources.slice(0, 1) }, '')
    expect(out.services).toEqual([])
    expect(out.resources).toEqual([])
    expect(out.recents).toHaveLength(1)
  })

  it('matches services and resources by label/hay', () => {
    const out = filterSearchIndex({ services, resources }, 'web')
    expect(out.services).toHaveLength(0)
    expect(out.resources.map((r) => r.id)).toEqual(['vm-1'])
    const svc = filterSearchIndex({ services, resources }, 'blob')
    expect(svc.services.map((s) => s.id)).toEqual(['storage'])
  })
})

describe('index*State helpers', () => {
  it('indexes Azure VMs and storage', () => {
    const rows = indexAzureState({
      vms: [{ name: 'vm-app01', location: 'eastus', resource_group: 'rg-a' }],
      storage_accounts: [{ name: 'stworkloads', location: 'eastus' }],
    })
    expect(rows.some((r) => r.label === 'vm-app01' && r.navKey === 'vms')).toBe(true)
    expect(rows.some((r) => r.label === 'stworkloads' && r.navKey === 'storage')).toBe(true)
  })

  it('indexes GCP instances with correct nav keys', () => {
    const rows = indexGcpState({ instances: [{ name: 'gce-1', zone: 'us-central1-a' }] })
    expect(rows[0].navKey).toBe('instances')
  })

  it('indexes datacenter rooms and servers', () => {
    const rows = indexDatacenterState({
      rooms: [{ id: 'mdf', name: 'MDF', type: 'network' }],
      servers: [{ id: 'srv-1', hostname: 'esx01', rack_id: 'R1' }],
    })
    expect(rows.some((r) => r.id === 'mdf' && r.navKey === 'rooms')).toBe(true)
    expect(rows.some((r) => r.label === 'esx01' && r.navKey === 'floor')).toBe(true)
  })

  it('indexes SOC alerts onto alerts nav', () => {
    const rows = indexSocState({ alerts: [{ id: 'a1', title: 'Brute force', severity: 'high' }] })
    expect(rows[0].navKey).toBe('alerts')
  })
})
