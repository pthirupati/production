import { describe, it, expect, beforeEach } from 'vitest'
import { parseHcl } from '../components/aws/terminal/hclParser.js'
import { syncTerraformApplyToAwsConsole, resetTerraformAwsLabState } from './terraformAwsBridge.js'
import { useAwsStore } from '../components/aws/store/awsStore'

// The IDE's default backend template (terraform_engine.py) drives most applies
// and is entirely variable-based — the old regex bridge could not read it.
const DEFAULT_IDE_MAIN_TF = `terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_instance" "web" {
  ami           = var.ami_id
  instance_type = var.instance_type
  tags = { Name = "web-server" }
}`

const DEFAULT_IDE_VARIABLES_TF = `variable "aws_region" { default = "ap-south-1" }
variable "ami_id"     { default = "ami-0c55b159cbfafe1f0" }
variable "instance_type" { default = "t3.medium" }`

// A richer multi-resource config that the terminal path handles but the regex
// bridge flattened to a single hardcoded instance/bucket/SG.
const MULTI_TF = `variable "web_type" { default = "t3.large" }

provider "aws" {
  region = "eu-west-1"
}

resource "aws_instance" "web" {
  ami                    = "ami-0557a15b87f6559cf"
  instance_type          = var.web_type
  key_name               = "production-key"
  count                  = 2
  vpc_security_group_ids = ["sg-0a1b2c3web00001"]
  tags = { Name = "app-node" }
}

resource "aws_instance" "bastion" {
  ami           = "ami-0c02fb55956c7d316"
  instance_type = "t3.micro"
  tags = { Name = "bastion" }
}

resource "aws_s3_bucket" "data" {
  bucket = "fixit-data-eu-west-1"
}

resource "aws_security_group" "app" {
  name        = "app-sg-tf"
  description = "app tier"
  ingress {
    protocol    = "tcp"
    from_port   = 443
    to_port     = 443
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    protocol    = "tcp"
    from_port   = 22
    to_port     = 22
    cidr_blocks = ["10.0.0.0/8"]
  }
}`

const applied = (files) => ({ state: { terraform: { last_apply: '2026-07-15T00:00:00Z' }, files } })

beforeEach(() => {
  useAwsStore.getState().resetSimulation()
  resetTerraformAwsLabState() // clears the per-session synced-address ledger
})

describe('hclParser variable resolution', () => {
  it('resolves var.* references from declared defaults (the IDE default template)', () => {
    const { resources, provider } = parseHcl(`${DEFAULT_IDE_MAIN_TF}\n${DEFAULT_IDE_VARIABLES_TF}`)
    expect(provider.region).toBe('ap-south-1')
    const web = resources.find((r) => r.type === 'aws_instance')
    expect(web.attrs.ami).toBe('ami-0c55b159cbfafe1f0')
    expect(web.attrs.instance_type).toBe('t3.medium') // not the raw "var.instance_type"
    expect(web.attrs.tags.Name).toBe('web-server')
  })

  it('leaves unknown var refs untouched', () => {
    const { resources } = parseHcl('resource "aws_instance" "x" { instance_type = var.missing }')
    expect(resources[0].attrs.instance_type).toBe('var.missing')
  })
})

