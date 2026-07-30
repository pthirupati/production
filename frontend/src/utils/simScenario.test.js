// @vitest-environment jsdom
import { describe, it, expect } from 'vitest'
import { getScenarioSimInfo } from './simScenario'
import { isTerraformLab } from './iacFlavor'

describe('simScenario AWS routing', () => {
  it('maps academy-aws packs to AWS console (not Terraform)', () => {
    const info = getScenarioSimInfo({
      slug: 'academy-aws-001-learn-ec2',
      technology: { slug: 'aws' },
      lab_mode: 'simulation',
    })
    expect(info?.key).toBe('aws')
    expect(isTerraformLab({
      slug: 'academy-aws-001-learn-ec2',
      technology: { slug: 'aws' },
    })).toBe(false)
  })

  it('maps ec2-/s3-/iam- heroes to AWS console', () => {
    expect(getScenarioSimInfo({ slug: 'ec2-launch-basics', lab_mode: 'simulation' })?.key).toBe('aws')
    expect(getScenarioSimInfo({ slug: 's3-encrypt-logs', lab_mode: 'simulation' })?.key).toBe('aws')
    expect(getScenarioSimInfo({ slug: 'iam-least-privilege', lab_mode: 'simulation' })?.key).toBe('aws')
  })

  it('maps bare aws-* to AWS console; Terraform only when tech/sim says so', () => {
    expect(getScenarioSimInfo({
      slug: 'aws-ec2-launch-web',
      technology: { slug: 'aws' },
      lab_mode: 'simulation',
    })?.key).toBe('aws')
    expect(isTerraformLab({
      slug: 'aws-vpc-basics',
      technology: { slug: 'terraform' },
      simulation_type: 'terraform',
    })).toBe(true)
    // Explicit terraform sim type wins over slugHints
    expect(getScenarioSimInfo({
      slug: 'aws-vpc-basics',
      technology: { slug: 'terraform' },
      simulation_type: 'terraform',
      lab_mode: 'simulation',
    })?.key).toBe('terraform')
  })
})
