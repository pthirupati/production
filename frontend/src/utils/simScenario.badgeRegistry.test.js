// @vitest-environment node
//
// Audit L509. simScenario's SIM_TYPES was documented as "resolve which in-app
// simulator a scenario opens", which reads like a routing table. It is not one —
// it is badge copy for ScenarioDetail — and the mislabel let it drift ~10 kinds
// behind the real router (labSimLoader.PRIMARY_SIM_COMPONENTS + LabRunner's
// primarySimKind chain).
//
// The dangerous "fix" here would be to make SIM_TYPES authoritative and drive
// routing from it, which would silently unroute every kind it lacks. These tests
// pin the opposite invariant: the badge map is allowed to be a SUBSET, it must
// never gate routing, and widening it must not start badging non-simulation
// scenarios.
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it, expect } from 'vitest'
import { getScenarioSimInfo } from './simScenario'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SRC = path.resolve(HERE, '..')

describe('SIM_TYPES is badge copy, not a router', () => {
  it('is not imported by anything on the lab routing path', async () => {
    // LabRunner / labSimLoader / scenarioConsoles decide which console opens.
    // If any of them starts importing simScenario, routing has been coupled to
    // badge copy and the drift becomes load-bearing.
    for (const rel of [
      'pages/LabRunner.jsx',
      'components/lab/labSimLoader.js',
      'components/lab/PrimaryLabSim.jsx',
      'utils/scenarioConsoles.js',
    ]) {
      const src = await fs.readFile(path.join(SRC, rel), 'utf8')
      expect(src, `${rel} must not import simScenario`).not.toMatch(/from ['"].*simScenario['"]/)
    }
  })

  it('no longer describes itself as a resolver', async () => {
    const src = await fs.readFile(path.join(SRC, 'utils/simScenario.js'), 'utf8')
    expect(src).not.toMatch(/Resolve which in-app simulator a scenario opens/)
    expect(src).toMatch(/NOT the router/)
  })

  it('badges the consoles that previously had none', () => {
    // These all had a component in PRIMARY_SIM_COMPONENTS but no badge entry.
    const cases = [
      ['azure', 'Azure'], ['gcp', 'GCP'], ['openstack', 'OpenStack'],
      ['k8s', 'Kubernetes'], ['docker', 'Docker'], ['netapp', 'NetApp'],
      ['commvault', 'Commvault'], ['dellemc', 'Dell EMC'],
      ['datacenter', 'Datacenter'], ['soc', 'SOC'],
    ]
    for (const [simType, short] of cases) {
      const info = getScenarioSimInfo({ slug: `${simType}-something`, simulation_type: simType, lab_mode: 'simulation' })
      expect(info?.short, `no badge for ${simType}`).toBe(short)
    }
  })

  it('still returns null for a non-simulation scenario on a newly-badged tech', () => {
    // The regression risk of adding keys: `SIM_TYPES[tech]` is consulted, so a
    // plain terminal Docker/K8s scenario must not suddenly claim a GUI badge.
    for (const tech of ['docker', 'k8s', 'kubernetes', 'azure', 'soc']) {
      expect(
        getScenarioSimInfo({ slug: 'some-terminal-lab', technology: { slug: tech } }),
        `${tech} terminal lab must not be badged`,
      ).toBeNull()
    }
  })

  it('leaves the pre-existing AWS/Terraform precedence untouched', () => {
    expect(getScenarioSimInfo({ slug: 'ec2-launch-basics', lab_mode: 'simulation' })?.key).toBe('aws')
    expect(getScenarioSimInfo({
      slug: 'aws-vpc-basics',
      technology: { slug: 'terraform' },
      simulation_type: 'terraform',
      lab_mode: 'simulation',
    })?.key).toBe('terraform')
  })
})
