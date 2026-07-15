import { describe, it, expect, beforeEach } from 'vitest'
import { createTerraform } from './terraformSim.js'
import { useAwsStore } from '../store/awsStore'

// Same config the bridge test uses — proves the terminal `terraform apply` path
// and the IDE bridge now produce the same resources from the shared tokenizer.
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

function makeTerraform(mainTf) {
  const files = { '/root/main.tf': mainTf }
  return createTerraform({
    store: useAwsStore.getState(),
    readFile: (path) => files[path] || null,
    getCwd: () => '/root',
    region: 'us-east-1',
  })
}

beforeEach(() => {
  useAwsStore.getState().resetSimulation()
})

describe('terraformSim terminal apply (shared tokenizer)', () => {
  it('applies every resource with tokenizer-parsed values', () => {
    const s0 = useAwsStore.getState()
    const inst0 = s0.instances.length
    const bkt0 = s0.s3Buckets.length
    const sg0 = s0.securityGroups.length

    const tf = makeTerraform(MULTI_TF)
    const out = tf.run(['apply']).join('\n')
    expect(out).toMatch(/Apply complete!/)

    const s = useAwsStore.getState()
    expect(s.instances.length).toBe(inst0 + 3) // count=2 web + bastion
    const appNodes = s.instances.filter((i) => i.name === 'app-node')
    expect(appNodes).toHaveLength(2)
    expect(appNodes[0].type).toBe('t3.large') // var.web_type resolved
    expect(appNodes[0].keyName).toBe('production-key')
    expect(appNodes[0].securityGroups).toEqual(['sg-0a1b2c3web00001'])

    expect(s.s3Buckets.length).toBe(bkt0 + 1)
    expect(s.s3Buckets.find((b) => b.name === 'fixit-data-eu-west-1').region).toBe('eu-west-1')

    expect(s.securityGroups.length).toBe(sg0 + 1)
    const sg = s.securityGroups.find((g) => g.name === 'app-sg-tf')
    expect(sg.inbound.map((r) => r.from).sort()).toEqual([22, 443])
  })

  it('is idempotent within a session (apply ledger prevents re-creation)', () => {
    const tf = makeTerraform(MULTI_TF)
    tf.run(['apply'])
    const afterFirst = useAwsStore.getState().instances.length
    const out = tf.run(['apply']).join('\n')
    expect(out).toMatch(/No changes\./)
    expect(useAwsStore.getState().instances.length).toBe(afterFirst)
  })
})
