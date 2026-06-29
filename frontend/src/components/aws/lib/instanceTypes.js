// EC2 instance-type catalog. vCPU/memory/network used by the launch wizard,
// instance detail, lscpu/free/proc simulation, and hourly on-demand pricing
// (us-east-1 list prices, approximate) used by the cost estimate + billing.
export const INSTANCE_TYPES = [
  // Burstable T2
  { type: 't2.nano', family: 'General purpose', vcpu: 1, memGiB: 0.5, arch: 'x86_64', net: 'Low to Moderate', price: 0.0058, freeTier: false },
  { type: 't2.micro', family: 'General purpose', vcpu: 1, memGiB: 1, arch: 'x86_64', net: 'Low to Moderate', price: 0.0116, freeTier: true },
  { type: 't2.small', family: 'General purpose', vcpu: 1, memGiB: 2, arch: 'x86_64', net: 'Low to Moderate', price: 0.023, freeTier: false },
  { type: 't2.medium', family: 'General purpose', vcpu: 2, memGiB: 4, arch: 'x86_64', net: 'Low to Moderate', price: 0.0464, freeTier: false },
  { type: 't2.large', family: 'General purpose', vcpu: 2, memGiB: 8, arch: 'x86_64', net: 'Low to Moderate', price: 0.0928, freeTier: false },
  { type: 't2.xlarge', family: 'General purpose', vcpu: 4, memGiB: 16, arch: 'x86_64', net: 'Moderate', price: 0.1856, freeTier: false },
  { type: 't2.2xlarge', family: 'General purpose', vcpu: 8, memGiB: 32, arch: 'x86_64', net: 'Moderate', price: 0.3712, freeTier: false },
  // Burstable T3
  { type: 't3.micro', family: 'General purpose', vcpu: 2, memGiB: 1, arch: 'x86_64', net: 'Up to 5 Gigabit', price: 0.0104, freeTier: true },
  { type: 't3.small', family: 'General purpose', vcpu: 2, memGiB: 2, arch: 'x86_64', net: 'Up to 5 Gigabit', price: 0.0208, freeTier: false },
  { type: 't3.medium', family: 'General purpose', vcpu: 2, memGiB: 4, arch: 'x86_64', net: 'Up to 5 Gigabit', price: 0.0416, freeTier: false },
  { type: 't3.large', family: 'General purpose', vcpu: 2, memGiB: 8, arch: 'x86_64', net: 'Up to 5 Gigabit', price: 0.0832, freeTier: false },
  { type: 't3.xlarge', family: 'General purpose', vcpu: 4, memGiB: 16, arch: 'x86_64', net: 'Up to 5 Gigabit', price: 0.1664, freeTier: false },
  { type: 't3.2xlarge', family: 'General purpose', vcpu: 8, memGiB: 32, arch: 'x86_64', net: 'Up to 5 Gigabit', price: 0.3328, freeTier: false },
  // T4g (ARM)
  { type: 't4g.micro', family: 'General purpose', vcpu: 2, memGiB: 1, arch: 'arm64', net: 'Up to 5 Gigabit', price: 0.0084, freeTier: true },
  { type: 't4g.small', family: 'General purpose', vcpu: 2, memGiB: 2, arch: 'arm64', net: 'Up to 5 Gigabit', price: 0.0168, freeTier: false },
  { type: 't4g.medium', family: 'General purpose', vcpu: 2, memGiB: 4, arch: 'arm64', net: 'Up to 5 Gigabit', price: 0.0336, freeTier: false },
  { type: 't4g.large', family: 'General purpose', vcpu: 2, memGiB: 8, arch: 'arm64', net: 'Up to 5 Gigabit', price: 0.0672, freeTier: false },
  // M5
  { type: 'm5.large', family: 'General purpose', vcpu: 2, memGiB: 8, arch: 'x86_64', net: 'Up to 10 Gigabit', price: 0.096, freeTier: false },
  { type: 'm5.xlarge', family: 'General purpose', vcpu: 4, memGiB: 16, arch: 'x86_64', net: 'Up to 10 Gigabit', price: 0.192, freeTier: false },
  { type: 'm5.2xlarge', family: 'General purpose', vcpu: 8, memGiB: 32, arch: 'x86_64', net: 'Up to 10 Gigabit', price: 0.384, freeTier: false },
  { type: 'm5.4xlarge', family: 'General purpose', vcpu: 16, memGiB: 64, arch: 'x86_64', net: 'Up to 10 Gigabit', price: 0.768, freeTier: false },
  // M6g ARM
  { type: 'm6g.large', family: 'General purpose', vcpu: 2, memGiB: 8, arch: 'arm64', net: 'Up to 10 Gigabit', price: 0.077, freeTier: false },
  { type: 'm6g.xlarge', family: 'General purpose', vcpu: 4, memGiB: 16, arch: 'arm64', net: 'Up to 10 Gigabit', price: 0.154, freeTier: false },
  // C5 compute
  { type: 'c5.large', family: 'Compute optimized', vcpu: 2, memGiB: 4, arch: 'x86_64', net: 'Up to 10 Gigabit', price: 0.085, freeTier: false },
  { type: 'c5.xlarge', family: 'Compute optimized', vcpu: 4, memGiB: 8, arch: 'x86_64', net: 'Up to 10 Gigabit', price: 0.17, freeTier: false },
  { type: 'c5.2xlarge', family: 'Compute optimized', vcpu: 8, memGiB: 16, arch: 'x86_64', net: 'Up to 10 Gigabit', price: 0.34, freeTier: false },
  { type: 'c6i.large', family: 'Compute optimized', vcpu: 2, memGiB: 4, arch: 'x86_64', net: 'Up to 12.5 Gigabit', price: 0.085, freeTier: false },
  { type: 'c6i.xlarge', family: 'Compute optimized', vcpu: 4, memGiB: 8, arch: 'x86_64', net: 'Up to 12.5 Gigabit', price: 0.17, freeTier: false },
  // R5 memory
  { type: 'r5.large', family: 'Memory optimized', vcpu: 2, memGiB: 16, arch: 'x86_64', net: 'Up to 10 Gigabit', price: 0.126, freeTier: false },
  { type: 'r5.xlarge', family: 'Memory optimized', vcpu: 4, memGiB: 32, arch: 'x86_64', net: 'Up to 10 Gigabit', price: 0.252, freeTier: false },
  { type: 'r5.2xlarge', family: 'Memory optimized', vcpu: 8, memGiB: 64, arch: 'x86_64', net: 'Up to 10 Gigabit', price: 0.504, freeTier: false },
  { type: 'r6g.large', family: 'Memory optimized', vcpu: 2, memGiB: 16, arch: 'arm64', net: 'Up to 10 Gigabit', price: 0.1008, freeTier: false },
  // GPU
  { type: 'g4dn.xlarge', family: 'Accelerated computing', vcpu: 4, memGiB: 16, arch: 'x86_64', net: 'Up to 25 Gigabit', price: 0.526, freeTier: false },
  { type: 'p3.2xlarge', family: 'Accelerated computing', vcpu: 8, memGiB: 61, arch: 'x86_64', net: 'Up to 10 Gigabit', price: 3.06, freeTier: false },
  // Storage
  { type: 'i3.large', family: 'Storage optimized', vcpu: 2, memGiB: 15.25, arch: 'x86_64', net: 'Up to 10 Gigabit', price: 0.156, freeTier: false },
  { type: 'i3.xlarge', family: 'Storage optimized', vcpu: 4, memGiB: 30.5, arch: 'x86_64', net: 'Up to 10 Gigabit', price: 0.312, freeTier: false },
]