describe('syncTerraformApplyToAwsConsole (IDE apply path)', () => {
  it('no-ops until an apply has happened', () => {
    const before = useAwsStore.getState().instances.length
    syncTerraformApplyToAwsConsole({ state: { terraform: {}, files: { 'main.tf': MULTI_TF } } })
    expect(useAwsStore.getState().instances.length).toBe(before)
  })

  it('mirrors every declared resource with accurate, tokenizer-parsed values', () => {
    const s0 = useAwsStore.getState()
    const inst0 = s0.instances.length
    const bkt0 = s0.s3Buckets.length
    const sg0 = s0.securityGroups.length

    syncTerraformApplyToAwsConsole(applied({ 'main.tf': MULTI_TF }))

    const s = useAwsStore.getState()
    // count = 2 web nodes + 1 bastion = 3 new instances
    expect(s.instances.length).toBe(inst0 + 3)
    const appNodes = s.instances.filter((i) => i.name === 'app-node')
    expect(appNodes).toHaveLength(2)
    expect(appNodes[0].type).toBe('t3.large') // resolved from var.web_type
    expect(appNodes[0].keyName).toBe('production-key') // real key, not hardcoded demo-key-pair
    expect(appNodes[0].securityGroups).toEqual(['sg-0a1b2c3web00001'])
    expect(s.instances.some((i) => i.name === 'bastion' && i.type === 't3.micro')).toBe(true)

    // bucket created under its literal name (region from provider block)
    expect(s.s3Buckets.length).toBe(bkt0 + 1)
    const bucket = s.s3Buckets.find((b) => b.name === 'fixit-data-eu-west-1')
    expect(bucket).toBeTruthy()
    expect(bucket.region).toBe('eu-west-1')

    // SG created with its real name + both ingress rules (regex bridge only ever
    // produced a single hardcoded HTTP rule on "web-sg-tf")
    expect(s.securityGroups.length).toBe(sg0 + 1)
    const sg = s.securityGroups.find((g) => g.name === 'app-sg-tf')
    expect(sg).toBeTruthy()
    expect(sg.inbound.map((r) => r.from).sort()).toEqual([22, 443])
    expect(sg.inbound.find((r) => r.from === 22).source).toBe('10.0.0.0/8')

    // lab-managed ledger tracks the created resources for teardown
    const managed = s.labManagedIds
    expect(managed).toContain('bucket:fixit-data-eu-west-1')
    expect(managed).toContain('sg:app-sg-tf')
    expect(managed.filter((x) => x.startsWith('i-'))).toHaveLength(3)
  })

  it('does not duplicate resources on re-apply of an unchanged config', () => {
    syncTerraformApplyToAwsConsole(applied({ 'main.tf': MULTI_TF }))
    const afterFirst = useAwsStore.getState().instances.length
    syncTerraformApplyToAwsConsole(applied({ 'main.tf': MULTI_TF }))
    expect(useAwsStore.getState().instances.length).toBe(afterFirst)
    expect(useAwsStore.getState().s3Buckets.filter((b) => b.name === 'fixit-data-eu-west-1')).toHaveLength(1)
  })

  it('parses the default IDE template (multi-file) into a clean instance', () => {
    const inst0 = useAwsStore.getState().instances.length
    syncTerraformApplyToAwsConsole(applied({
      'main.tf': DEFAULT_IDE_MAIN_TF,
      'variables.tf': DEFAULT_IDE_VARIABLES_TF,
    }))
    const s = useAwsStore.getState()
    expect(s.instances.length).toBe(inst0 + 1)
    const web = s.instances.find((i) => i.name === 'web-server')
    expect(web).toBeTruthy()
    expect(web.type).toBe('t3.medium') // regex bridge would have shown a stale default
  })

  it('teardown removes lab-managed resources and re-enables a fresh apply', () => {
    syncTerraformApplyToAwsConsole(applied({ 'main.tf': MULTI_TF }))
    const s1 = useAwsStore.getState()
    expect(s1.instances.some((i) => i.name === 'bastion')).toBe(true)

    resetTerraformAwsLabState()
    const s2 = useAwsStore.getState()
    expect(s2.instances.some((i) => i.name === 'bastion')).toBe(false)
    expect(s2.s3Buckets.some((b) => b.name === 'fixit-data-eu-west-1')).toBe(false)
    expect(s2.securityGroups.some((g) => g.name === 'app-sg-tf')).toBe(false)

    // address ledger was cleared, so applying again re-creates the resources
    const inst0 = useAwsStore.getState().instances.length
    syncTerraformApplyToAwsConsole(applied({ 'main.tf': MULTI_TF }))
    expect(useAwsStore.getState().instances.length).toBe(inst0 + 3)
  })
})
