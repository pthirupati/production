# FixitLab — Complete AWS Infrastructure with Terraform
# EKS cluster, RDS PostgreSQL, ElastiCache Redis, ECR, S3, CloudFront

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "fixitlab-terraform-state"
    key    = "infrastructure/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}

# ──── Variables ─────────────────────────────────────────────

variable "aws_region" {
  default = "us-east-1"
}

variable "environment" {
  default = "production"
}

variable "cluster_name" {
  default = "fixitlab-eks"
}

variable "db_instance_class" {
  default = "db.r6g.large"
}

variable "domain_name" {
  default = "fixitlab.in"
}

# ──── VPC ───────────────────────────────────────────────────

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "fixitlab-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway   = true
  single_nat_gateway   = false
  enable_dns_hostnames = true
  enable_dns_support   = true

  public_subnet_tags = {
    "kubernetes.io/role/elb"                      = "1"
    "kubernetes.io/cluster/${var.cluster_name}"    = "owned"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb"              = "1"
    "kubernetes.io/cluster/${var.cluster_name}"    = "owned"
  }

  tags = {
    Environment = var.environment
    Project     = "fixitlab"
  }
}

# ──── EKS Cluster ───────────────────────────────────────────

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = "1.29"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access = true

  eks_managed_node_groups = {
    # Application nodes — handle API, WebSocket, frontend
    app = {
      min_size     = 5
      max_size     = 50
      desired_size = 5
      instance_types = ["m5.xlarge"]
      capacity_type  = "ON_DEMAND"

      labels = { role = "app" }
    }

    # Lab runner nodes (larger, for Docker containers)
    # Each m5.2xlarge (32GB RAM, 8 vCPU) can run ~60 labs (512MB each)
    # 200 nodes × 60 labs = 12,000 concurrent labs
    # For 10L registered users, ~5-10% concurrent = 50K-100K labs
    lab_runners = {
      min_size     = 5
      max_size     = 200
      desired_size = 10
      instance_types = ["m5.2xlarge", "m5.xlarge"]
      capacity_type  = "SPOT"

      labels = { role = "lab-runner" }

      taints = [{
        key    = "workload"
        value  = "lab"
        effect = "NO_SCHEDULE"
      }]
    }
  }

  tags = {
    Environment = var.environment
    Project     = "fixitlab"
  }
}

# ──── RDS PostgreSQL ────────────────────────────────────────

resource "aws_db_subnet_group" "fixitlab" {
  name       = "fixitlab-db-subnet"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "rds" {
  name_prefix = "fixitlab-rds-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
}

resource "aws_rds_cluster" "fixitlab" {
  cluster_identifier = "fixitlab-db"
  engine             = "aurora-postgresql"
  engine_version     = "15.4"
  database_name      = "fixitlab"
  master_username    = "fixitlab"
  master_password    = "change-me-use-secrets-manager"

  db_subnet_group_name   = aws_db_subnet_group.fixitlab.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  backup_retention_period = 7
  preferred_backup_window = "03:00-04:00"
  skip_final_snapshot     = false
  final_snapshot_identifier = "fixitlab-final"

  tags = {
    Environment = var.environment
    Project     = "fixitlab"
  }
}

resource "aws_rds_cluster_instance" "fixitlab" {
  count              = 2
  identifier         = "fixitlab-db-${count.index}"
  cluster_identifier = aws_rds_cluster.fixitlab.id
  instance_class     = var.db_instance_class
  engine             = aws_rds_cluster.fixitlab.engine
}

# ──── ElastiCache Redis ─────────────────────────────────────

resource "aws_security_group" "redis" {
  name_prefix = "fixitlab-redis-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
}

resource "aws_elasticache_subnet_group" "fixitlab" {
  name       = "fixitlab-redis"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_elasticache_replication_group" "fixitlab" {
  replication_group_id = "fixitlab-redis"
  description          = "FixitLab Redis cluster"
  node_type            = "cache.r6g.large"
  num_cache_clusters   = 2
  engine_version       = "7.0"

  subnet_group_name  = aws_elasticache_subnet_group.fixitlab.name
  security_group_ids = [aws_security_group.redis.id]

  automatic_failover_enabled = true
  multi_az_enabled           = true

  tags = {
    Environment = var.environment
    Project     = "fixitlab"
  }
}

# ──── ECR Repositories ──────────────────────────────────────

resource "aws_ecr_repository" "backend" {
  name                 = "fixitlab/backend"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration { scan_on_push = true }
}

resource "aws_ecr_repository" "frontend" {
  name                 = "fixitlab/frontend"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration { scan_on_push = true }
}

# ──── S3 for static assets ──────────────────────────────────

resource "aws_s3_bucket" "static" {
  bucket = "fixitlab-static-assets"
}

resource "aws_s3_bucket_public_access_block" "static" {
  bucket                  = aws_s3_bucket.static.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ──── CloudFront CDN ────────────────────────────────────────

resource "aws_cloudfront_distribution" "fixitlab" {
  enabled             = true
  default_root_object = "index.html"
  aliases             = [var.domain_name, "www.${var.domain_name}"]

  origin {
    domain_name = aws_s3_bucket.static.bucket_regional_domain_name
    origin_id   = "S3-static"

    s3_origin_config {
      origin_access_identity = ""
    }
  }

  default_cache_behavior {
    target_origin_id       = "S3-static"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 86400
    max_ttl     = 31536000
    compress    = true
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    acm_certificate_arn      = "arn:aws:acm:us-east-1:ACCOUNT:certificate/CERT-ID"
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = {
    Environment = var.environment
    Project     = "fixitlab"
  }
}

# ──── Outputs ───────────────────────────────────────────────

output "eks_cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "rds_endpoint" {
  value = aws_rds_cluster.fixitlab.endpoint
}

output "redis_endpoint" {
  value = aws_elasticache_replication_group.fixitlab.primary_endpoint_address
}

output "ecr_backend_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_url" {
  value = aws_ecr_repository.frontend.repository_url
}

output "cloudfront_domain" {
  value = aws_cloudfront_distribution.fixitlab.domain_name
}