export const INSTANCE_FAMILIES = [
  'General purpose', 'Compute optimized', 'Memory optimized', 'Accelerated computing', 'Storage optimized',
]

export function getInstanceType(type) {
  return INSTANCE_TYPES.find((t) => t.type === type) || INSTANCE_TYPES[1]
}

// EBS volume type metadata for the storage step of the launch wizard.
export const VOLUME_TYPES = [
  { type: 'gp3', label: 'General Purpose SSD (gp3)', maxIops: 16000, price: 0.08 },
  { type: 'gp2', label: 'General Purpose SSD (gp2)', maxIops: 16000, price: 0.10 },
  { type: 'io1', label: 'Provisioned IOPS SSD (io1)', maxIops: 64000, price: 0.125 },
  { type: 'io2', label: 'Provisioned IOPS SSD (io2)', maxIops: 64000, price: 0.125 },
  { type: 'st1', label: 'Throughput Optimized HDD (st1)', maxIops: 500, price: 0.045 },
  { type: 'sc1', label: 'Cold HDD (sc1)', maxIops: 250, price: 0.015 },
  { type: 'standard', label: 'Magnetic (standard)', maxIops: 200, price: 0.05 },
]

// AMI catalog (Quick Start) — region-independent IDs for the simulation.
export const AMI_CATALOG = [
  { id: 'ami-0c02fb55956c7d316', name: 'Amazon Linux 2023 AMI', os: 'amazon-linux-2023', platform: 'Linux/UNIX', arch: 'x86_64', user: 'ec2-user', desc: 'Amazon Linux 2023 AMI 2023.x kernel-6.1 x86_64 HVM', freeTier: true },
  { id: 'ami-0a1b2c3d4amzn2', name: 'Amazon Linux 2 AMI', os: 'amazon-linux-2', platform: 'Linux/UNIX', arch: 'x86_64', user: 'ec2-user', desc: 'Amazon Linux 2 Kernel 5.10 HVM x86_64', freeTier: true },
  { id: 'ami-0557a15b87f6559cf', name: 'Ubuntu Server 22.04 LTS', os: 'ubuntu-22.04', platform: 'Ubuntu', arch: 'x86_64', user: 'ubuntu', desc: 'Canonical, Ubuntu, 22.04 LTS, amd64 jammy', freeTier: true },
  { id: 'ami-0e001c9271cf7f3b9', name: 'Ubuntu Server 24.04 LTS', os: 'ubuntu-24.04', platform: 'Ubuntu', arch: 'x86_64', user: 'ubuntu', desc: 'Canonical, Ubuntu, 24.04 LTS, amd64 noble', freeTier: true },
  { id: 'ami-026ebd4cfe2c043b2', name: 'Red Hat Enterprise Linux 9', os: 'rhel-9', platform: 'Red Hat', arch: 'x86_64', user: 'ec2-user', desc: 'RHEL-9 HVM x86_64 Hourly2', freeTier: false },
  { id: 'ami-0150ccaf51ab55a51', name: 'Debian 12 (Bookworm)', os: 'debian-12', platform: 'Debian', arch: 'x86_64', user: 'admin', desc: 'Debian 12 (20240xxx) amd64', freeTier: true },
  { id: 'ami-eks-worker-al2023', name: 'Amazon EKS Optimized AMI', os: 'amazon-linux-2023', platform: 'Linux/UNIX', arch: 'x86_64', user: 'ec2-user', desc: 'EKS worker node — kubectl, kubelet, containerd', freeTier: false, workload: 'kubernetes' },
  { id: 'ami-k8s-ubuntu2204', name: 'Ubuntu EKS / Kubernetes worker', os: 'ubuntu-22.04', platform: 'Ubuntu', arch: 'x86_64', user: 'ubuntu', desc: 'Kubernetes worker node on Ubuntu 22.04', freeTier: false, workload: 'kubernetes' },
  { id: 'ami-win2022-base', name: 'Microsoft Windows Server 2022 Base', os: 'windows-server-2022', platform: 'Windows', arch: 'x86_64', user: 'Administrator', desc: 'Windows Server 2022 Full Locale English Base', freeTier: false, workload: 'windows' },
  { id: 'ami-win2019-base', name: 'Microsoft Windows Server 2019 Base', os: 'windows-server-2019', platform: 'Windows', arch: 'x86_64', user: 'Administrator', desc: 'Windows Server 2019 Full Locale English Base', freeTier: false, workload: 'windows' },
]

export function getAmi(id) {
  return AMI_CATALOG.find((a) => a.id === id) || AMI_CATALOG[0]
}
