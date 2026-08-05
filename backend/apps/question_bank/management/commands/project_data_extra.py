"""Auto-generated guided projects for technologies that lacked them.

Authored to satisfy the >=5-projects-per-technology guarantee
(see tests/test_seed_projects.py). Imported and appended by seed_projects.py."""

EXTRA_PROJECTS = [{'technology_slug': 'aws',
  'title': 'Build a Secure VPC Network Foundation',
  'slug': 'aws-vpc-network-foundation',
  'architecture_type': 'custom',
  'description': 'Design and build a production-style Virtual Private Cloud from scratch: a custom VPC, '
                 'public and private subnets across two Availability Zones, an Internet Gateway, route '
                 'tables, and least-privilege security groups. This is the networking foundation that every '
                 'later AWS project deploys into.',
  'objectives': ['Create a custom VPC with a planned CIDR block and DNS support enabled',
                 'Segment the network into public and private subnets across two Availability Zones',
                 'Wire up an Internet Gateway and route tables so public subnets reach the internet',
                 'Author least-privilege security groups for web and database tiers',
                 'Verify network reachability and isolation using the AWS CLI and Reachability Analyzer'],
  'difficulty': 'beginner',
  'estimated_hours': 3,
  'order': 1,
  'tasks': [{'jira_key': 'AWSVPC-1',
             'title': 'Create the VPC with a planned CIDR block',
             'description': 'Create a custom VPC named fixitlab-vpc with CIDR 10.0.0.0/16 and enable DNS '
                            'hostnames and DNS resolution so instances get resolvable private DNS names.',
             'acceptance_criteria': 'A VPC exists with CIDR 10.0.0.0/16; `aws ec2 describe-vpcs` shows '
                                    'EnableDnsHostnames and EnableDnsSupport both true.',
             'hint': 'Run `aws ec2 create-vpc --cidr-block 10.0.0.0/16 --tag-specifications '
                     "'ResourceType=vpc,Tags=[{Key=Name,Value=fixitlab-vpc}]'`, then `aws ec2 "
                     'modify-vpc-attribute --vpc-id <id> --enable-dns-hostnames` (and again with '
                     '--enable-dns-support).',
             'order': 1},
            {'jira_key': 'AWSVPC-2',
             'title': 'Create public and private subnets in two AZs',
             'description': 'Carve four /24 subnets: public-a (10.0.0.0/24) and public-b (10.0.1.0/24) in '
                            'two Availability Zones, plus private-a (10.0.10.0/24) and private-b '
                            '(10.0.11.0/24). Enable auto-assign public IP on the public subnets only.',
             'acceptance_criteria': 'Four subnets exist across two distinct AZs; the two public subnets have '
                                    'MapPublicIpOnLaunch=true and the two private subnets have it false.',
             'hint': 'Use `aws ec2 create-subnet --vpc-id <id> --cidr-block 10.0.0.0/24 --availability-zone '
                     'us-east-1a` per subnet, then `aws ec2 modify-subnet-attribute --subnet-id <id> '
                     '--map-public-ip-on-launch` on the public ones only.',
             'order': 2,
             'depends_on': 'AWSVPC-1'},
            {'jira_key': 'AWSVPC-3',
             'title': 'Attach an Internet Gateway',
             'description': 'Create an Internet Gateway and attach it to fixitlab-vpc so resources in public '
                            'subnets can send and receive traffic to the internet.',
             'acceptance_criteria': '`aws ec2 describe-internet-gateways` shows the IGW attached to the VPC '
                                    "with state 'available'.",
             'hint': 'Run `aws ec2 create-internet-gateway`, then `aws ec2 attach-internet-gateway '
                     '--internet-gateway-id <igw> --vpc-id <vpc>`.',
             'order': 3,
             'depends_on': 'AWSVPC-1'},
            {'jira_key': 'AWSVPC-4',
             'title': 'Configure route tables for public subnets',
             'description': 'Create a public route table with a default route (0.0.0.0/0) to the Internet '
                            'Gateway and associate it with both public subnets. Leave the private subnets on '
                            "the VPC's local-only main route table.",
             'acceptance_criteria': 'The public route table has a 0.0.0.0/0 route targeting the IGW and is '
                                    'associated with public-a and public-b; private subnets have no internet '
                                    'route.',
             'hint': '`aws ec2 create-route-table --vpc-id <vpc>`, then `aws ec2 create-route '
                     '--route-table-id <rtb> --destination-cidr-block 0.0.0.0/0 --gateway-id <igw>`, then '
                     '`associate-route-table` for each public subnet.',
             'order': 4,
             'depends_on': 'AWSVPC-3'},
            {'jira_key': 'AWSVPC-5',
             'title': 'Author least-privilege security groups',
             'description': 'Create a web-sg allowing inbound HTTP (80) and HTTPS (443) from 0.0.0.0/0 and '
                            'SSH (22) only from your admin IP. Create a db-sg allowing inbound PostgreSQL '
                            '(5432) only from web-sg as the source, not from a CIDR.',
             'acceptance_criteria': 'web-sg allows 80/443 from anywhere and 22 from a single /32; db-sg '
                                    'allows 5432 only when the source is the web-sg security group ID.',
             'hint': 'Use `aws ec2 authorize-security-group-ingress --group-id <db-sg> --protocol tcp --port '
                     '5432 --source-group <web-sg>` so the DB rule references the web SG instead of a CIDR.',
             'order': 5,
             'depends_on': 'AWSVPC-1'},
            {'jira_key': 'AWSVPC-6',
             'title': 'Verify reachability and isolation',
             'description': 'Confirm the design works: a resource in a public subnet can reach the internet, '
                            'and the private subnets remain isolated. Use VPC Reachability Analyzer or '
                            'route/security-group inspection to prove the paths.',
             'acceptance_criteria': 'Documented evidence that public subnets route to 0.0.0.0/0 via the IGW '
                                    'and private subnets have no internet route; security group rules match '
                                    'the least-privilege spec.',
             'hint': 'Create a Reachability Analyzer path from an IGW to a public subnet ENI with `aws ec2 '
                     'create-network-insights-path`, then `start-network-insights-analysis`, or inspect '
                     'routes with `aws ec2 describe-route-tables`.',
             'order': 6,
             'depends_on': 'AWSVPC-4'}]},
 {'technology_slug': 'aws',
  'title': 'Host a Static Website on S3 with CloudFront CDN',
  'slug': 'aws-s3-static-site-cloudfront',
  'architecture_type': 'custom',
  'description': 'Publish a static website using an S3 bucket as the origin and Amazon CloudFront as a '
                 'global CDN in front of it. You will keep the bucket private, serve it only through '
                 'CloudFront using Origin Access Control, and enforce HTTPS with cache invalidation on '
                 'deploys.',
  'objectives': ['Create and configure an S3 bucket to store static website assets',
                 'Keep the bucket private and serve it exclusively through CloudFront using Origin Access '
                 'Control',
                 'Distribute content globally over HTTPS with a CloudFront distribution',
                 'Set an index and error document and cache-control behavior',
                 'Invalidate the CDN cache to push a content update live'],
  'difficulty': 'beginner',
  'estimated_hours': 3,
  'order': 2,
  'tasks': [{'jira_key': 'AWSS3-1',
             'title': 'Create the origin S3 bucket',
             'description': 'Create a uniquely named S3 bucket (e.g. fixitlab-site-<random>) in your region '
                            'to hold the site assets. Leave Block Public Access fully enabled — the bucket '
                            'must stay private.',
             'acceptance_criteria': 'The bucket exists and `aws s3api get-public-access-block` shows all '
                                    'four block-public-access settings are true.',
             'hint': 'Create with `aws s3api create-bucket --bucket fixitlab-site-<rand> --region '
                     'us-east-1`. Bucket names are globally unique; append random characters if it collides.',
             'order': 1},
            {'jira_key': 'AWSS3-2',
             'title': 'Upload the static site content',
             'description': 'Upload an index.html and error.html (plus any css/js assets) to the bucket, '
                            'preserving the correct Content-Type on each object so browsers render HTML '
                            'instead of downloading it.',
             'acceptance_criteria': '`aws s3 ls s3://<bucket>/` lists index.html and error.html; '
                                    '`head-object` shows ContentType text/html on the HTML files.',
             'hint': 'Use `aws s3 sync ./site s3://<bucket>/` — the CLI infers Content-Type from file '
                     'extensions. Verify with `aws s3api head-object --bucket <bucket> --key index.html`.',
             'order': 2,
             'depends_on': 'AWSS3-1'},
            {'jira_key': 'AWSS3-3',
             'title': 'Create a CloudFront distribution with Origin Access Control',
             'description': 'Create a CloudFront distribution using the S3 bucket as the origin. Attach an '
                            'Origin Access Control (OAC) so CloudFront signs requests to S3, and set '
                            'index.html as the default root object.',
             'acceptance_criteria': 'A distribution exists with the S3 bucket as origin, an OAC attached, '
                                    "and DefaultRootObject set to index.html; status becomes 'Deployed'.",
             'hint': 'Create an OAC with `aws cloudfront create-origin-access-control`, then reference its '
                     'ID in the distribution config passed to `aws cloudfront create-distribution '
                     '--distribution-config file://dist.json`.',
             'order': 3,
             'depends_on': 'AWSS3-2'},
            {'jira_key': 'AWSS3-4',
             'title': 'Lock the bucket policy to CloudFront only',
             'description': 'Attach an S3 bucket policy that allows s3:GetObject only from the CloudFront '
                            'service principal, restricted via aws:SourceArn to your specific distribution. '
                            'Confirm direct S3 URL access is denied.',
             'acceptance_criteria': 'Fetching an object via the direct S3 URL returns 403 Access Denied, '
                                    'while fetching it through the CloudFront domain returns 200.',
             'hint': 'The policy Principal is `{"Service":"cloudfront.amazonaws.com"}` with a Condition on '
                     '`AWS:SourceArn` equal to the distribution ARN. Apply with `aws s3api '
                     'put-bucket-policy`.',
             'order': 4,
             'depends_on': 'AWSS3-3'},
            {'jira_key': 'AWSS3-5',
             'title': 'Enforce HTTPS and set the error document',
             'description': "Configure the distribution's default cache behavior to redirect HTTP to HTTPS "
                            '(ViewerProtocolPolicy redirect-to-https) and add a custom error response '
                            'mapping 403/404 to error.html with a 200 response for SPA-style routing.',
             'acceptance_criteria': 'Requests over http:// redirect to https://; requesting a missing path '
                                    'returns the error.html content.',
             'hint': 'Set `ViewerProtocolPolicy: redirect-to-https` in the default cache behavior and add a '
                     'CustomErrorResponse (ErrorCode 404, ResponsePagePath /error.html) via `aws cloudfront '
                     'update-distribution`.',
             'order': 5,
             'depends_on': 'AWSS3-3'},
            {'jira_key': 'AWSS3-6',
             'title': 'Deploy an update and invalidate the cache',
             'description': 'Change index.html, re-sync it to S3, then create a CloudFront invalidation so '
                            'edge caches serve the new version instead of the stale cached copy.',
             'acceptance_criteria': 'After the invalidation completes, loading the CloudFront URL shows the '
                                    'updated content, not the old cached page.',
             'hint': 'Re-run `aws s3 sync`, then `aws cloudfront create-invalidation --distribution-id <id> '
                     "--paths '/*'`. Poll status with `get-invalidation` until it is 'Completed'.",
             'order': 6,
             'depends_on': 'AWSS3-4'}]},
 {'technology_slug': 'aws',
  'title': 'Deploy an EC2 Web Application in Your VPC',
  'slug': 'aws-ec2-web-app-2tier',
  'architecture_type': '2tier',
  'description': 'Launch and configure an EC2 web server inside the VPC you built earlier, forming a 2-tier '
                 'setup: a public-facing web instance backed by an Elastic IP. You will bootstrap the app '
                 'with user data, attach an IAM instance role for secure S3 access, and verify the app is '
                 'reachable over HTTP.',
  'objectives': ['Launch an EC2 instance into a public subnet with the correct security group',
                 'Bootstrap a web application automatically at boot using EC2 user data',
                 'Attach an IAM instance profile so the app reaches S3 without hardcoded keys',
                 'Assign a stable Elastic IP and connect using SSH key pairs',
                 'Verify the running application over HTTP from the public internet'],
  'difficulty': 'intermediate',
  'estimated_hours': 4,
  'order': 3,
  'tasks': [{'jira_key': 'AWSEC2-1',
             'title': 'Create an SSH key pair',
             'description': 'Create an EC2 key pair named fixitlab-key and save the private key locally with '
                            'correct permissions so you can SSH into the instance.',
             'acceptance_criteria': '`aws ec2 describe-key-pairs` lists fixitlab-key; the local .pem file '
                                    'exists with 400 permissions.',
             'hint': "Run `aws ec2 create-key-pair --key-name fixitlab-key --query 'KeyMaterial' --output "
                     'text > fixitlab-key.pem` then `chmod 400 fixitlab-key.pem`.',
             'order': 1},
            {'jira_key': 'AWSEC2-2',
             'title': 'Create an IAM role and instance profile for S3 read access',
             'description': 'Create an IAM role that EC2 can assume (trust policy for ec2.amazonaws.com), '
                            'attach a policy granting read-only access to your site S3 bucket, and wrap it '
                            'in an instance profile.',
             'acceptance_criteria': 'An instance profile exists containing a role whose attached policy '
                                    'allows s3:GetObject/s3:ListBucket on the target bucket only.',
             'hint': 'Create the role with an assume-role trust policy, attach a scoped policy (or '
                     'AmazonS3ReadOnlyAccess for a start), then `aws iam create-instance-profile` and '
                     '`add-role-to-instance-profile`.',
             'order': 2},
            {'jira_key': 'AWSEC2-3',
             'title': 'Launch the EC2 instance with user data',
             'description': 'Launch a t3.micro Amazon Linux 2023 instance into the public-a subnet, using '
                            'web-sg, the fixitlab-key key pair, and the instance profile from AWSEC2-2. Pass '
                            'user data that installs and starts a web server serving a simple page.',
             'acceptance_criteria': "The instance reaches 'running', has the instance profile attached, and "
                                    'the user-data-installed web server is listening on port 80.',
             'hint': 'Use `aws ec2 run-instances --image-id <al2023-ami> --instance-type t3.micro '
                     '--subnet-id <public-a> --security-group-ids <web-sg> --iam-instance-profile '
                     'Name=<profile> --user-data file://bootstrap.sh`.',
             'order': 3,
             'depends_on': 'AWSEC2-2'},
            {'jira_key': 'AWSEC2-4',
             'title': 'Allocate and associate an Elastic IP',
             'description': 'Allocate an Elastic IP and associate it with the instance so its public address '
                            'stays stable across stops and starts.',
             'acceptance_criteria': 'The instance has an associated Elastic IP; `aws ec2 describe-addresses` '
                                    'shows the EIP bound to the instance ID.',
             'hint': 'Run `aws ec2 allocate-address --domain vpc`, then `aws ec2 associate-address '
                     '--instance-id <id> --allocation-id <alloc>`.',
             'order': 4,
             'depends_on': 'AWSEC2-3'},
            {'jira_key': 'AWSEC2-5',
             'title': 'Verify SSH access and app health',
             'description': 'SSH into the instance using the key pair and confirm the web server process is '
                            'running and healthy. Check the app can list the S3 bucket using the instance '
                            'role — no access keys configured.',
             'acceptance_criteria': 'SSH succeeds; the web server is active; `aws s3 ls s3://<bucket>` run '
                                    'from the instance works using only the instance role credentials.',
             'hint': '`ssh -i fixitlab-key.pem ec2-user@<eip>`. On the box run `systemctl status httpd` (or '
                     'nginx) and `aws s3 ls s3://<bucket>` to prove the role works without `aws configure`.',
             'order': 5,
             'depends_on': 'AWSEC2-4'},
            {'jira_key': 'AWSEC2-6',
             'title': 'Confirm public HTTP reachability',
             'description': 'From your own machine, request the app over HTTP using the Elastic IP and '
                            'confirm the bootstrapped page is served, proving the full public path through '
                            'the security group and route table works.',
             'acceptance_criteria': '`curl http://<eip>/` returns HTTP 200 with the expected page content '
                                    'from any external network.',
             'hint': 'Run `curl -v http://<eip>/`. If it hangs, check web-sg allows 80 inbound and the '
                     'public subnet route table points 0.0.0.0/0 at the IGW.',
             'order': 6,
             'depends_on': 'AWSEC2-4'}]},
 {'technology_slug': 'aws',
  'title': 'Add a Managed RDS Database Behind Your App',
  'slug': 'aws-rds-app-3tier',
  'architecture_type': '3tier',
  'description': 'Extend the 2-tier setup into a 3-tier architecture by adding a managed Amazon RDS '
                 'PostgreSQL database in the private subnets. You will place RDS in a private DB subnet '
                 "group, lock it to the web tier's security group, store credentials in Secrets Manager, and "
                 'connect the app to persist data.',
  'objectives': ['Create a DB subnet group spanning the private subnets in two AZs',
                 'Provision a managed RDS PostgreSQL instance that is not publicly accessible',
                 'Restrict database access to the web tier using security group references',
                 'Store and retrieve database credentials with AWS Secrets Manager',
                 'Connect the application to RDS and verify data persistence end to end'],
  'difficulty': 'intermediate',
  'estimated_hours': 5,
  'order': 4,
  'tasks': [{'jira_key': 'AWSRDS-1',
             'title': 'Create a DB subnet group in the private subnets',
             'description': 'Create an RDS DB subnet group named fixitlab-db-subnets containing private-a '
                            'and private-b so RDS can place its instance across two Availability Zones with '
                            'no public exposure.',
             'acceptance_criteria': '`aws rds describe-db-subnet-groups` shows fixitlab-db-subnets '
                                    'containing both private subnet IDs across two distinct AZs.',
             'hint': 'Run `aws rds create-db-subnet-group --db-subnet-group-name fixitlab-db-subnets '
                     "--db-subnet-group-description 'private db subnets' --subnet-ids <private-a> "
                     '<private-b>`.',
             'order': 1},
            {'jira_key': 'AWSRDS-2',
             'title': 'Store the DB credentials in Secrets Manager',
             'description': 'Create a secret in AWS Secrets Manager holding the database username and a '
                            'strong password, so the app never hardcodes credentials and they can be rotated '
                            'later.',
             'acceptance_criteria': 'A secret exists whose JSON value contains username and password keys; '
                                    '`aws secretsmanager get-secret-value` returns them.',
             'hint': 'Use `aws secretsmanager create-secret --name fixitlab/db --secret-string '
                     '\'{"username":"appuser","password":"<strong-pass>"}\'`.',
             'order': 2},
            {'jira_key': 'AWSRDS-3',
             'title': 'Provision the RDS PostgreSQL instance',
             'description': 'Create a db.t3.micro PostgreSQL RDS instance using the DB subnet group and the '
                            'db-sg security group. Set PubliclyAccessible to false and enable storage '
                            'encryption and automated backups.',
             'acceptance_criteria': "The RDS instance reaches 'available', has PubliclyAccessible=false, is "
                                    'in the private subnet group, and has StorageEncrypted=true.',
             'hint': 'Run `aws rds create-db-instance --db-instance-identifier fixitlab-db --engine postgres '
                     '--db-instance-class db.t3.micro --allocated-storage 20 --db-subnet-group-name '
                     'fixitlab-db-subnets --vpc-security-group-ids <db-sg> --no-publicly-accessible '
                     '--storage-encrypted --master-username appuser --master-user-password <pass>`.',
             'order': 3,
             'depends_on': 'AWSRDS-1'},
            {'jira_key': 'AWSRDS-4',
             'title': 'Restrict the DB security group to the web tier',
             'description': 'Confirm db-sg permits inbound 5432 only from web-sg (as a source security '
                            'group, not a CIDR), so only application instances can reach the database and '
                            'nothing on the internet can.',
             'acceptance_criteria': 'db-sg inbound rules show port 5432 sourced from the web-sg group ID and '
                                    'no 0.0.0.0/0 rule for the database port.',
             'hint': 'Inspect with `aws ec2 describe-security-groups --group-ids <db-sg>`. If missing, add '
                     '`authorize-security-group-ingress --source-group <web-sg> --protocol tcp --port 5432`.',
             'order': 4,
             'depends_on': 'AWSRDS-3'},
            {'jira_key': 'AWSRDS-5',
             'title': 'Connect the app to RDS and create the schema',
             'description': 'From the EC2 app instance, fetch the credentials from Secrets Manager and the '
                            'RDS endpoint, then connect with psql and create the application table the app '
                            'writes to.',
             'acceptance_criteria': "`psql -h <rds-endpoint> -U appuser -d appdb -c '\\dt'` from the app "
                                    'instance lists the created table; connections from outside the VPC time '
                                    'out.',
             'hint': 'On the instance: `aws secretsmanager get-secret-value --secret-id fixitlab/db` to read '
                     'creds, then `PGPASSWORD=... psql -h <endpoint> -U appuser -d appdb`. The RDS endpoint '
                     'comes from `describe-db-instances`.',
             'order': 5,
             'depends_on': 'AWSRDS-4'},
            {'jira_key': 'AWSRDS-6',
             'title': 'Verify end-to-end data persistence',
             'description': 'Exercise the full 3-tier path: POST data through the web app so it writes to '
                            'RDS, then GET it back and confirm it survives an app instance restart, proving '
                            'state lives in the database, not the instance.',
             'acceptance_criteria': 'Data written via the app is readable after the EC2 instance is '
                                    'rebooted, confirming persistence in RDS rather than local storage.',
             'hint': "`curl -X POST http://<eip>/data -d '...'`, reboot the instance with `aws ec2 "
                     'reboot-instances`, then `curl http://<eip>/data` and confirm the record is still '
                     'returned.',
             'order': 6,
             'depends_on': 'AWSRDS-5'}]},
 {'technology_slug': 'aws',
  'title': 'Auto-Scaling Web Tier Behind an Application Load Balancer',
  'slug': 'aws-autoscaling-elb-3tier',
  'architecture_type': '3tier',
  'description': 'Turn the single EC2 web server into a resilient, self-healing tier: a launch template, an '
                 'Auto Scaling Group across two Availability Zones, and an Application Load Balancer '
                 'distributing traffic with health checks. You will configure target-tracking scaling '
                 'policies and prove the system heals and scales under load.',
  'objectives': ['Capture the web server configuration into a reusable EC2 launch template',
                 'Create an Application Load Balancer with a target group and health checks',
                 'Run an Auto Scaling Group across two AZs registered to the load balancer',
                 'Configure target-tracking scaling policies driven by CPU utilization',
                 'Validate self-healing on instance failure and scale-out under simulated load'],
  'difficulty': 'advanced',
  'estimated_hours': 6,
  'order': 5,
  'tasks': [{'jira_key': 'AWSASG-1',
             'title': 'Create a launch template for the web tier',
             'description': 'Create an EC2 launch template capturing the AMI, t3.micro instance type, '
                            'web-sg, IAM instance profile, and the user data that bootstraps the app, so '
                            'every scaled instance is identical.',
             'acceptance_criteria': '`aws ec2 describe-launch-template-versions` shows a template with the '
                                    'correct AMI, instance type, security group, instance profile, and '
                                    'base64 user data.',
             'hint': 'Use `aws ec2 create-launch-template --launch-template-name fixitlab-web-lt '
                     "--launch-template-data '{...}'` embedding ImageId, InstanceType, SecurityGroupIds, "
                     'IamInstanceProfile, and base64-encoded UserData.',
             'order': 1},
            {'jira_key': 'AWSASG-2',
             'title': 'Create the target group with health checks',
             'description': 'Create an ALB target group of type instance on port 80 in the VPC, with an HTTP '
                            'health check hitting /health, healthy threshold 2 and interval 15s, so the ALB '
                            'only routes to healthy instances.',
             'acceptance_criteria': '`aws elbv2 describe-target-groups` shows a target group on port 80 with '
                                    'HealthCheckPath /health and the configured thresholds.',
             'hint': 'Run `aws elbv2 create-target-group --name fixitlab-tg --protocol HTTP --port 80 '
                     '--vpc-id <vpc> --health-check-path /health --healthy-threshold-count 2 '
                     '--health-check-interval-seconds 15`.',
             'order': 2},
            {'jira_key': 'AWSASG-3',
             'title': 'Create the Application Load Balancer and listener',
             'description': 'Create an internet-facing Application Load Balancer spanning both public '
                            'subnets, using a security group that allows inbound 80, and add an HTTP:80 '
                            'listener that forwards to the target group.',
             'acceptance_criteria': "The ALB is 'active' across two public subnets and its listener forwards "
                                    'port 80 traffic to the target group; the ALB DNS name resolves.',
             'hint': '`aws elbv2 create-load-balancer --name fixitlab-alb --subnets <public-a> <public-b> '
                     '--security-groups <alb-sg> --scheme internet-facing`, then `create-listener --protocol '
                     'HTTP --port 80 --default-actions Type=forward,TargetGroupArn=<tg>`.',
             'order': 3,
             'depends_on': 'AWSASG-2'},
            {'jira_key': 'AWSASG-4',
             'title': 'Create the Auto Scaling Group across two AZs',
             'description': 'Create an Auto Scaling Group using the launch template, spanning private-a and '
                            'private-b (or public subnets), with min 2, desired 2, max 4, attached to the '
                            'ALB target group and using ELB health checks.',
             'acceptance_criteria': 'The ASG launches 2 instances across two AZs, registers them in the '
                                    'target group, and they pass ELB health checks (Healthy in the target '
                                    'group).',
             'hint': '`aws autoscaling create-auto-scaling-group --auto-scaling-group-name fixitlab-asg '
                     '--launch-template LaunchTemplateName=fixitlab-web-lt --min-size 2 --max-size 4 '
                     "--desired-capacity 2 --vpc-zone-identifier '<subnet-a>,<subnet-b>' --target-group-arns "
                     '<tg> --health-check-type ELB`.',
             'order': 4,
             'depends_on': 'AWSASG-3'},
            {'jira_key': 'AWSASG-5',
             'title': 'Add a target-tracking scaling policy',
             'description': 'Attach a target-tracking scaling policy that keeps average CPU utilization at '
                            '50%, so the group scales out toward max under load and back in when idle.',
             'acceptance_criteria': '`aws autoscaling describe-policies` shows a TargetTrackingScaling '
                                    'policy on ASGAverageCPUUtilization with a target value of 50.',
             'hint': 'Run `aws autoscaling put-scaling-policy --auto-scaling-group-name fixitlab-asg '
                     '--policy-name cpu50 --policy-type TargetTrackingScaling '
                     '--target-tracking-configuration '
                     '\'{"PredefinedMetricSpecification":{"PredefinedMetricType":"ASGAverageCPUUtilization"},"TargetValue":50}\'`.',
             'order': 5,
             'depends_on': 'AWSASG-4'},
            {'jira_key': 'AWSASG-6',
             'title': 'Validate self-healing and scale-out',
             'description': 'Prove resilience: terminate one instance and confirm the ASG replaces it and '
                            'the ALB keeps serving traffic; then drive CPU load and confirm the group scales '
                            'out toward its maximum.',
             'acceptance_criteria': 'After terminating an instance, the ASG restores desired capacity and '
                                    'the ALB DNS keeps returning 200; under sustained load the group '
                                    'launches additional instances up to max.',
             'hint': 'Terminate with `aws ec2 terminate-instances` and watch `describe-auto-scaling-groups` '
                     'replace it. Generate load with `stress-ng --cpu 4` on instances (or a load tester '
                     'against the ALB DNS) and watch DesiredCapacity rise.',
             'order': 6,
             'depends_on': 'AWSASG-5'}]},
 {'technology_slug': 'postgresql',
  'title': 'Design a Bookstore Schema with Constraints and Referential Integrity',
  'slug': 'postgresql-bookstore-schema-constraints',
  'architecture_type': 'custom',
  'description': 'Build the relational schema for an online bookstore from scratch: authors, books, '
                 'customers, and orders. You will enforce data quality with primary keys, foreign keys, '
                 'CHECK, UNIQUE, and NOT NULL constraints, then prove the constraints actually reject bad '
                 'data.',
  'objectives': ['Model a normalized multi-table schema with appropriate data types',
                 'Enforce referential integrity with foreign keys and ON DELETE actions',
                 'Apply CHECK, UNIQUE, and NOT NULL constraints to guarantee data quality',
                 'Use a junction table to model a many-to-many relationship',
                 'Verify constraints by attempting inserts that must fail'],
  'difficulty': 'beginner',
  'estimated_hours': 3,
  'order': 1,
  'tasks': [{'jira_key': 'BOOK-1',
             'title': 'Create the database and authors table',
             'description': 'Create a database `bookstore`, connect to it, and create an `authors` table '
                            'with `author_id` as a generated identity primary key, a NOT NULL `name`, and a '
                            'UNIQUE `email`.',
             'acceptance_criteria': '`\\d authors` shows author_id as PK, name NOT NULL, and a UNIQUE '
                                    'constraint on email.',
             'hint': 'createdb bookstore; then in psql: CREATE TABLE authors (author_id int GENERATED ALWAYS '
                     'AS IDENTITY PRIMARY KEY, name text NOT NULL, email text UNIQUE);',
             'order': 1},
            {'jira_key': 'BOOK-2',
             'title': 'Create the books table with typed columns and CHECK constraints',
             'description': 'Create a `books` table with `book_id` identity PK, `title` NOT NULL, `isbn` '
                            'UNIQUE, `price numeric(8,2)`, `published_year int`, and a `stock int` '
                            'defaulting to 0. Add a CHECK so price > 0 and stock >= 0.',
             'acceptance_criteria': 'Inserting a book with price = -5 or stock = -1 is rejected with a check '
                                    'constraint violation error.',
             'hint': 'Add: price numeric(8,2) NOT NULL CHECK (price > 0), stock int NOT NULL DEFAULT 0 CHECK '
                     '(stock >= 0). Test with INSERT ... (price) VALUES (-5).',
             'order': 2},
            {'jira_key': 'BOOK-3',
             'title': 'Link books to authors with a many-to-many junction table',
             'description': 'A book can have multiple authors and an author writes multiple books. Create a '
                            '`book_authors` table with `book_id` and `author_id` foreign keys, a composite '
                            'primary key on both, and ON DELETE CASCADE on the book reference.',
             'acceptance_criteria': '`\\d book_authors` shows a composite PK and two FKs; deleting a book '
                                    'removes its book_authors rows automatically.',
             'hint': 'CREATE TABLE book_authors (book_id int REFERENCES books(book_id) ON DELETE CASCADE, '
                     'author_id int REFERENCES authors(author_id), PRIMARY KEY (book_id, author_id));',
             'order': 3,
             'depends_on': 'BOOK-2'},
            {'jira_key': 'BOOK-4',
             'title': 'Model customers and orders with a foreign key',
             'description': 'Create a `customers` table (customer_id identity PK, email UNIQUE NOT NULL) and '
                            'an `orders` table with `order_id` identity PK, `customer_id` FK to customers, '
                            '`order_date` defaulting to now(), and `status` restricted to a fixed set of '
                            'values.',
             'acceptance_criteria': "Inserting an order with status = 'foo' fails; inserting with status = "
                                    "'pending' succeeds. Deleting a customer with orders is blocked by the "
                                    'FK.',
             'hint': "status text NOT NULL DEFAULT 'pending' CHECK (status IN "
                     "('pending','shipped','delivered','cancelled')). Leave the customer FK with default "
                     'RESTRICT behavior.',
             'order': 4,
             'depends_on': 'BOOK-1'},
            {'jira_key': 'BOOK-5',
             'title': 'Add order line items with a composite integrity rule',
             'description': 'Create `order_items` (order_id FK, book_id FK, quantity int, unit_price '
                            'numeric(8,2)) with a composite PK on (order_id, book_id) so the same book '
                            'cannot appear twice on one order, and a CHECK that quantity > 0.',
             'acceptance_criteria': 'Adding the same book twice to one order raises a duplicate key error; '
                                    'quantity = 0 is rejected.',
             'hint': 'PRIMARY KEY (order_id, book_id), quantity int NOT NULL CHECK (quantity > 0). FK '
                     'order_id ... ON DELETE CASCADE so line items die with the order.',
             'order': 5,
             'depends_on': 'BOOK-4'},
            {'jira_key': 'BOOK-6',
             'title': 'Seed data and prove the constraints hold',
             'description': 'Insert a few authors, books, customers, and a full order with line items. Then '
                            'run a set of intentionally invalid inserts (orphan FK, duplicate email, '
                            'negative price) and confirm each is rejected.',
             'acceptance_criteria': 'A valid end-to-end order inserts cleanly, and every invalid insert '
                                    'returns the expected constraint-violation error rather than being '
                                    'stored.',
             'hint': 'Wrap the failing inserts in a transaction and use ROLLBACK; or run each individually. '
                     'Query with a JOIN across orders, order_items, books to confirm the valid order is '
                     'intact.',
             'order': 6,
             'depends_on': 'BOOK-5'}]},
 {'technology_slug': 'postgresql',
  'title': 'Load, Query, and Aggregate a Sales Dataset',
  'slug': 'postgresql-sales-analytics-queries',
  'architecture_type': 'custom',
  'description': 'Ingest a realistic sales dataset and answer business questions with progressively richer '
                 'SQL. You will bulk-load with COPY, then build up from filtering and joins to GROUP BY '
                 'aggregations, subqueries, and window functions for running totals and rankings.',
  'objectives': ['Bulk-load CSV data efficiently with COPY',
                 'Write multi-table JOINs to combine related data',
                 'Aggregate with GROUP BY, HAVING, and aggregate functions',
                 'Use subqueries and CTEs to structure complex queries',
                 'Apply window functions for running totals and rankings'],
  'difficulty': 'beginner',
  'estimated_hours': 4,
  'order': 2,
  'tasks': [{'jira_key': 'SALES-1',
             'title': 'Create staging tables and bulk-load with COPY',
             'description': 'Create `products`, `customers`, and `sales` tables, then load a provided '
                            'sales.csv into `sales` using COPY. The sales table has sale_id, product_id, '
                            'customer_id, sale_date, quantity, and unit_price.',
             'acceptance_criteria': '`SELECT count(*) FROM sales;` returns the full row count of the CSV, '
                                    'and a sample row matches the file.',
             'hint': "\\COPY sales FROM '/data/sales.csv' WITH (FORMAT csv, HEADER true); use \\COPY "
                     '(client-side) if COPY hits a permissions error on the file path.',
             'order': 1},
            {'jira_key': 'SALES-2',
             'title': 'Filter and join to enrich sales records',
             'description': 'Write a query that joins sales to products and customers to produce a report of '
                            'each sale with the product name and customer name, filtered to a single month '
                            'using a date range on sale_date.',
             'acceptance_criteria': 'The result has one row per sale in the chosen month, each showing '
                                    'product name and customer name (no NULL names from missing joins).',
             'hint': 'SELECT s.sale_id, p.name, c.name FROM sales s JOIN products p USING (product_id) JOIN '
                     "customers c USING (customer_id) WHERE s.sale_date >= DATE '2025-06-01' AND s.sale_date "
                     "< DATE '2025-07-01';",
             'order': 2,
             'depends_on': 'SALES-1'},
            {'jira_key': 'SALES-3',
             'title': 'Aggregate revenue per product with GROUP BY and HAVING',
             'description': 'Compute total revenue (quantity * unit_price) per product, ordered from highest '
                            'to lowest, and use HAVING to keep only products whose total revenue exceeds '
                            '10000.',
             'acceptance_criteria': 'Result lists product name and total revenue, sorted descending, with '
                                    'only products above the 10000 threshold.',
             'hint': 'SELECT p.name, SUM(s.quantity * s.unit_price) AS revenue FROM sales s JOIN products p '
                     'USING (product_id) GROUP BY p.name HAVING SUM(s.quantity * s.unit_price) > 10000 ORDER '
                     'BY revenue DESC;',
             'order': 3,
             'depends_on': 'SALES-1'},
            {'jira_key': 'SALES-4',
             'title': 'Find top customers using a CTE and subquery',
             'description': 'Using a CTE, compute total spend per customer, then select customers who spent '
                            'more than the overall average customer spend. Return customer name and total '
                            'spend.',
             'acceptance_criteria': 'Only above-average-spend customers appear, and the average used in the '
                                    'filter matches the average over all customers.',
             'hint': 'WITH spend AS (SELECT customer_id, SUM(quantity*unit_price) t FROM sales GROUP BY '
                     'customer_id) SELECT c.name, s.t FROM spend s JOIN customers c USING (customer_id) '
                     'WHERE s.t > (SELECT avg(t) FROM spend);',
             'order': 4,
             'depends_on': 'SALES-3'},
            {'jira_key': 'SALES-5',
             'title': 'Compute a running monthly revenue total with a window function',
             'description': 'Aggregate revenue by month, then use a window function to produce a cumulative '
                            'running total of revenue across months in chronological order.',
             'acceptance_criteria': "Each month row shows that month's revenue and a running total that "
                                    'increases monotonically and equals the sum of all prior months plus the '
                                    'current one.',
             'hint': "WITH m AS (SELECT date_trunc('month', sale_date) mth, SUM(quantity*unit_price) rev "
                     'FROM sales GROUP BY 1) SELECT mth, rev, SUM(rev) OVER (ORDER BY mth) AS running FROM m '
                     'ORDER BY mth;',
             'order': 5,
             'depends_on': 'SALES-3'},
            {'jira_key': 'SALES-6',
             'title': 'Rank products within each category',
             'description': 'Add a category column to products (or join to a categories table), then rank '
                            'products by revenue within each category using RANK() OVER (PARTITION BY '
                            'category ORDER BY revenue DESC), keeping only the top 3 per category.',
             'acceptance_criteria': 'For every category, at most three products are returned, ordered by '
                                    'revenue, with a rank column of 1, 2, 3.',
             'hint': 'Wrap the ranked query in a subquery/CTE and filter WHERE rnk <= 3, since you cannot '
                     'reference a window alias directly in WHERE.',
             'order': 6,
             'depends_on': 'SALES-5'}]},
 {'technology_slug': 'postgresql',
  'title': 'Diagnose and Fix Slow Queries with EXPLAIN and Indexes',
  'slug': 'postgresql-query-tuning-explain-indexes',
  'architecture_type': 'custom',
  'description': 'Take a schema with millions of rows and a set of painfully slow queries, then make them '
                 'fast. You will read EXPLAIN ANALYZE plans, add the right B-tree, composite, and partial '
                 'indexes, turn a sequential scan into an index scan, and confirm the speedup with real '
                 'timings.',
  'objectives': ['Read and interpret EXPLAIN and EXPLAIN ANALYZE output',
                 'Distinguish sequential scans from index scans and index-only scans',
                 'Design B-tree, composite, and partial indexes for specific query shapes',
                 'Understand how column order in a composite index affects usage',
                 'Measure and verify query improvements with ANALYZE and timing'],
  'difficulty': 'intermediate',
  'estimated_hours': 5,
  'order': 3,
  'tasks': [{'jira_key': 'TUNE-1',
             'title': 'Generate a large table and capture the baseline plan',
             'description': 'Create an `events` table (id, user_id, event_type, created_at, payload) and '
                            'populate ~2 million rows with generate_series. Run ANALYZE, then capture '
                            'EXPLAIN ANALYZE for a query filtering by user_id.',
             'acceptance_criteria': 'The baseline EXPLAIN ANALYZE for `WHERE user_id = 12345` shows a Seq '
                                    'Scan and a total execution time you record for comparison.',
             'hint': 'INSERT INTO events (user_id, event_type, created_at, payload) SELECT '
                     '(random()*100000)::int, ... FROM generate_series(1,2000000); then EXPLAIN (ANALYZE, '
                     'BUFFERS) SELECT * FROM events WHERE user_id = 12345;',
             'order': 1},
            {'jira_key': 'TUNE-2',
             'title': 'Add a B-tree index and confirm the plan changes',
             'description': 'Create a B-tree index on `user_id` and re-run the same EXPLAIN ANALYZE. Compare '
                            'the plan node and execution time against the baseline you captured.',
             'acceptance_criteria': 'The plan now shows an Index Scan (or Bitmap Index Scan) on the new '
                                    'index and execution time is dramatically lower than the Seq Scan '
                                    'baseline.',
             'hint': 'CREATE INDEX idx_events_user_id ON events (user_id); Re-run EXPLAIN (ANALYZE, '
                     'BUFFERS). Note the switch from Seq Scan to Index Scan.',
             'order': 2,
             'depends_on': 'TUNE-1'},
            {'jira_key': 'TUNE-3',
             'title': 'Design a composite index for a filter + sort query',
             'description': 'Tune a query that filters by user_id and orders by created_at DESC. Create a '
                            'composite index and confirm PostgreSQL uses it to satisfy both the filter and '
                            'the ordering without a separate Sort node.',
             'acceptance_criteria': 'EXPLAIN shows the composite index used and no explicit Sort node '
                                    'appears for `WHERE user_id = 12345 ORDER BY created_at DESC LIMIT 20`.',
             'hint': 'CREATE INDEX idx_events_user_created ON events (user_id, created_at DESC); column '
                     'order matters: the equality column must come first, the ordering column second.',
             'order': 3,
             'depends_on': 'TUNE-2'},
            {'jira_key': 'TUNE-4',
             'title': 'Create a partial index for a hot subset',
             'description': "Most queries only care about `event_type = 'error'`, which is a small fraction "
                            'of rows. Create a partial index limited to that predicate and confirm it is '
                            'smaller and gets used for error-only queries.',
             'acceptance_criteria': "The partial index is used for `WHERE event_type = 'error' AND "
                                    "created_at > now() - interval '1 day'`, and \\di+ shows it is much "
                                    'smaller than a full index.',
             'hint': "CREATE INDEX idx_events_errors ON events (created_at) WHERE event_type = 'error'; "
                     'Compare size with \\di+ and verify usage with EXPLAIN.',
             'order': 4,
             'depends_on': 'TUNE-1'},
            {'jira_key': 'TUNE-5',
             'title': 'Achieve an index-only scan by covering the query',
             'description': 'Take a query that selects only user_id and created_at. Build a covering index '
                            '(or use INCLUDE) so PostgreSQL can answer it entirely from the index. Ensure '
                            'the visibility map is up to date with VACUUM.',
             'acceptance_criteria': "EXPLAIN ANALYZE reports an Index Only Scan with 'Heap Fetches: 0' (or "
                                    'near zero) after VACUUM.',
             'hint': 'CREATE INDEX idx_cover ON events (user_id) INCLUDE (created_at); run VACUUM events; '
                     'then EXPLAIN ANALYZE the SELECT user_id, created_at ... query and look for Index Only '
                     'Scan.',
             'order': 5,
             'depends_on': 'TUNE-2'},
            {'jira_key': 'TUNE-6',
             'title': 'Find and remove a redundant or unused index',
             'description': 'Query pg_stat_user_indexes to find indexes with zero scans, and identify an '
                            'index made redundant by your composite index. Drop it and confirm no query '
                            'regressed.',
             'acceptance_criteria': 'You identify at least one unused/redundant index from '
                                    'pg_stat_user_indexes, drop it, and the previously tuned queries still '
                                    'use their intended indexes.',
             'hint': 'SELECT relname, indexrelname, idx_scan FROM pg_stat_user_indexes ORDER BY idx_scan; '
                     'the single-column idx_events_user_id may now be redundant given '
                     'idx_events_user_created.',
             'order': 6,
             'depends_on': 'TUNE-3'}]},
 {'technology_slug': 'postgresql',
  'title': 'Secure a Multi-Tenant Database with Roles, Privileges, and RLS',
  'slug': 'postgresql-roles-privileges-rls-security',
  'architecture_type': 'custom',
  'description': 'Lock down a multi-tenant SaaS database so tenants can only ever see their own rows. You '
                 'will build a least-privilege role hierarchy, grant table and column privileges precisely, '
                 'then enforce hard isolation with Row-Level Security policies driven by a session variable.',
  'objectives': ['Design a least-privilege role hierarchy with login and group roles',
                 'Grant and revoke table, column, and schema privileges precisely',
                 'Enable and write Row-Level Security policies',
                 'Enforce per-tenant isolation using session settings',
                 'Verify that privilege and RLS boundaries cannot be bypassed'],
  'difficulty': 'intermediate',
  'estimated_hours': 5,
  'order': 4,
  'tasks': [{'jira_key': 'SEC-1',
             'title': 'Create a multi-tenant table and a role hierarchy',
             'description': 'Create a `documents` table with a `tenant_id` column plus content. Create a '
                            'NOLOGIN group role `app_readwrite`, a login role `app_user` that inherits it, '
                            'and confirm `app_user` has no privileges on documents by default.',
             'acceptance_criteria': 'Connecting as app_user and running `SELECT * FROM documents;` fails '
                                    'with a permission denied error before any grants.',
             'hint': "CREATE ROLE app_readwrite NOLOGIN; CREATE ROLE app_user LOGIN PASSWORD '...' IN ROLE "
                     'app_readwrite; Test with psql -U app_user.',
             'order': 1},
            {'jira_key': 'SEC-2',
             'title': 'Grant least-privilege table access to the group role',
             'description': 'Grant USAGE on the schema and SELECT, INSERT, UPDATE, DELETE on documents to '
                            '`app_readwrite` only (not to individual users). Do not grant anything on other '
                            'admin tables.',
             'acceptance_criteria': 'app_user can now SELECT and INSERT into documents (privileges inherited '
                                    'from the group), but still cannot touch tables it was not granted.',
             'hint': 'GRANT USAGE ON SCHEMA public TO app_readwrite; GRANT SELECT, INSERT, UPDATE, DELETE ON '
                     'documents TO app_readwrite; keep grants on the group, not the user.',
             'order': 2,
             'depends_on': 'SEC-1'},
            {'jira_key': 'SEC-3',
             'title': 'Restrict a sensitive column with column-level privileges',
             'description': 'Add a `salary` or `ssn`-style sensitive column. Revoke SELECT on that column '
                            'while keeping SELECT on the rest, so app_user can read most columns but not the '
                            'sensitive one.',
             'acceptance_criteria': '`SELECT * FROM documents;` as app_user fails on the sensitive column, '
                                    'but selecting the explicitly allowed columns succeeds.',
             'hint': 'REVOKE SELECT ON documents FROM app_readwrite; then GRANT SELECT (id, tenant_id, '
                     'content) ON documents TO app_readwrite; Column grants replace the table-wide SELECT.',
             'order': 3,
             'depends_on': 'SEC-2'},
            {'jira_key': 'SEC-4',
             'title': 'Enable Row-Level Security and write a tenant isolation policy',
             'description': 'Enable RLS on documents and create a policy so a session can only see rows '
                            'where tenant_id matches a session setting `app.current_tenant`. Set FORCE ROW '
                            'LEVEL SECURITY so even the table owner is subject to it in tests.',
             'acceptance_criteria': 'With RLS enabled and no policy match, app_user sees zero rows; after '
                                    "setting the tenant, only that tenant's rows appear.",
             'hint': 'ALTER TABLE documents ENABLE ROW LEVEL SECURITY; CREATE POLICY tenant_isolation ON '
                     "documents USING (tenant_id = current_setting('app.current_tenant')::int);",
             'order': 4,
             'depends_on': 'SEC-2'},
            {'jira_key': 'SEC-5',
             'title': 'Drive tenant context with a session setting and verify isolation',
             'description': 'Insert rows for tenant 1 and tenant 2. As app_user, set `app.current_tenant` to '
                            '1 and confirm only tenant 1 rows are visible; switch to 2 and confirm the '
                            'switch. Confirm INSERT of a mismatched tenant_id is blocked by a WITH CHECK '
                            'clause.',
             'acceptance_criteria': "SELECT returns only the current tenant's rows, and inserting a row "
                                    'whose tenant_id differs from the session tenant is rejected.',
             'hint': "SET app.current_tenant = '1'; add WITH CHECK (tenant_id = "
                     "current_setting('app.current_tenant')::int) to the policy so writes are constrained "
                     'too.',
             'order': 5,
             'depends_on': 'SEC-4'},
            {'jira_key': 'SEC-6',
             'title': 'Attempt to bypass the controls and confirm they hold',
             'description': 'Try to escalate: query without setting the tenant, attempt to read the '
                            "sensitive column, and try to modify another tenant's row. Document that each "
                            'attempt is denied, then review privileges with \\dp and pg_policies.',
             'acceptance_criteria': 'Every bypass attempt fails; \\dp documents shows the exact grants and '
                                    '\\d documents / pg_policies shows the active RLS policies.',
             'hint': 'As app_user run RESET app.current_tenant then SELECT (should be empty). Use SELECT * '
                     "FROM pg_policies WHERE tablename='documents'; to audit policies.",
             'order': 6,
             'depends_on': 'SEC-5'}]},
 {'technology_slug': 'postgresql',
  'title': 'Backup, Point-in-Time Recovery, and Streaming Replication',
  'slug': 'postgresql-pitr-streaming-replication',
  'architecture_type': 'custom',
  'description': 'Operate PostgreSQL like a production DBA: configure WAL archiving, take base backups, and '
                 'recover the cluster to an exact moment before a bad DELETE. Then stand up a hot-standby '
                 'replica with streaming replication and verify it stays in sync and can be promoted.',
  'objectives': ['Configure WAL archiving and continuous archiving for PITR',
                 'Take physical base backups with pg_basebackup',
                 'Perform point-in-time recovery to a target timestamp',
                 'Configure primary and standby for streaming replication',
                 'Verify replica lag and promote a standby to primary'],
  'difficulty': 'advanced',
  'estimated_hours': 8,
  'order': 5,
  'tasks': [{'jira_key': 'REPL-1',
             'title': 'Enable WAL archiving on the primary',
             'description': 'On the primary cluster, set wal_level to replica, enable archiving with '
                            'archive_mode = on, and configure archive_command to copy completed WAL segments '
                            'to an archive directory. Restart and confirm segments are being archived.',
             'acceptance_criteria': 'After a `SELECT pg_switch_wal();` new WAL files appear in the archive '
                                    'directory and the server log shows successful archive_command runs.',
             'hint': "In postgresql.conf: wal_level=replica, archive_mode=on, archive_command='test ! -f "
                     "/var/lib/pgsql/archive/%f && cp %p /var/lib/pgsql/archive/%f'. Restart, then SELECT "
                     'pg_switch_wal();',
             'order': 1},
            {'jira_key': 'REPL-2',
             'title': 'Take a base backup',
             'description': 'Create a role/entry allowing replication connections, then take a physical base '
                            'backup of the running cluster with pg_basebackup into a separate directory, '
                            'including the WAL needed to make it self-consistent.',
             'acceptance_criteria': 'pg_basebackup completes and the backup directory contains a full data '
                                    'directory copy plus a backup_label / WAL files.',
             'hint': 'In pg_hba.conf allow a replication connection; then pg_basebackup -D /backup/base -Fp '
                     '-Xs -P -U replicator. The -Xs streams WAL during the backup.',
             'order': 2,
             'depends_on': 'REPL-1'},
            {'jira_key': 'REPL-3',
             'title': 'Simulate a disaster and recover to a point in time',
             'description': 'Note the current timestamp, insert some good rows, then run a destructive '
                            '`DELETE FROM ... ` (or DROP). Restore the base backup into a fresh data '
                            'directory and configure recovery to replay WAL up to just before the '
                            'destructive statement.',
             'acceptance_criteria': 'The recovered cluster contains the good rows and does NOT contain the '
                                    'effects of the destructive statement; the log shows recovery stopping '
                                    'at the target.',
             'hint': 'Restore base backup, set restore_command to copy from the archive, set '
                     'recovery_target_time to a timestamp just before the DELETE, create recovery.signal, '
                     'and start the server.',
             'order': 3,
             'depends_on': 'REPL-2'},
            {'jira_key': 'REPL-4',
             'title': 'Configure a hot standby with streaming replication',
             'description': 'Provision a second cluster from a fresh pg_basebackup using the -R flag to '
                            'write standby connection settings, then start it as a hot standby that streams '
                            'WAL from the primary in real time.',
             'acceptance_criteria': 'The standby starts in recovery mode and `SELECT pg_is_in_recovery();` '
                                    'returns true on the standby and false on the primary.',
             'hint': 'pg_basebackup -h primary -D /standby -Fp -Xs -R -U replicator writes primary_conninfo '
                     'and standby.signal automatically. Start the standby and check pg_is_in_recovery().',
             'order': 4,
             'depends_on': 'REPL-2'},
            {'jira_key': 'REPL-5',
             'title': 'Verify replication and measure lag',
             'description': 'Insert data on the primary and confirm it appears on the standby. Inspect '
                            'replication state from both sides: pg_stat_replication on the primary and '
                            'pg_last_wal_receive_lsn / replay LSN on the standby.',
             'acceptance_criteria': 'New rows on the primary are visible on the standby within seconds, and '
                                    'pg_stat_replication shows a connected streaming standby with minimal '
                                    'replay lag.',
             'hint': 'On primary: SELECT client_addr, state, sent_lsn, replay_lsn FROM pg_stat_replication; '
                     'On standby: SELECT pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn();',
             'order': 5,
             'depends_on': 'REPL-4'},
            {'jira_key': 'REPL-6',
             'title': 'Promote the standby to primary',
             'description': 'Simulate primary failure by stopping it, then promote the standby so it becomes '
                            'a writable primary. Confirm it exits recovery and accepts writes, and '
                            'understand the timeline switch that occurs.',
             'acceptance_criteria': 'After promotion `SELECT pg_is_in_recovery();` returns false on the '
                                    'former standby and an INSERT succeeds; the log records a new timeline.',
             'hint': 'Run pg_ctl promote -D /standby (or SELECT pg_promote();). Verify with '
                     'pg_is_in_recovery() = false and a test INSERT.',
             'order': 6,
             'depends_on': 'REPL-5'}]},
 {'technology_slug': 'mysql',
  'title': 'Design and Normalize a Bookstore Schema in MySQL',
  'slug': 'mysql-schema-design-normalization-bookstore',
  'architecture_type': 'custom',
  'description': 'Build a relational schema for an online bookstore from a messy single-table spreadsheet, '
                 'then normalize it to Third Normal Form with proper primary and foreign keys. You will '
                 'finish with a clean, constraint-enforced MySQL database that eliminates redundancy and '
                 'prevents bad data at the storage layer.',
  'objectives': ['Create databases and tables with appropriate data types, PRIMARY KEY, and AUTO_INCREMENT',
                 'Identify functional dependencies and decompose an unnormalized table through 1NF, 2NF, and '
                 '3NF',
                 'Enforce referential integrity with FOREIGN KEY constraints and ON DELETE/UPDATE actions',
                 'Apply NOT NULL, UNIQUE, CHECK, and DEFAULT constraints to guarantee data quality',
                 'Verify the schema by inserting valid rows and proving invalid rows are rejected'],
  'difficulty': 'beginner',
  'estimated_hours': 3,
  'order': 1,
  'tasks': [{'jira_key': 'BOOKDB-1',
             'title': 'Create the database and connect as a working user',
             'description': 'Log in to MySQL, create a dedicated database named bookstore using UTF8MB4, and '
                            'set it as the active schema. Confirm you are on the correct server version and '
                            'character set.',
             'acceptance_criteria': "SHOW DATABASES lists 'bookstore'; SELECT DATABASE() returns "
                                    "'bookstore'; the default charset is utf8mb4.",
             'hint': 'mysql -u root -p then: CREATE DATABASE bookstore CHARACTER SET utf8mb4 COLLATE '
                     'utf8mb4_0900_ai_ci; USE bookstore; SELECT VERSION();',
             'order': 1},
            {'jira_key': 'BOOKDB-2',
             'title': 'Load the messy flat table and spot the anomalies',
             'description': 'Create a single wide table raw_orders that mirrors a spreadsheet: each row '
                            'repeats customer name, email, book title, author, and publisher. Insert 8-10 '
                            'sample rows and identify insertion, update, and deletion anomalies.',
             'acceptance_criteria': 'raw_orders exists with at least 8 rows; you can name one update anomaly '
                                    '(e.g. changing an author name requires editing many rows) and one '
                                    'insertion anomaly (cannot add a book with no order).',
             'hint': 'CREATE TABLE raw_orders (id INT PRIMARY KEY AUTO_INCREMENT, customer_name '
                     'VARCHAR(100), customer_email VARCHAR(120), book_title VARCHAR(200), author '
                     'VARCHAR(120), publisher VARCHAR(120), qty INT, order_date DATE); then INSERT '
                     'deliberately redundant rows.',
             'order': 2,
             'depends_on': 'BOOKDB-1'},
            {'jira_key': 'BOOKDB-3',
             'title': 'Decompose to 3NF with lookup tables',
             'description': 'Break raw_orders into normalized tables: customers, publishers, authors, books, '
                            'orders, and order_items. Each non-key column must depend on the whole key and '
                            'nothing but the key. Choose surrogate INT primary keys.',
             'acceptance_criteria': 'Six tables exist; no repeating groups; author, publisher, and book '
                                    'attributes each live in exactly one table; SHOW TABLES lists all six.',
             'hint': 'customers(id, name, email); publishers(id, name); authors(id, name); books(id, title, '
                     'author_id, publisher_id, isbn); orders(id, customer_id, order_date); order_items(id, '
                     'order_id, book_id, qty). Put shared attributes in their own table.',
             'order': 3,
             'depends_on': 'BOOKDB-2'},
            {'jira_key': 'BOOKDB-4',
             'title': 'Add foreign keys and referential actions',
             'description': 'Wire every child table to its parent with FOREIGN KEY constraints. Use ON '
                            'DELETE RESTRICT for financial data (orders) and ON DELETE CASCADE where '
                            'appropriate (order_items when an order is removed).',
             'acceptance_criteria': 'SHOW CREATE TABLE order_items shows a FK to orders with ON DELETE '
                                    'CASCADE; attempting to delete a customer that still has orders fails '
                                    'with a foreign key error.',
             'hint': 'ALTER TABLE order_items ADD CONSTRAINT fk_oi_order FOREIGN KEY (order_id) REFERENCES '
                     'orders(id) ON DELETE CASCADE; ensure the parent columns are indexed (PK covers this).',
             'order': 4,
             'depends_on': 'BOOKDB-3'},
            {'jira_key': 'BOOKDB-5',
             'title': 'Enforce data quality with column constraints',
             'description': 'Add UNIQUE on customers.email and books.isbn, NOT NULL on required columns, a '
                            'CHECK (qty > 0) on order_items, and a DEFAULT CURRENT_DATE on '
                            'orders.order_date.',
             'acceptance_criteria': 'Inserting a duplicate email fails; inserting order_items with qty = 0 '
                                    "fails the CHECK; an order inserted without order_date gets today's "
                                    'date.',
             'hint': 'ALTER TABLE customers ADD UNIQUE (email); ALTER TABLE order_items ADD CONSTRAINT '
                     'chk_qty CHECK (qty > 0); ALTER TABLE orders MODIFY order_date DATE NOT NULL DEFAULT '
                     '(CURRENT_DATE).',
             'order': 5,
             'depends_on': 'BOOKDB-4'},
            {'jira_key': 'BOOKDB-6',
             'title': 'Migrate the data and validate with a join',
             'description': 'Populate the normalized tables from raw_orders (or fresh inserts), then '
                            'reconstruct the original view with a multi-table JOIN to prove no information '
                            'was lost.',
             'acceptance_criteria': 'A SELECT joining orders, order_items, books, authors, publishers, and '
                                    'customers returns the same logical rows as raw_orders; row counts '
                                    'reconcile.',
             'hint': 'SELECT c.name, b.title, a.name AS author, oi.qty FROM order_items oi JOIN orders o ON '
                     'oi.order_id=o.id JOIN books b ON oi.book_id=b.id JOIN authors a ON b.author_id=a.id '
                     'JOIN customers c ON o.customer_id=c.id;',
             'order': 6,
             'depends_on': 'BOOKDB-5'}]},
 {'technology_slug': 'mysql',
  'title': 'Secure a MySQL Database with Users, Roles, and Least-Privilege Grants',
  'slug': 'mysql-users-grants-security-hardening',
  'architecture_type': 'custom',
  'description': 'Lock down a shared application database by replacing the anti-pattern of everyone using '
                 'root with purpose-built accounts and least-privilege grants. You will create app, '
                 'read-only reporting, and backup accounts, group privileges with roles, and audit exactly '
                 'who can do what.',
  'objectives': ['Create MySQL accounts scoped by username and host and manage their authentication',
                 'Grant table- and database-level privileges following least privilege',
                 'Define and assign roles to standardize permissions across accounts',
                 'Audit effective privileges with SHOW GRANTS and the information_schema privilege tables',
                 'Rotate a password and revoke access to demonstrate credential lifecycle control'],
  'difficulty': 'beginner',
  'estimated_hours': 3,
  'order': 2,
  'tasks': [{'jira_key': 'SECDB-1',
             'title': 'Set up the target database and audit existing accounts',
             'description': 'Create a shopdb database with a couple of tables, then inventory current '
                            'accounts and their hosts. Identify any accounts with blank passwords or overly '
                            'broad wildcard hosts.',
             'acceptance_criteria': 'shopdb exists with at least two tables; SELECT user, host, plugin FROM '
                                    "mysql.user lists all accounts; you can point to any account using '%' "
                                    'as its host.',
             'hint': "CREATE DATABASE shopdb; then SELECT user, host, authentication_string='' AS blank_pw "
                     "FROM mysql.user; note who uses host '%'.",
             'order': 1},
            {'jira_key': 'SECDB-2',
             'title': 'Create purpose-built application accounts',
             'description': "Create three accounts: app_rw@'10.0.%' for the application, "
                            "reporter@'localhost' for analysts, and backup_svc@'localhost' for backups. Use "
                            'strong passwords and appropriate host scoping.',
             'acceptance_criteria': 'All three accounts appear in mysql.user with the intended host '
                                    "patterns; each can authenticate; no account uses host '%'.",
             'hint': "CREATE USER 'app_rw'@'10.0.%' IDENTIFIED BY 'S0me-Str0ng!pw'; repeat for "
                     "reporter@'localhost' and backup_svc@'localhost'.",
             'order': 2,
             'depends_on': 'SECDB-1'},
            {'jira_key': 'SECDB-3',
             'title': 'Grant least-privilege access per account',
             'description': 'Give app_rw SELECT/INSERT/UPDATE/DELETE on shopdb.*, reporter only SELECT on '
                            'shopdb.*, and backup_svc the minimal SELECT, LOCK TABLES, SHOW VIEW, EVENT, '
                            'TRIGGER, and RELOAD needed for a consistent dump.',
             'acceptance_criteria': 'reporter can SELECT but a INSERT attempt is denied; app_rw can write '
                                    'but cannot DROP the database; backup_svc has no write privileges on '
                                    'table data.',
             'hint': "GRANT SELECT,INSERT,UPDATE,DELETE ON shopdb.* TO 'app_rw'@'10.0.%'; GRANT SELECT ON "
                     "shopdb.* TO 'reporter'@'localhost'; GRANT SELECT,LOCK TABLES,SHOW "
                     "VIEW,EVENT,TRIGGER,RELOAD ON *.* TO 'backup_svc'@'localhost'; FLUSH PRIVILEGES;",
             'order': 3,
             'depends_on': 'SECDB-2'},
            {'jira_key': 'SECDB-4',
             'title': 'Introduce roles to standardize permissions',
             'description': 'Create roles app_readwrite and app_readonly, grant the appropriate privileges '
                            'to the roles, then assign roles to accounts and set them as default so '
                            'privileges activate on login.',
             'acceptance_criteria': 'SHOW GRANTS FOR reporter shows the app_readonly role; after SET DEFAULT '
                                    'ROLE the reporter can query without manually activating the role.',
             'hint': 'CREATE ROLE app_readonly, app_readwrite; GRANT SELECT ON shopdb.* TO app_readonly; '
                     "GRANT app_readonly TO 'reporter'@'localhost'; SET DEFAULT ROLE ALL TO "
                     "'reporter'@'localhost';",
             'order': 4,
             'depends_on': 'SECDB-3'},
            {'jira_key': 'SECDB-5',
             'title': 'Audit effective privileges',
             'description': "Verify each account's real capabilities using SHOW GRANTS and "
                            'information_schema privilege views. Produce a short access matrix mapping '
                            'account to allowed operations.',
             'acceptance_criteria': 'You can list every privilege for each account via SHOW GRANTS; a query '
                                    'against information_schema.schema_privileges confirms reporter has only '
                                    'SELECT on shopdb.',
             'hint': "SHOW GRANTS FOR 'app_rw'@'10.0.%'; SELECT grantee, privilege_type FROM "
                     "information_schema.schema_privileges WHERE table_schema='shopdb';",
             'order': 5,
             'depends_on': 'SECDB-4'},
            {'jira_key': 'SECDB-6',
             'title': 'Rotate a password and revoke stale access',
             'description': "Rotate app_rw's password, force its expiration policy, and fully revoke and "
                            'drop a decommissioned account to complete the credential lifecycle.',
             'acceptance_criteria': 'app_rw authenticates with the new password only; the decommissioned '
                                    'account no longer appears in mysql.user; revoked privileges are gone '
                                    'from SHOW GRANTS.',
             'hint': "ALTER USER 'app_rw'@'10.0.%' IDENTIFIED BY 'New-Str0ng!pw' PASSWORD EXPIRE INTERVAL 90 "
                     "DAY; REVOKE ALL PRIVILEGES ON shopdb.* FROM 'olduser'@'localhost'; DROP USER "
                     "'olduser'@'localhost';",
             'order': 6,
             'depends_on': 'SECDB-5'}]},
 {'technology_slug': 'mysql',
  'title': 'Backup and Point-in-Time Recovery with mysqldump and Binary Logs',
  'slug': 'mysql-backup-restore-binlog-pitr',
  'architecture_type': 'custom',
  'description': 'Build a reliable backup and recovery workflow: take consistent logical backups with '
                 'mysqldump, enable binary logging, and perform point-in-time recovery to undo an accidental '
                 'data-loss event. You will simulate a bad DELETE and restore the database to the exact '
                 'moment before disaster struck.',
  'objectives': ['Take consistent full logical backups with mysqldump including routines and triggers',
                 'Enable and interpret binary logs for incremental, point-in-time recovery',
                 'Restore a full backup into a clean database and validate integrity',
                 'Replay binlog events up to a precise position or timestamp with mysqlbinlog',
                 'Verify recovery correctness and reason about RPO/RTO trade-offs'],
  'difficulty': 'intermediate',
  'estimated_hours': 4,
  'order': 3,
  'tasks': [{'jira_key': 'BKUP-1',
             'title': 'Enable binary logging and confirm configuration',
             'description': 'Turn on binary logging with a server_id and ROW format in my.cnf, restart '
                            'MySQL, and confirm the binlog is active. This is the foundation for incremental '
                            'recovery.',
             'acceptance_criteria': "SHOW VARIABLES LIKE 'log_bin' returns ON; SHOW BINARY LOGS lists at "
                                    'least one file; binlog_format is ROW.',
             'hint': 'In [mysqld]: server_id=1, log_bin=/var/log/mysql/mysql-bin, binlog_format=ROW. '
                     'Restart, then SHOW MASTER STATUS; and SHOW BINARY LOGS;',
             'order': 1},
            {'jira_key': 'BKUP-2',
             'title': 'Seed a sample database with known data',
             'description': 'Create a sales database with a customers and an invoices table, then insert a '
                            'known, countable dataset you can later verify against.',
             'acceptance_criteria': 'sales database exists; SELECT COUNT(*) on both tables returns a '
                                    'documented baseline you record for later comparison.',
             'hint': 'CREATE DATABASE sales; create tables; INSERT 50 customers and 200 invoices; record '
                     'SELECT COUNT(*) FROM invoices;',
             'order': 2,
             'depends_on': 'BKUP-1'},
            {'jira_key': 'BKUP-3',
             'title': 'Take a consistent full logical backup',
             'description': 'Use mysqldump with --single-transaction to capture a consistent snapshot '
                            'without locking, including routines, triggers, and events. Record the binlog '
                            'file and position at dump time.',
             'acceptance_criteria': 'A sales_full.sql file exists and is non-empty; it contains CREATE TABLE '
                                    'and INSERT statements; you have recorded the binlog coordinates via '
                                    '--master-data or SHOW MASTER STATUS.',
             'hint': 'mysqldump --single-transaction --routines --triggers --events --master-data=2 sales > '
                     "sales_full.sql; grep 'CHANGE MASTER' sales_full.sql to read the position.",
             'order': 3,
             'depends_on': 'BKUP-2'},
            {'jira_key': 'BKUP-4',
             'title': 'Simulate a disaster after the backup',
             'description': 'After the backup, run more legitimate writes, then execute an accidental '
                            'destructive statement (a DELETE without WHERE on invoices). Note the '
                            'approximate timestamp and the binlog position just before the bad statement.',
             'acceptance_criteria': 'invoices row count drops to 0; you can identify the binlog file and the '
                                    'position (or timestamp) immediately before the DELETE using '
                                    'mysqlbinlog.',
             'hint': 'Do a few good INSERTs first, then DELETE FROM invoices; -- oops. mysqlbinlog '
                     '--base64-output=DECODE-ROWS -vv mysql-bin.00000X | grep -n -i delete to find the '
                     'offending position.',
             'order': 4,
             'depends_on': 'BKUP-3'},
            {'jira_key': 'BKUP-5',
             'title': 'Restore the full backup into a clean database',
             'description': 'Recreate the database fresh and load the full mysqldump. This returns you to '
                            'the snapshot state; the post-backup good writes are not yet present.',
             'acceptance_criteria': 'After restore, invoices count equals the backup-time baseline (not the '
                                    'pre-disaster count yet); no errors during import.',
             'hint': 'DROP DATABASE sales; CREATE DATABASE sales; mysql sales < sales_full.sql; then SELECT '
                     'COUNT(*) FROM invoices;',
             'order': 5,
             'depends_on': 'BKUP-4'},
            {'jira_key': 'BKUP-6',
             'title': 'Replay binlogs for point-in-time recovery',
             'description': 'Apply binary log events from the backup position up to just before the bad '
                            'DELETE, restoring the legitimate post-backup writes while excluding the '
                            'destructive statement.',
             'acceptance_criteria': 'After replay, invoices contains the backup rows plus the good '
                                    'post-backup inserts but not the deleted state; the count matches the '
                                    'pre-disaster documented total.',
             'hint': 'mysqlbinlog --start-position=<backup_pos> --stop-position=<pos_before_delete> '
                     'mysql-bin.00000X | mysql sales; then verify SELECT COUNT(*) FROM invoices; equals the '
                     'pre-DELETE baseline.',
             'order': 6,
             'depends_on': 'BKUP-5'}]},
 {'technology_slug': 'mysql',
  'title': 'Diagnose and Fix Slow Queries with Indexes and EXPLAIN',
  'slug': 'mysql-performance-tuning-slow-query-indexes',
  'architecture_type': 'custom',
  'description': "Take a sluggish reporting database and make it fast using MySQL's own diagnostics. You "
                 'will capture slow queries with the slow query log, read EXPLAIN plans to find full table '
                 'scans, and add targeted single-column, composite, and covering indexes to turn seconds '
                 'into milliseconds.',
  'objectives': ['Enable and analyze the slow query log to find the worst offenders',
                 'Read EXPLAIN and EXPLAIN ANALYZE output to identify full scans and bad join order',
                 'Design single-column, composite, and covering indexes that match query patterns',
                 'Measure before/after performance and avoid over-indexing and redundant indexes',
                 'Recognize when indexes are ignored due to functions or leading-wildcard predicates'],
  'difficulty': 'intermediate',
  'estimated_hours': 5,
  'order': 4,
  'tasks': [{'jira_key': 'PERF-1',
             'title': 'Generate a realistic dataset',
             'description': 'Create an orders table and populate it with roughly 500k rows spanning many '
                            'customers, statuses, and dates so that scans are genuinely expensive.',
             'acceptance_criteria': 'orders has at least 500,000 rows; SELECT COUNT(*) confirms the volume; '
                                    'the table has no non-primary indexes yet.',
             'hint': 'Use a recursive CTE or a numbers table to bulk-insert: INSERT INTO orders '
                     '(customer_id,status,total,created_at) SELECT ... FROM a generator. Confirm with SHOW '
                     'INDEX FROM orders;',
             'order': 1},
            {'jira_key': 'PERF-2',
             'title': 'Enable the slow query log',
             'description': 'Turn on the slow query log with a low long_query_time and enable '
                            'log_queries_not_using_indexes to capture the problem queries as you run the '
                            'reporting workload.',
             'acceptance_criteria': "SHOW VARIABLES LIKE 'slow_query_log' is ON; long_query_time is set low "
                                    '(e.g. 0.2s); the slow log file grows when you run unindexed queries.',
             'hint': 'SET GLOBAL slow_query_log=ON; SET GLOBAL long_query_time=0.2; SET GLOBAL '
                     'log_queries_not_using_indexes=ON; then inspect with mysqldumpslow -s t slow.log.',
             'order': 2,
             'depends_on': 'PERF-1'},
            {'jira_key': 'PERF-3',
             'title': 'Profile the worst query with EXPLAIN',
             'description': 'Run a report query filtering by customer_id and status ordered by created_at, '
                            'then read its EXPLAIN plan to confirm a full table scan and estimate rows '
                            'examined.',
             'acceptance_criteria': 'EXPLAIN shows type=ALL and a high rows estimate; EXPLAIN ANALYZE '
                                    'reports actual time in the hundreds of milliseconds or worse.',
             'hint': "EXPLAIN SELECT * FROM orders WHERE customer_id=42 AND status='shipped' ORDER BY "
                     'created_at; look for type: ALL and key: NULL. Then EXPLAIN ANALYZE the same query.',
             'order': 3,
             'depends_on': 'PERF-2'},
            {'jira_key': 'PERF-4',
             'title': 'Add a composite index matching the predicate and sort',
             'description': 'Create a composite index on (customer_id, status, created_at) so the equality '
                            'predicates and the ORDER BY are satisfied by the index. Re-run EXPLAIN to '
                            'confirm the change.',
             'acceptance_criteria': 'EXPLAIN now shows type=ref using the new index and a dramatically lower '
                                    "rows estimate; the ORDER BY no longer triggers 'Using filesort'.",
             'hint': 'CREATE INDEX idx_cust_status_created ON orders (customer_id, status, created_at); '
                     'column order matters: equality columns first, then the sort column.',
             'order': 4,
             'depends_on': 'PERF-3'},
            {'jira_key': 'PERF-5',
             'title': 'Build a covering index and measure the win',
             'description': 'For a specific SELECT of only a few columns, extend the index so the query is '
                            'answered entirely from the index (Using index) with no table lookups. Compare '
                            'timings before and after.',
             'acceptance_criteria': "EXPLAIN shows 'Using index' (covering) for the targeted query; EXPLAIN "
                                    'ANALYZE shows at least an order-of-magnitude latency reduction versus '
                                    'PERF-3.',
             'hint': 'If the query selects customer_id,status,created_at,total, create INDEX idx_cover '
                     "(customer_id,status,created_at,total). Extra='Using index' means no row lookups.",
             'order': 5,
             'depends_on': 'PERF-4'},
            {'jira_key': 'PERF-6',
             'title': 'Find and fix a query that ignores its index',
             'description': 'Demonstrate two SARGability pitfalls: wrapping the indexed column in a function '
                            '(e.g. DATE(created_at)) and a leading-wildcard LIKE. Rewrite each so the index '
                            'is used, and remove any redundant indexes you created.',
             'acceptance_criteria': 'The rewritten range query uses the index (type=range, key not NULL); '
                                    'SHOW INDEX confirms no redundant/duplicate index remains; the slow log '
                                    'no longer flags these queries.',
             'hint': "Replace WHERE DATE(created_at)='2026-01-01' with WHERE created_at >= '2026-01-01' AND "
                     "created_at < '2026-01-02'. Avoid LIKE '%term'. Drop indexes fully covered by a wider "
                     'one via DROP INDEX.',
             'order': 6,
             'depends_on': 'PERF-5'}]},
 {'technology_slug': 'mysql',
  'title': 'Build Primary-Replica Replication with Failover and Monitoring',
  'slug': 'mysql-primary-replica-replication-failover',
  'architecture_type': '2tier',
  'description': 'Stand up asynchronous primary-replica replication between two MySQL servers using GTIDs, '
                 'then operate it like production: monitor lag, break and repair the replica, and perform a '
                 'controlled promotion. You will finish able to reason about consistency, read scaling, and '
                 'disaster failover.',
  'objectives': ['Configure GTID-based replication with dedicated replication accounts',
                 'Seed a replica from a consistent primary backup and start replication',
                 'Monitor replication health, lag, and error state operationally',
                 'Diagnose and recover from a replication break without full reseeding',
                 'Perform a controlled promotion of a replica to primary'],
  'difficulty': 'advanced',
  'estimated_hours': 7,
  'order': 5,
  'tasks': [{'jira_key': 'REPL-1',
             'title': 'Configure two servers for GTID replication',
             'description': 'On the primary and replica, set unique server_id values, enable binary logging, '
                            'and turn on gtid_mode and enforce_gtid_consistency. Restart both and confirm '
                            'GTID mode is active.',
             'acceptance_criteria': "Both servers report distinct server_id; SHOW VARIABLES LIKE 'gtid_mode' "
                                    'returns ON on both; log_bin is ON.',
             'hint': 'In each [mysqld]: unique server_id, log_bin=ON, gtid_mode=ON, '
                     'enforce_gtid_consistency=ON. Restart, then SELECT @@server_id, @@gtid_mode;',
             'order': 1},
            {'jira_key': 'REPL-2',
             'title': 'Create a replication account on the primary',
             'description': "Create a dedicated repl user restricted to the replica's network with only "
                            'REPLICATION SLAVE privilege, following least privilege.',
             'acceptance_criteria': 'SHOW GRANTS FOR the repl user shows exactly REPLICATION SLAVE ON *.*; '
                                    'the account can connect from the replica host.',
             'hint': "CREATE USER 'repl'@'10.0.0.%' IDENTIFIED BY 'Repl-Str0ng!pw'; GRANT REPLICATION SLAVE "
                     "ON *.* TO 'repl'@'10.0.0.%';",
             'order': 2,
             'depends_on': 'REPL-1'},
            {'jira_key': 'REPL-3',
             'title': 'Seed the replica from a consistent dump',
             'description': 'Take a GTID-aware mysqldump from the primary and import it on the replica so '
                            'the replica knows the exact GTID set already applied.',
             'acceptance_criteria': 'The dump includes SET @@GLOBAL.GTID_PURGED; after import, SELECT '
                                    "@@GLOBAL.gtid_executed on the replica matches the primary's purged set.",
             'hint': 'mysqldump --all-databases --single-transaction --triggers --routines --events '
                     '--set-gtid-purged=ON > full.sql; import on replica with mysql < full.sql (reset the '
                     "replica's GTID state first if needed).",
             'order': 3,
             'depends_on': 'REPL-2'},
            {'jira_key': 'REPL-4',
             'title': 'Start replication and verify data flow',
             'description': 'Point the replica at the primary using MASTER_AUTO_POSITION=1, start the '
                            'replica threads, then insert on the primary and confirm the row appears on the '
                            'replica.',
             'acceptance_criteria': 'SHOW REPLICA STATUS shows Replica_IO_Running=Yes and '
                                    'Replica_SQL_Running=Yes with Last_Error empty; a row inserted on the '
                                    'primary is readable on the replica within seconds.',
             'hint': "CHANGE REPLICATION SOURCE TO SOURCE_HOST='primary', SOURCE_USER='repl', "
                     "SOURCE_PASSWORD='...', SOURCE_AUTO_POSITION=1; START REPLICA; then SHOW REPLICA "
                     'STATUS\\G;',
             'order': 4,
             'depends_on': 'REPL-3'},
            {'jira_key': 'REPL-5',
             'title': 'Monitor lag and recover from a break',
             'description': 'Observe Seconds_Behind_Source under load, then intentionally break replication '
                            'by creating a conflicting row on the replica. Diagnose the error and recover by '
                            'resolving the conflict and skipping/re-syncing the offending transaction.',
             'acceptance_criteria': 'You can read Seconds_Behind_Source; after inducing an error you '
                                    'identify it in Last_SQL_Error; replication resumes with both threads '
                                    'Yes and no data divergence.',
             'hint': 'Cause a duplicate-key error on the replica, read SHOW REPLICA STATUS\\G '
                     'Last_SQL_Error, fix the conflicting row, then use GTID-based skip (SET GTID_NEXT to '
                     'the errant GTID and commit an empty transaction) and START REPLICA.',
             'order': 5,
             'depends_on': 'REPL-4'},
            {'jira_key': 'REPL-6',
             'title': 'Perform a controlled promotion',
             'description': 'Simulate planned failover: stop writes on the primary, ensure the replica has '
                            'caught up (equal gtid_executed), stop replication on the replica, and promote '
                            'it to accept writes.',
             'acceptance_criteria': "Before promotion the replica's gtid_executed equals the primary's; "
                                    'after STOP REPLICA and enabling writes, the promoted server accepts a '
                                    'test INSERT and read_only is OFF.',
             'hint': 'Set the primary read_only=ON, confirm replica caught up (compare @@gtid_executed), '
                     'then on the replica: STOP REPLICA; RESET REPLICA ALL; SET GLOBAL read_only=OFF; verify '
                     'with a test write.',
             'order': 6,
             'depends_on': 'REPL-5'}]},
 {'technology_slug': 'react',
  'title': 'Scaffold Your First React SPA with Vite',
  'slug': 'react-vite-spa-foundations',
  'architecture_type': 'custom',
  'description': 'Stand up a modern React single-page app from an empty folder using Vite. You will scaffold '
                 'the project, learn the component + props model, add interactive state with hooks, and '
                 'produce an optimized production build. This is the foundation every later React project '
                 'builds on.',
  'objectives': ['Scaffold a Vite + React project and run the dev server with HMR',
                 'Compose a UI from reusable presentational components driven by props',
                 'Add local interactive state with the useState hook',
                 'Render lists correctly with stable keys',
                 'Produce and preview an optimized production build'],
  'difficulty': 'beginner',
  'estimated_hours': 3,
  'order': 1,
  'tasks': [{'jira_key': 'RVITE-1',
             'title': 'Scaffold a Vite + React project',
             'description': 'Create a new React app named `spa-foundations` using the Vite React (JSX) '
                            'template, install dependencies, and start the dev server.',
             'acceptance_criteria': '`npm run dev` starts Vite on http://localhost:5173 and the default '
                                    'React page renders in the browser with hot module replacement working.',
             'hint': 'Run `npm create vite@latest spa-foundations -- --template react`, then `cd '
                     'spa-foundations && npm install && npm run dev`. Vite serves on port 5173 by default.',
             'order': 1},
            {'jira_key': 'RVITE-2',
             'title': 'Clean the boilerplate and render a root component',
             'description': 'Strip the demo counter/logo markup from App.jsx and render a simple `<App>` '
                            'component that shows a page title. Confirm the app mounts via `createRoot` in '
                            'src/main.jsx.',
             'acceptance_criteria': 'The browser shows only your own heading (e.g. an <h1>), with no '
                                    'leftover Vite/React demo content, and no console errors.',
             'hint': "Delete the counter state and logo imports in src/App.jsx. Keep src/main.jsx's "
                     "`createRoot(document.getElementById('root')).render(<App />)`. A component is just a "
                     'function that returns JSX.',
             'order': 2,
             'depends_on': 'RVITE-1'},
            {'jira_key': 'RVITE-3',
             'title': 'Build a reusable presentational component with props',
             'description': 'Create src/components/ProductCard.jsx that accepts `name`, `price`, and '
                            '`inStock` props and renders them. Import and render it from App with hardcoded '
                            'props.',
             'acceptance_criteria': 'ProductCard renders purely from the props passed in — changing the '
                                    'props in App changes what appears, and the component contains no '
                                    'hardcoded product data.',
             'hint': 'Destructure props in the signature: `function ProductCard({ name, price, inStock }) { '
                     '... }`. Presentational components should be pure functions of their props.',
             'order': 3,
             'depends_on': 'RVITE-2'},
            {'jira_key': 'RVITE-4',
             'title': 'Render a list of products with stable keys',
             'description': 'Define an array of product objects in App and map over it to render a '
                            'ProductCard for each. Give each rendered element a stable `key`.',
             'acceptance_criteria': "The page shows one card per array item and React logs no 'unique key' "
                                    'warning in the console.',
             'hint': 'Use `{products.map(p => <ProductCard key={p.id} {...p} />)}`. Use a stable id as the '
                     'key, never the array index when the list can reorder.',
             'order': 4,
             'depends_on': 'RVITE-3'},
            {'jira_key': 'RVITE-5',
             'title': 'Add interactive state with useState',
             'description': "Add a 'Add to cart' button to ProductCard and a cart count in App. Track the "
                            'count with useState and pass an `onAdd` callback down to each card.',
             'acceptance_criteria': "Clicking a card's button increments the cart count shown in App, and "
                                    'the update never mutates state directly.',
             'hint': 'In App: `const [count, setCount] = useState(0)`. Update with the functional form '
                     '`setCount(c => c + 1)`. Pass `onAdd={() => setCount(c => c + 1)}` down as a prop.',
             'order': 5,
             'depends_on': 'RVITE-4'},
            {'jira_key': 'RVITE-6',
             'title': 'Build and preview a production bundle',
             'description': 'Generate an optimized production build with Vite and serve it locally to '
                            'confirm it works outside the dev server.',
             'acceptance_criteria': '`npm run build` produces a `dist/` folder and `npm run preview` serves '
                                    'the built app with the same functionality as dev.',
             'hint': '`npm run build` runs `vite build` (minifies, tree-shakes, hashes filenames into '
                     'dist/). Then `npm run preview` serves dist/ on a local port so you can smoke-test the '
                     'real artifact.',
             'order': 6,
             'depends_on': 'RVITE-5'}]},
 {'technology_slug': 'react',
  'title': 'Build a Task Tracker: Hooks, Lists & Derived State',
  'slug': 'react-task-tracker-hooks',
  'architecture_type': 'custom',
  'description': 'Build an interactive task tracker SPA that adds, toggles, deletes, and filters tasks '
                 'entirely in the browser. You will practice controlled inputs, immutable state updates, '
                 'derived state, list rendering, and refactoring complex state into a useReducer. No backend '
                 'required.',
  'objectives': ['Manage a list in state using immutable add/update/remove patterns',
                 'Wire a controlled input to create new items',
                 'Compute derived state (filters and counts) without extra state',
                 'Refactor tangled useState logic into a useReducer',
                 'Persist state to localStorage with useEffect'],
  'difficulty': 'beginner',
  'estimated_hours': 4,
  'order': 2,
  'tasks': [{'jira_key': 'RTASK-1',
             'title': 'Scaffold the app and model task state',
             'description': 'Create a Vite + React app and hold an array of task objects (`{ id, text, done '
                            '}`) in App using useState. Render the list of tasks.',
             'acceptance_criteria': 'The app renders a hardcoded starter list of tasks, each showing its '
                                    'text and done state.',
             'hint': "`const [tasks, setTasks] = useState([{ id: crypto.randomUUID(), text: 'Learn hooks', "
                     'done: false }])`. Map over tasks to render them with `key={task.id}`.',
             'order': 1},
            {'jira_key': 'RTASK-2',
             'title': 'Add tasks via a controlled input',
             'description': 'Add a text input and an Add button. Track the input value in state (controlled '
                            'component) and append a new task on submit, clearing the input.',
             'acceptance_criteria': 'Typing and submitting adds a new task to the list without mutating the '
                                    'previous array, and the input clears afterward.',
             'hint': 'Controlled input: `value={text} onChange={e => setText(e.target.value)}`. Add '
                     'immutably with `setTasks(prev => [...prev, newTask])` — never `prev.push`.',
             'order': 2,
             'depends_on': 'RTASK-1'},
            {'jira_key': 'RTASK-3',
             'title': 'Toggle and delete tasks immutably',
             'description': "Add a checkbox to toggle each task's `done` and a button to delete it. Both "
                            'must update state without mutating existing objects/arrays.',
             'acceptance_criteria': "Toggling flips only the targeted task's `done`; deleting removes only "
                                    'that task; existing task objects are never mutated in place.',
             'hint': 'Toggle: `setTasks(ts => ts.map(t => t.id === id ? { ...t, done: !t.done } : t))`. '
                     'Delete: `setTasks(ts => ts.filter(t => t.id !== id))`.',
             'order': 3,
             'depends_on': 'RTASK-2'},
            {'jira_key': 'RTASK-4',
             'title': 'Add filtering with derived state',
             'description': 'Add All / Active / Completed filter buttons. Store only the active filter in '
                            'state and compute the visible list from tasks + filter during render.',
             'acceptance_criteria': 'The visible list matches the selected filter, and there is NO separate '
                                    'state array holding the filtered results — it is computed on render.',
             'hint': 'Keep one `filter` state value. Derive: `const visible = tasks.filter(t => filter === '
                     "'all' || (filter === 'active' ? !t.done : t.done))`. Derived data should never be "
                     'stored in state.',
             'order': 4,
             'depends_on': 'RTASK-3'},
            {'jira_key': 'RTASK-5',
             'title': 'Refactor to useReducer',
             'description': 'Replace the scattered setTasks calls with a single reducer handling `add`, '
                            '`toggle`, `delete` actions, wired via useReducer.',
             'acceptance_criteria': 'All task mutations go through `dispatch({ type, payload })`, the '
                                    'reducer returns new state (no mutation), and behavior is unchanged from '
                                    'before the refactor.',
             'hint': '`const [tasks, dispatch] = useReducer(taskReducer, initialTasks)`. The reducer is a '
                     'pure `(state, action) => newState` switch on `action.type`. Dispatch actions from '
                     'event handlers.',
             'order': 5,
             'depends_on': 'RTASK-4'},
            {'jira_key': 'RTASK-6',
             'title': 'Persist tasks to localStorage',
             'description': 'Load tasks from localStorage on first render and save them whenever the list '
                            'changes using useEffect.',
             'acceptance_criteria': 'Reloading the page restores the exact task list, and the effect runs '
                                    'whenever tasks change (correct dependency array).',
             'hint': 'Lazy init: `useReducer(reducer, undefined, () => '
                     "JSON.parse(localStorage.getItem('tasks')) ?? initial)`. Save with `useEffect(() => "
                     "localStorage.setItem('tasks', JSON.stringify(tasks)), [tasks])`.",
             'order': 6,
             'depends_on': 'RTASK-5'}]},
 {'technology_slug': 'react',
  'title': 'Multi-Page SPA with React Router & Global State',
  'slug': 'react-router-global-state',
  'architecture_type': '2tier',
  'description': 'Turn a single-screen app into a real multi-page SPA. You will add client-side routing with '
                 'React Router, load data per-route with URL params, share state across the whole app with '
                 'Context, and guard a protected route behind an auth check. The result is a navigable app '
                 'with proper deep links and a 404 page.',
  'objectives': ['Configure client-side routing with nested routes and a shared layout',
                 'Read route params to render a dynamic detail page',
                 'Share cross-cutting state app-wide with a Context provider',
                 'Protect a route with an auth guard and redirect',
                 'Handle unmatched URLs with a 404 route and programmatic navigation'],
  'difficulty': 'intermediate',
  'estimated_hours': 5,
  'order': 3,
  'tasks': [{'jira_key': 'RROUTE-1',
             'title': 'Install and configure React Router',
             'description': 'Add react-router-dom and wrap the app in a BrowserRouter. Define routes for '
                            'Home (`/`) and Products (`/products`) rendered via <Routes>/<Route>.',
             'acceptance_criteria': 'Navigating to `/` and `/products` renders the correct page component '
                                    'without a full page reload.',
             'hint': '`npm install react-router-dom`. Wrap <App/> in <BrowserRouter> in main.jsx, then '
                     "declare `<Routes><Route path='/' element={<Home/>} /><Route path='/products' "
                     'element={<Products/>} /></Routes>`.',
             'order': 1},
            {'jira_key': 'RROUTE-2',
             'title': 'Add a shared layout with nested routes and NavLinks',
             'description': 'Create a Layout component with a nav bar (using <NavLink>) and an <Outlet>. '
                            'Nest the page routes inside the layout route so the nav persists across pages.',
             'acceptance_criteria': 'The nav bar stays mounted across navigation, and the active link is '
                                    "visually highlighted via NavLink's active state.",
             'hint': 'Make a parent `<Route element={<Layout/>}>` with child routes inside it. Layout '
                     'renders <nav> plus <Outlet/> where children appear. NavLink exposes an `isActive` flag '
                     'in its className callback.',
             'order': 2,
             'depends_on': 'RROUTE-1'},
            {'jira_key': 'RROUTE-3',
             'title': 'Build a dynamic detail route with URL params',
             'description': 'Add a route `/products/:id`. On the Products page, link each product to its '
                            'detail page; the detail page reads the id from the URL to show that product.',
             'acceptance_criteria': 'Clicking a product navigates to `/products/<id>` and the detail page '
                                    'shows the matching product; visiting the URL directly (deep link) also '
                                    'works.',
             'hint': "Declare `<Route path='/products/:id' element={<ProductDetail/>} />`. Inside "
                     'ProductDetail, `const { id } = useParams()`. Link with `<Link '
                     'to={`/products/${p.id}`}>`.',
             'order': 3,
             'depends_on': 'RROUTE-2'},
            {'jira_key': 'RROUTE-4',
             'title': 'Add global state with Context',
             'description': 'Create an AuthContext (with a `user` and `login`/`logout`) and a CartContext. '
                            'Wrap the app in the providers and consume them from the nav and pages with '
                            'useContext.',
             'acceptance_criteria': 'The nav shows login state and cart count from context, and any '
                                    'component can read/update them without prop drilling.',
             'hint': '`const AuthContext = createContext(null)`. Provide with `<AuthContext.Provider '
                     'value={{ user, login, logout }}>`. Consume with `const { user } = '
                     'useContext(AuthContext)`. Wrap providers around the router tree.',
             'order': 4,
             'depends_on': 'RROUTE-3'},
            {'jira_key': 'RROUTE-5',
             'title': 'Protect a route with an auth guard',
             'description': 'Add a `/account` route that redirects unauthenticated users to `/login`, then '
                            'bounces them back after login. Implement a RequireAuth wrapper using the '
                            'AuthContext.',
             'acceptance_criteria': 'Visiting `/account` while logged out redirects to `/login`; after '
                                    'logging in the user lands back on `/account`.',
             'hint': "RequireAuth reads `user` from context; if absent, `return <Navigate to='/login' "
                     'state={{ from: location }} replace />`. On login, `navigate(from, { replace: true })` '
                     'using useNavigate + useLocation.',
             'order': 5,
             'depends_on': 'RROUTE-4'},
            {'jira_key': 'RROUTE-6',
             'title': 'Add a 404 catch-all route',
             'description': 'Add a wildcard route that renders a NotFound page for any unmatched URL, with a '
                            'link back home.',
             'acceptance_criteria': 'Visiting a nonexistent URL (e.g. `/nope`) renders the NotFound page '
                                    'inside the layout, not a blank screen.',
             'hint': "Add `<Route path='*' element={<NotFound/>} />` as the last route. Order matters only "
                     'for the wildcard — React Router v6 otherwise picks the most specific match.',
             'order': 6,
             'depends_on': 'RROUTE-2'}]},
 {'technology_slug': 'react',
  'title': 'Storefront: Consume a REST API with Forms & Validation',
  'slug': 'react-rest-api-forms-validation',
  'architecture_type': '3tier',
  'description': 'Build the data-driven core of a storefront SPA that reads from and writes to a REST API. '
                 'You will fetch and paginate a product list, handle loading/error/empty states, cancel '
                 'stale requests, and build a validated checkout form that POSTs an order and shows '
                 'server-side field errors. The API layer is factored into a small reusable client.',
  'objectives': ['Fetch REST data with proper loading, error, and empty states',
                 'Cancel in-flight requests with AbortController to avoid race conditions',
                 'Build a controlled form with client-side validation',
                 'POST data and surface server-side validation errors on fields',
                 'Extract fetch logic into a reusable custom hook and API client'],
  'difficulty': 'intermediate',
  'estimated_hours': 6,
  'order': 4,
  'tasks': [{'jira_key': 'RSHOP-1',
             'title': 'Create a typed API client module',
             'description': 'Create src/api/client.js with helpers `getProducts()` and '
                            '`createOrder(payload)` that wrap fetch, set JSON headers, and throw on non-2xx '
                            'responses. Point at a base URL from an env var.',
             'acceptance_criteria': 'The client centralizes fetch config, throws an Error carrying the '
                                    'response status/body on non-2xx, and reads the base URL from '
                                    '`import.meta.env.VITE_API_URL`.',
             'hint': 'Wrap fetch: `if (!res.ok) throw new ApiError(res.status, await res.json())`. Vite '
                     'exposes env vars prefixed with `VITE_` on `import.meta.env`. Keep one place that knows '
                     'about headers/base URL.',
             'order': 1},
            {'jira_key': 'RSHOP-2',
             'title': 'Fetch and render the product list with all states',
             'description': 'On the products page, call getProducts() in useEffect and render loading, '
                            'error, empty, and success states distinctly.',
             'acceptance_criteria': 'The UI shows a loading indicator, then either an error message with a '
                                    'retry, an empty-state message, or the product grid — never a blank '
                                    'flash of nothing.',
             'hint': "Track `status` ('loading'|'error'|'success') plus `data` and `error`. Set loading "
                     'before the call, success/error after. Render a branch per status; an empty array is a '
                     'success with zero items.',
             'order': 2,
             'depends_on': 'RSHOP-1'},
            {'jira_key': 'RSHOP-3',
             'title': 'Add search with request cancellation',
             'description': 'Add a search box that refetches products by query. Cancel the previous '
                            "in-flight request when the query changes so a slow earlier response can't "
                            'overwrite a newer one.',
             'acceptance_criteria': 'Rapidly changing the query never renders stale results, and aborted '
                                    "requests do not set state (no 'setState on unmounted / stale request' "
                                    'warnings).',
             'hint': 'In the effect, `const ctrl = new AbortController()`, pass `signal: ctrl.signal` to '
                     'fetch, and `return () => ctrl.abort()` as cleanup. Ignore `AbortError` in the catch. '
                     'Debounce the query if desired.',
             'order': 3,
             'depends_on': 'RSHOP-2'},
            {'jira_key': 'RSHOP-4',
             'title': 'Build a controlled checkout form with client-side validation',
             'description': 'Create a checkout form with name, email, and address fields. Validate on '
                            'blur/submit: required fields, valid email format. Block submission and show '
                            'inline messages when invalid.',
             'acceptance_criteria': 'Submitting with an empty required field or a malformed email shows a '
                                    'specific inline error next to that field and prevents the network call.',
             'hint': 'Keep values and errors in state objects keyed by field name. Validate in an `onSubmit` '
                     'that calls `e.preventDefault()` first. Use a simple email regex and render '
                     '`errors.email` under the input when present.',
             'order': 4,
             'depends_on': 'RSHOP-1'},
            {'jira_key': 'RSHOP-5',
             'title': 'Submit the order and map server-side errors to fields',
             'description': 'On valid submit, POST the order via createOrder(). Show a submitting state, a '
                            'success confirmation on 201, and map 422 field errors from the response body '
                            'back onto the form.',
             'acceptance_criteria': 'A successful POST shows a confirmation; a 422 validation response '
                                    'populates the matching field errors; the submit button is disabled '
                                    'while the request is in flight.',
             'hint': 'Catch the ApiError from RSHOP-1: if `err.status === 422`, merge `err.body.errors` '
                     "(e.g. `{ email: 'already used' }`) into your errors state. Disable submit with a "
                     '`submitting` boolean toggled around the await.',
             'order': 5,
             'depends_on': 'RSHOP-4'},
            {'jira_key': 'RSHOP-6',
             'title': 'Extract fetching into a reusable useFetch hook',
             'description': 'Refactor the product-fetching logic into a custom hook `useFetch(fetcher, '
                            'deps)` that returns `{ status, data, error, refetch }` and handles cancellation '
                            'internally. Use it on the products page.',
             'acceptance_criteria': 'The products page uses the hook instead of inline effect code, '
                                    'cancellation still works, and the hook is generic enough to reuse for '
                                    'another endpoint.',
             'hint': 'A custom hook is a function starting with `use` that calls other hooks. Move the '
                     'useEffect + AbortController + status state inside it. Return a `refetch` that re-runs '
                     'the fetcher for the error-state retry button.',
             'order': 6,
             'depends_on': 'RSHOP-3'}]},
 {'technology_slug': 'react',
  'title': 'Ship a Tested Component Library & Analytics Dashboard',
  'slug': 'react-component-library-testing',
  'architecture_type': 'cicd',
  'description': 'Build a reusable component library and an analytics dashboard that consumes it, then lock '
                 'quality in with a full testing setup. You will design accessible components, cover them '
                 'with Vitest + React Testing Library unit tests, add MSW-mocked integration tests for data '
                 'flows, optimize with memoization and code splitting, and gate everything behind a CI '
                 'pipeline.',
  'objectives': ['Design reusable, accessible components with variant props',
                 'Unit test components with Vitest and React Testing Library by behavior',
                 'Mock the network with MSW to integration-test data-driven views',
                 'Optimize renders with memoization and route-based code splitting',
                 'Enforce lint, test, and coverage gates in a CI pipeline'],
  'difficulty': 'advanced',
  'estimated_hours': 8,
  'order': 5,
  'tasks': [{'jira_key': 'RDASH-1',
             'title': 'Build a reusable, accessible Button and Modal',
             'description': 'Create a components/ui library with a Button (variant + size props) and a Modal '
                            '(focus trap, Escape-to-close, aria attributes). Render them on a demo page.',
             'acceptance_criteria': 'Button renders correct classes per variant/size; Modal traps focus, '
                                    "closes on Escape, sets `role='dialog'` and `aria-modal='true'`, and "
                                    'returns focus to the trigger on close.',
             'hint': 'Drive Button styles from a `variant`/`size` prop map. For Modal, render via a portal, '
                     'add a keydown listener for Escape, and move focus into the dialog on open (store the '
                     'previously focused element to restore it).',
             'order': 1},
            {'jira_key': 'RDASH-2',
             'title': 'Set up Vitest + React Testing Library',
             'description': 'Install and configure Vitest with jsdom and React Testing Library. Add a test '
                            'script and a setup file wiring jest-dom matchers.',
             'acceptance_criteria': '`npm test` runs Vitest in jsdom, a trivial smoke test passes, and '
                                    '`toBeInTheDocument()` matchers are available globally.',
             'hint': '`npm i -D vitest @testing-library/react @testing-library/jest-dom jsdom`. Set `test: { '
                     "environment: 'jsdom', setupFiles: './src/test/setup.js', globals: true }` in "
                     "vite.config.js and import '@testing-library/jest-dom' in the setup file.",
             'order': 2,
             'depends_on': 'RDASH-1'},
            {'jira_key': 'RDASH-3',
             'title': 'Unit test the components by behavior',
             'description': 'Write tests for Button (renders label, fires onClick, disabled blocks clicks) '
                            'and Modal (opens, Escape closes, focus is trapped). Query by role/text, not by '
                            'class names.',
             'acceptance_criteria': 'Tests use `getByRole`/`getByText` and userEvent, assert user-visible '
                                    'behavior rather than implementation details, and all pass.',
             'hint': '`render(<Button onClick={fn}>Save</Button>)`, then `await '
                     "userEvent.click(screen.getByRole('button', { name: /save/i }))` and "
                     '`expect(fn).toHaveBeenCalled()`. Prefer role queries so tests mirror how users and '
                     'assistive tech find elements.',
             'order': 3,
             'depends_on': 'RDASH-2'},
            {'jira_key': 'RDASH-4',
             'title': 'Integration-test a data view with MSW',
             'description': 'Build a dashboard StatsPanel that fetches metrics from a REST endpoint using '
                            'the library components. Add Mock Service Worker handlers and write a test '
                            'covering loading -> data and the error path.',
             'acceptance_criteria': 'MSW intercepts the fetch in tests; one test asserts the loading state '
                                    'then the rendered metrics, and another forces a 500 and asserts the '
                                    'error UI — with no real network calls.',
             'hint': "`npm i -D msw`. Define `http.get('/api/metrics', () => HttpResponse.json({...}))`, "
                     'start the server in setup (`beforeAll(() => server.listen())`). Override with an error '
                     'handler per-test using `server.use(...)`. Assert with `findBy*` for async UI.',
             'order': 4,
             'depends_on': 'RDASH-3'},
            {'jira_key': 'RDASH-5',
             'title': 'Optimize renders and split the bundle',
             'description': 'Profile the dashboard, memoize an expensive list/chart with React.memo + '
                            'useMemo, stabilize callbacks with useCallback, and lazy-load the heaviest route '
                            'with React.lazy + Suspense.',
             'acceptance_criteria': 'Unnecessary re-renders of the memoized component are eliminated '
                                    '(verified via React DevTools Profiler), and the heavy route ships in a '
                                    'separate chunk visible in the `vite build` output.',
             'hint': 'Wrap the pure child in `React.memo`, compute derived data with `useMemo(() => ..., '
                     '[deps])`, and pass stable handlers via `useCallback`. Split routes: `const Reports = '
                     "React.lazy(() => import('./Reports'))` inside <Suspense fallback={...}>.",
             'order': 5,
             'depends_on': 'RDASH-4'},
            {'jira_key': 'RDASH-6',
             'title': 'Gate quality in CI',
             'description': 'Add a GitHub Actions workflow that installs deps, runs the linter, runs the '
                            'test suite with coverage, and builds the app on every push/PR. Fail the job if '
                            'any step fails or coverage drops below a threshold.',
             'acceptance_criteria': 'The workflow runs on push/PR, executes lint + `vitest run --coverage` + '
                                    '`vite build`, and the job goes red when a test fails or coverage is '
                                    'under the configured threshold.',
             'hint': 'In .github/workflows/ci.yml use `actions/setup-node` with a Node version and cache, '
                     'then steps `npm ci`, `npm run lint`, `npm run test -- --coverage`, `npm run build`. '
                     'Set coverage thresholds under `test.coverage.thresholds` in the Vitest config so a '
                     'shortfall exits non-zero.',
             'order': 6,
             'depends_on': 'RDASH-5'}]},
 {'technology_slug': 'nodejs',
  'title': 'First Express API: Routing, JSON, and Health Checks',
  'slug': 'nodejs-express-first-rest-api',
  'architecture_type': '2tier',
  'description': 'Bootstrap a Node.js project from scratch and build your first Express server that serves '
                 'JSON over HTTP. You will define REST routes for an in-memory `tasks` resource, parse '
                 'request bodies, and expose a health endpoint the way production services do.',
  'objectives': ['Initialize a Node.js project with npm and install Express',
                 'Create an Express app with a listening HTTP server',
                 'Implement CRUD routes for a resource using an Express Router',
                 'Parse and return JSON request/response bodies with correct status codes',
                 'Add a /health endpoint and run the server with nodemon for live reload'],
  'difficulty': 'beginner',
  'estimated_hours': 3,
  'order': 1,
  'tasks': [{'jira_key': 'EXP-1',
             'title': 'Initialize the Node project and install Express',
             'description': 'Create a new project directory, generate a package.json, and install Express as '
                            'a dependency. Set the package `type` so you can choose CommonJS or ESM '
                            'consistently.',
             'acceptance_criteria': '`package.json` exists with `express` under `dependencies`, and `node -e '
                                    '"require(\'express\')"` runs without error.',
             'hint': 'Run `npm init -y`, then `npm install express`. Confirm the version with `npm ls '
                     'express`.',
             'order': 1},
            {'jira_key': 'EXP-2',
             'title': 'Create a minimal Express server',
             'description': 'Create `src/app.js` that builds an Express app and `src/server.js` that starts '
                            'it listening on `process.env.PORT || 3000`. Log the bound port on startup.',
             'acceptance_criteria': '`node src/server.js` starts and logs the port; `curl localhost:3000/` '
                                    'returns an HTTP response (any status is fine at this stage).',
             'hint': "In app.js: `const express = require('express'); const app = express(); module.exports "
                     '= app;`. In server.js: `app.listen(port, () => console.log(...))`.',
             'order': 2,
             'depends_on': 'EXP-1'},
            {'jira_key': 'EXP-3',
             'title': 'Add JSON body parsing and a health endpoint',
             'description': 'Register the built-in `express.json()` middleware so the app can read JSON '
                            "request bodies. Add a `GET /health` route that returns `{ status: 'ok', uptime: "
                            'process.uptime() }`.',
             'acceptance_criteria': '`curl localhost:3000/health` returns 200 with a JSON body containing '
                                    '`"status":"ok"`.',
             'hint': 'Add `app.use(express.json())` before your routes. Return JSON with `res.json({ status: '
                     "'ok', uptime: process.uptime() })`.",
             'order': 3,
             'depends_on': 'EXP-2'},
            {'jira_key': 'EXP-4',
             'title': 'Build a tasks router with GET and POST',
             'description': 'Create `src/routes/tasks.js` using `express.Router()`. Back it with an '
                            'in-memory array. Implement `GET /tasks` (list) and `POST /tasks` (create, '
                            'returning 201 with the new record including a generated id).',
             'acceptance_criteria': '`POST /tasks` with `{"title":"Buy milk"}` returns 201 and the created '
                                    'object; a following `GET /tasks` includes it.',
             'hint': "Mount with `app.use('/tasks', require('./routes/tasks'))`. Generate ids with a counter "
                     'or `crypto.randomUUID()`. Use `res.status(201).json(task)`.',
             'order': 4,
             'depends_on': 'EXP-3'},
            {'jira_key': 'EXP-5',
             'title': 'Add GET-by-id, PUT, and DELETE with correct status codes',
             'description': 'Extend the tasks router with `GET /tasks/:id`, `PUT /tasks/:id`, and `DELETE '
                            '/tasks/:id`. Return 404 when the id does not exist and 204 on successful '
                            'delete.',
             'acceptance_criteria': '`GET /tasks/<unknown-id>` returns 404; `DELETE /tasks/<id>` returns 204 '
                                    'and the item no longer appears in `GET /tasks`.',
             'hint': 'Read the id via `req.params.id`. Use `Array.prototype.find` / `findIndex`. Return '
                     "`res.status(404).json({ error: 'Not found' })` when missing.",
             'order': 5,
             'depends_on': 'EXP-4'},
            {'jira_key': 'EXP-6',
             'title': 'Add dev scripts and nodemon for live reload',
             'description': 'Install `nodemon` as a dev dependency and add `start` and `dev` scripts to '
                            'package.json so the server restarts automatically on file changes.',
             'acceptance_criteria': '`npm run dev` starts the server via nodemon; editing a route file '
                                    'triggers an automatic restart in the terminal.',
             'hint': '`npm install --save-dev nodemon`, then set `"scripts": { "start": "node '
                     'src/server.js", "dev": "nodemon src/server.js" }`.',
             'order': 6,
             'depends_on': 'EXP-5'}]},
 {'technology_slug': 'nodejs',
  'title': 'Validation and Error Handling for an Express API',
  'slug': 'nodejs-validation-error-handling',
  'architecture_type': '2tier',
  'description': 'Take a working Express API and make it robust. You will validate incoming request bodies, '
                 'centralize error handling with a single middleware, return consistent RFC-style error '
                 'payloads, and add security and logging middleware that every real API needs.',
  'objectives': ['Validate request bodies and params using a schema library (Zod or Joi)',
                 'Return consistent, structured JSON error responses with correct HTTP codes',
                 'Centralize error handling in a single Express error middleware',
                 'Add async route wrapping so rejected promises are not swallowed',
                 'Harden the API with helmet, CORS, and request logging middleware'],
  'difficulty': 'beginner',
  'estimated_hours': 4,
  'order': 2,
  'tasks': [{'jira_key': 'VALERR-1',
             'title': 'Install a validation library and define a schema',
             'description': 'Install Zod (or Joi) and create `src/schemas/task.js` describing a valid task: '
                            '`title` is a required non-empty string, `priority` is an optional enum of '
                            '`low|medium|high`.',
             'acceptance_criteria': "Importing the schema and calling `.parse({ title: '' })` throws a "
                                    "validation error, while `.parse({ title: 'x' })` succeeds.",
             'hint': '`npm install zod`. Define `z.object({ title: z.string().min(1), priority: '
                     "z.enum(['low','medium','high']).optional() })`.",
             'order': 1},
            {'jira_key': 'VALERR-2',
             'title': 'Create a reusable validation middleware',
             'description': 'Write `src/middleware/validate.js` that takes a schema and validates '
                            '`req.body`, replacing it with the parsed value. On failure it should forward a '
                            '400 error via `next(err)` rather than throwing.',
             'acceptance_criteria': '`POST /tasks` with an empty title returns 400 and does NOT create a '
                                    'record; a valid body still creates a 201.',
             'hint': 'Return a closure: `const validate = (schema) => (req, res, next) => { const r = '
                     'schema.safeParse(req.body); if (!r.success) return next(new ValidationError(r.error)); '
                     'req.body = r.data; next(); }`.',
             'order': 2,
             'depends_on': 'VALERR-1'},
            {'jira_key': 'VALERR-3',
             'title': 'Define a typed error class and a 404 fallthrough',
             'description': 'Create an `AppError` class carrying `statusCode` and a machine-readable `code`. '
                            'Add a catch-all middleware after all routes that produces a 404 for unmatched '
                            'paths.',
             'acceptance_criteria': '`curl localhost:3000/does-not-exist` returns 404 with a JSON body like '
                                    '`{ "error": { "code": "NOT_FOUND" } }`.',
             'hint': "`class AppError extends Error { constructor(msg, statusCode=500, code='INTERNAL') "
                     "{...} }`. Add `app.use((req,res,next) => next(new AppError('Not found', 404, "
                     "'NOT_FOUND')))` after routes.",
             'order': 3,
             'depends_on': 'VALERR-2'},
            {'jira_key': 'VALERR-4',
             'title': 'Add a centralized error-handling middleware',
             'description': 'Register a 4-argument Express error middleware (`(err, req, res, next)`) as the '
                            'LAST middleware. Map known errors to their status and hide stack traces in '
                            'production, logging them server-side.',
             'acceptance_criteria': 'All error responses share one shape `{ error: { code, message } }`; a '
                                    'thrown 500 does not leak a stack trace in the HTTP body.',
             'hint': 'Express identifies error middleware by its 4 arguments. Read `err.statusCode || 500`. '
                     "Only include `err.stack` in the body when `process.env.NODE_ENV !== 'production'`.",
             'order': 4,
             'depends_on': 'VALERR-3'},
            {'jira_key': 'VALERR-5',
             'title': 'Wrap async handlers so rejections reach the error middleware',
             'description': 'Create an `asyncHandler` wrapper so that rejected promises in async route '
                            'handlers are passed to `next()` instead of crashing or hanging the request.',
             'acceptance_criteria': 'An async route that throws returns a proper JSON error response (not a '
                                    'hung request or an unhandled rejection in the logs).',
             'hint': '`const asyncHandler = (fn) => (req, res, next) => Promise.resolve(fn(req, res, '
                     'next)).catch(next);` then wrap each async handler with it.',
             'order': 5,
             'depends_on': 'VALERR-4'},
            {'jira_key': 'VALERR-6',
             'title': 'Add helmet, CORS, and request logging',
             'description': 'Install and register `helmet` for secure headers, `cors` with an explicit '
                            'allowed origin, and `morgan` (or pino-http) for request logging.',
             'acceptance_criteria': 'Response headers include '
                                    '`X-DNS-Prefetch-Control`/`X-Content-Type-Options` from helmet; each '
                                    'request prints a log line with method, path, and status.',
             'hint': '`npm install helmet cors morgan`. Register early: `app.use(helmet()); app.use(cors({ '
                     "origin: process.env.CORS_ORIGIN })); app.use(morgan('combined'));`.",
             'order': 6,
             'depends_on': 'VALERR-5'}]},
 {'technology_slug': 'nodejs',
  'title': 'Persist Data with PostgreSQL and Migrations',
  'slug': 'nodejs-postgres-persistence',
  'architecture_type': '3tier',
  'description': 'Replace the in-memory store with a real PostgreSQL database. You will run Postgres, manage '
                 'a connection pool, write versioned SQL migrations, and refactor your routes into a '
                 'repository layer that uses parameterized queries to avoid SQL injection.',
  'objectives': ['Connect Node.js to PostgreSQL using the pg connection pool',
                 'Design a schema and manage it with versioned SQL migrations',
                 'Refactor routes into a repository/service layer backed by SQL',
                 'Use parameterized queries to prevent SQL injection',
                 'Handle pool lifecycle, transactions, and graceful shutdown'],
  'difficulty': 'intermediate',
  'estimated_hours': 5,
  'order': 3,
  'tasks': [{'jira_key': 'PGDB-1',
             'title': 'Run PostgreSQL and store the connection URL in env',
             'description': 'Start a PostgreSQL 15 instance and create a database `taskapi`. Store the '
                            'connection string in a `.env` file loaded via `dotenv`, and ensure `.env` is '
                            'gitignored.',
             'acceptance_criteria': '`psql "$DATABASE_URL" -c \'SELECT 1\'` succeeds and `.env` appears in '
                                    '`.gitignore`.',
             'hint': 'Use Docker: `docker run -d --name pg -e POSTGRES_PASSWORD=pass -e POSTGRES_DB=taskapi '
                     '-p 5432:5432 postgres:15`. Set '
                     '`DATABASE_URL=postgres://postgres:pass@localhost:5432/taskapi`.',
             'order': 1},
            {'jira_key': 'PGDB-2',
             'title': 'Create a pooled pg client module',
             'description': 'Install `pg` and `dotenv`. Create `src/db/pool.js` that exports a shared `Pool` '
                            'configured from `DATABASE_URL`, plus a `query(text, params)` helper.',
             'acceptance_criteria': "A quick script calling `query('SELECT NOW()')` prints the current "
                                    'timestamp from the database.',
             'hint': "`npm install pg dotenv`. `const { Pool } = require('pg'); const pool = new Pool({ "
                     'connectionString: process.env.DATABASE_URL }); module.exports = { query: (t,p) => '
                     'pool.query(t,p), pool };`.',
             'order': 2,
             'depends_on': 'PGDB-1'},
            {'jira_key': 'PGDB-3',
             'title': 'Write the first migration to create the tasks table',
             'description': 'Add a migration tool (node-pg-migrate or a simple numbered .sql runner) and '
                            'write a migration creating a `tasks` table with `id` (uuid/serial), `title`, '
                            '`priority`, `done`, and `created_at`.',
             'acceptance_criteria': 'Running the migrate command creates the `tasks` table; `\\d tasks` in '
                                    'psql shows all columns.',
             'hint': '`npm install node-pg-migrate`. Add script `"migrate": "node-pg-migrate"`. Use '
                     "`pgm.createTable('tasks', { id: 'id', title: { type: 'text', notNull: true }, ... })`.",
             'order': 3,
             'depends_on': 'PGDB-2'},
            {'jira_key': 'PGDB-4',
             'title': 'Build a tasks repository with parameterized queries',
             'description': 'Create `src/repositories/tasksRepo.js` with `list`, `getById`, `create`, '
                            '`update`, and `remove` functions that use parameterized SQL ($1, $2 '
                            'placeholders) exclusively.',
             'acceptance_criteria': "A malicious title like `Robert'); DROP TABLE tasks;--` is stored "
                                    'verbatim as data and the table still exists afterward.',
             'hint': "Never string-concat SQL. Use `query('INSERT INTO tasks(title, priority) VALUES ($1, "
                     "$2) RETURNING *', [title, priority])` and return `rows[0]`.",
             'order': 4,
             'depends_on': 'PGDB-3'},
            {'jira_key': 'PGDB-5',
             'title': 'Wire the routes to the repository',
             'description': 'Refactor the tasks routes to call the repository instead of the in-memory '
                            "array. Map 'not found' repository results to 404s using the existing "
                            'error-handling middleware.',
             'acceptance_criteria': 'Full CRUD works against the database and data survives a server restart '
                                    '(`GET /tasks` returns previously created rows).',
             'hint': 'In each async handler, `const task = await tasksRepo.getById(req.params.id); if '
                     "(!task) return next(new AppError('Not found', 404, 'NOT_FOUND'));`.",
             'order': 5,
             'depends_on': 'PGDB-4'},
            {'jira_key': 'PGDB-6',
             'title': 'Add a transaction and graceful shutdown',
             'description': 'Add one operation that uses a transaction (e.g. bulk-create tasks atomically) '
                            'via a checked-out client. On SIGTERM/SIGINT, drain the pool with `pool.end()` '
                            'before exiting.',
             'acceptance_criteria': 'If the bulk operation fails midway, no partial rows are committed; '
                                    'pressing Ctrl-C logs a clean shutdown and closes the pool.',
             'hint': "`const client = await pool.connect(); try { await client.query('BEGIN'); ...; await "
                     "client.query('COMMIT'); } catch(e){ await client.query('ROLLBACK'); throw e; } finally "
                     "{ client.release(); }`. Handle `process.on('SIGTERM', ...)`.",
             'order': 6,
             'depends_on': 'PGDB-5'}]},
 {'technology_slug': 'nodejs',
  'title': 'JWT Authentication and Role-Based Authorization',
  'slug': 'nodejs-jwt-auth-rbac',
  'architecture_type': '3tier',
  'description': 'Add secure authentication to your API. You will hash passwords with bcrypt, issue and '
                 'verify JWTs, protect routes with auth middleware, and implement role-based access control '
                 'plus refresh-token rotation the way production APIs do.',
  'objectives': ['Store users with bcrypt-hashed passwords, never plaintext',
                 'Issue signed JWT access tokens on login and verify them on protected routes',
                 'Build auth middleware that populates req.user from the bearer token',
                 'Enforce role-based authorization (e.g. admin-only endpoints)',
                 'Implement refresh tokens and rate-limit the login endpoint'],
  'difficulty': 'intermediate',
  'estimated_hours': 6,
  'order': 4,
  'tasks': [{'jira_key': 'AUTH-1',
             'title': 'Add a users table and register endpoint with bcrypt',
             'description': "Create a `users` table (email unique, password_hash, role default 'user'). "
                            'Build `POST /auth/register` that hashes the password with bcrypt and stores the '
                            'user, returning 201 without the hash.',
             'acceptance_criteria': 'Registering returns 201 with `{ id, email, role }` and NO password '
                                    'field; the stored `password_hash` is a bcrypt string starting with '
                                    '`$2`.',
             'hint': '`npm install bcrypt`. `const hash = await bcrypt.hash(password, 12);`. Select only '
                     'safe columns when returning the user.',
             'order': 1},
            {'jira_key': 'AUTH-2',
             'title': 'Implement login and issue a JWT access token',
             'description': 'Build `POST /auth/login` that verifies the password with `bcrypt.compare` and, '
                            'on success, signs a JWT containing `sub` (user id) and `role`, expiring in 15 '
                            'minutes. Use a secret from env.',
             'acceptance_criteria': 'Login with correct credentials returns 200 and a JWT; wrong password '
                                    'returns 401 with a generic message.',
             'hint': '`npm install jsonwebtoken`. `jwt.sign({ sub: user.id, role: user.role }, '
                     "process.env.JWT_SECRET, { expiresIn: '15m' })`. Keep the 401 message generic to avoid "
                     'user enumeration.',
             'order': 2,
             'depends_on': 'AUTH-1'},
            {'jira_key': 'AUTH-3',
             'title': 'Create JWT verification middleware',
             'description': 'Write `src/middleware/auth.js` that reads the `Authorization: Bearer <token>` '
                            'header, verifies the JWT, and sets `req.user`. Reject missing or invalid tokens '
                            'with 401.',
             'acceptance_criteria': 'A protected route returns 401 without a token and 200 with a valid '
                                    'token; an expired token returns 401.',
             'hint': 'Split the header on space to get the token. `jwt.verify(token, '
                     'process.env.JWT_SECRET)` throws on invalid/expired — catch it and return 401. Set '
                     '`req.user = payload`.',
             'order': 3,
             'depends_on': 'AUTH-2'},
            {'jira_key': 'AUTH-4',
             'title': 'Protect the tasks routes and scope data to the owner',
             'description': 'Require authentication on all `/tasks` routes. Add an `owner_id` column and '
                            'ensure users only see and modify their own tasks by filtering queries on '
                            '`req.user.sub`.',
             'acceptance_criteria': "User A cannot read or delete User B's task (returns 404/403); each "
                                    "user's `GET /tasks` shows only their own rows.",
             'hint': "Mount the middleware: `app.use('/tasks', auth, tasksRouter)`. Add `WHERE owner_id = "
                     '$1` with `req.user.sub` to every repository query.',
             'order': 4,
             'depends_on': 'AUTH-3'},
            {'jira_key': 'AUTH-5',
             'title': 'Add role-based authorization for admin endpoints',
             'description': "Create a `requireRole('admin')` middleware and add an admin-only endpoint (e.g. "
                            '`GET /admin/users` listing all users). Non-admins must be rejected.',
             'acceptance_criteria': 'A user token gets 403 on `GET /admin/users`; an admin token gets 200 '
                                    'with the user list.',
             'hint': '`const requireRole = (role) => (req, res, next) => req.user?.role === role ? next() : '
                     "next(new AppError('Forbidden', 403, 'FORBIDDEN'));`. Chain after `auth`.",
             'order': 5,
             'depends_on': 'AUTH-4'},
            {'jira_key': 'AUTH-6',
             'title': 'Add refresh tokens and rate-limit login',
             'description': 'Issue a longer-lived refresh token stored server-side, add `POST /auth/refresh` '
                            'to mint a new access token, and apply `express-rate-limit` to the login route '
                            'to blunt brute-force attempts.',
             'acceptance_criteria': '`/auth/refresh` returns a new access token for a valid refresh token; '
                                    'more than N rapid logins from one IP return 429.',
             'hint': '`npm install express-rate-limit`. Store refresh tokens (hashed) in a table so they can '
                     'be revoked. `rateLimit({ windowMs: 15*60*1000, max: 10 })` on `/auth/login`.',
             'order': 6,
             'depends_on': 'AUTH-5'}]},
 {'technology_slug': 'nodejs',
  'title': 'Test and Dockerize a Production-Ready API with CI',
  'slug': 'nodejs-testing-docker-cicd',
  'architecture_type': 'cicd',
  'description': 'Turn your API into a shippable, tested artifact. You will write unit and HTTP integration '
                 'tests with Jest and Supertest, add coverage gates, containerize the app with a multi-stage '
                 'Dockerfile, run it alongside Postgres via docker-compose, and wire a GitHub Actions '
                 'pipeline that tests and builds on every push.',
  'objectives': ['Write unit tests and HTTP integration tests with Jest and Supertest',
                 'Isolate tests with a throwaway database and enforce a coverage threshold',
                 'Build a small, secure multi-stage Docker image for the API',
                 'Orchestrate the API and PostgreSQL with docker-compose',
                 'Automate test-and-build in a GitHub Actions CI pipeline'],
  'difficulty': 'advanced',
  'estimated_hours': 7,
  'order': 5,
  'tasks': [{'jira_key': 'SHIP-1',
             'title': 'Set up Jest and write unit tests for validation logic',
             'description': 'Install Jest, configure it in package.json, and write unit tests for pure logic '
                            'such as the task validation schema and the auth role check. Add a `test` '
                            'script.',
             'acceptance_criteria': '`npm test` runs Jest and passes with at least 5 unit assertions across '
                                    'the validation and role-check modules.',
             'hint': '`npm install --save-dev jest`. Set `"test": "jest"`. Name files `*.test.js`; assert '
                     'with `expect(schema.safeParse({}).success).toBe(false)`.',
             'order': 1},
            {'jira_key': 'SHIP-2',
             'title': 'Add Supertest HTTP integration tests against the app',
             'description': 'Install Supertest and test the real Express app (exported without calling '
                            'listen) end-to-end: register, login, create a task, and fetch it with the '
                            'returned token.',
             'acceptance_criteria': '`npm test` includes an integration suite where '
                                    "`request(app).post('/auth/login')` returns 200 and a subsequent "
                                    'authorized `GET /tasks` returns the created task.',
             'hint': '`npm install --save-dev supertest`. Import the app (not server.js): `const request = '
                     "require('supertest'); await request(app).post('/tasks').set('Authorization', ...)`.",
             'order': 2,
             'depends_on': 'SHIP-1'},
            {'jira_key': 'SHIP-3',
             'title': 'Isolate the test database and enforce coverage',
             'description': 'Point tests at a separate test database via `DATABASE_URL`, run migrations and '
                            'truncate tables between tests, and configure a Jest coverage threshold that '
                            'fails the build below the bar.',
             'acceptance_criteria': '`npm test -- --coverage` fails if coverage drops below the configured '
                                    'threshold (e.g. 70%) and tests do not pollute the dev database.',
             'hint': 'Use a `.env.test` and set `NODE_ENV=test`. In `beforeEach`, `TRUNCATE tasks, users '
                     'RESTART IDENTITY CASCADE`. Add `coverageThreshold: { global: { lines: 70 } }` to Jest '
                     'config.',
             'order': 3,
             'depends_on': 'SHIP-2'},
            {'jira_key': 'SHIP-4',
             'title': 'Write a multi-stage Dockerfile for the API',
             'description': 'Create a Dockerfile with a build stage that installs all deps and a slim '
                            'runtime stage that copies only production node_modules and source, runs as a '
                            'non-root user, and starts the server.',
             'acceptance_criteria': '`docker build -t task-api .` succeeds and `docker run -p 3000:3000 '
                                    '--env-file .env task-api` serves `GET /health` with 200.',
             'hint': 'Base on `node:20-alpine`. Stage 1: `npm ci` then copy source. Stage 2: `npm ci '
                     '--omit=dev`, `USER node`, `CMD ["node", "src/server.js"]`. Add a `.dockerignore` with '
                     '`node_modules`.',
             'order': 4,
             'depends_on': 'SHIP-3'},
            {'jira_key': 'SHIP-5',
             'title': 'Compose the API with PostgreSQL',
             'description': 'Write a `docker-compose.yml` defining a `db` (postgres:15) service with a '
                            'volume and healthcheck, and an `api` service that depends on it and runs '
                            'migrations on startup.',
             'acceptance_criteria': '`docker compose up` brings up both services; the API becomes reachable '
                                    'once the DB healthcheck passes, and `curl localhost:3000/tasks` returns '
                                    '200/401 (not a connection error).',
             'hint': 'Use `depends_on: { db: { condition: service_healthy } }` and a Postgres `healthcheck` '
                     'running `pg_isready`. Run migrations in an entrypoint before starting the server.',
             'order': 5,
             'depends_on': 'SHIP-4'},
            {'jira_key': 'SHIP-6',
             'title': 'Add a GitHub Actions CI pipeline',
             'description': 'Create `.github/workflows/ci.yml` that installs dependencies, spins up a '
                            'Postgres service container, runs migrations and the full test suite, and builds '
                            'the Docker image on every push and PR.',
             'acceptance_criteria': 'The workflow runs on push, the test job passes against the CI Postgres '
                                    'service, and the Docker build step completes green in the Actions tab.',
             'hint': 'Use `services: postgres:` in the job with health-check options, '
                     '`actions/setup-node@v4` with `cache: npm`, then `npm ci`, `npm test`, and `docker '
                     'build .`.',
             'order': 6,
             'depends_on': 'SHIP-5'}]},
 {'technology_slug': 'ai-ml',
  'title': 'Build Your First ML Model: Tabular Classification with scikit-learn',
  'slug': 'ai-ml-tabular-classification-sklearn',
  'architecture_type': 'custom',
  'description': 'Take a raw tabular dataset (Titanic-style survival data) from CSV to a trained, evaluated '
                 'scikit-learn classifier. You will clean the data, engineer features inside a reusable '
                 'Pipeline, train logistic regression, and interpret proper classification metrics instead '
                 'of accuracy alone.',
  'objectives': ['Load and inspect a tabular dataset with pandas and diagnose missing values',
                 'Build a preprocessing + model Pipeline with ColumnTransformer to prevent leakage',
                 'Train a LogisticRegression classifier and generate predictions',
                 'Evaluate with precision, recall, F1, and a confusion matrix rather than accuracy alone',
                 'Persist the trained pipeline to disk with joblib for reuse'],
  'difficulty': 'beginner',
  'estimated_hours': 3,
  'order': 1,
  'tasks': [{'jira_key': 'CLF-1',
             'title': 'Load the dataset and run exploratory checks',
             'description': 'Read data/titanic.csv into a pandas DataFrame. Print df.shape, df.info(), '
                            "df.describe(include='all'), and the per-column null counts so you understand "
                            'the data before modeling.',
             'acceptance_criteria': 'A load_data.py script prints the row/column count, dtypes, and a '
                                    "null-count table. The 'Survived' target column is identified and its "
                                    'class balance (value_counts) is printed.',
             'hint': "import pandas as pd; df = pd.read_csv('data/titanic.csv'); print(df.isna().sum()); "
                     "print(df['Survived'].value_counts(normalize=True)). Note that Age and Cabin have many "
                     'nulls.',
             'order': 1},
            {'jira_key': 'CLF-2',
             'title': 'Split into train and test sets with stratification',
             'description': 'Separate features (X) from the target (y). Use train_test_split with '
                            'test_size=0.2, random_state=42, and stratify=y so the class balance is '
                            'preserved in both splits.',
             'acceptance_criteria': 'X_train, X_test, y_train, y_test exist. The positive-class ratio in '
                                    'y_train and y_test differ by less than 0.02, confirming stratification '
                                    'worked.',
             'hint': 'from sklearn.model_selection import train_test_split; X_train, X_test, y_train, y_test '
                     '= train_test_split(X, y, test_size=0.2, stratify=y, random_state=42). Never fit any '
                     'transformer before this split.',
             'order': 2,
             'depends_on': 'CLF-1'},
            {'jira_key': 'CLF-3',
             'title': 'Build a preprocessing ColumnTransformer',
             'description': 'Create a ColumnTransformer that imputes numeric columns (Age, Fare) with the '
                            'median and scales them with StandardScaler, and imputes categorical columns '
                            '(Sex, Embarked, Pclass) with the most-frequent value then one-hot encodes them.',
             'acceptance_criteria': 'preprocess.fit_transform(X_train) returns a matrix with no NaNs and '
                                    'expanded one-hot columns. Fitting on X_train only (not the full '
                                    'dataset) is verifiable in the code.',
             'hint': "Use SimpleImputer(strategy='median') + StandardScaler in a numeric Pipeline, "
                     "SimpleImputer(strategy='most_frequent') + OneHotEncoder(handle_unknown='ignore') for "
                     'categoricals, then combine with ColumnTransformer([...]).',
             'order': 3,
             'depends_on': 'CLF-2'},
            {'jira_key': 'CLF-4',
             'title': 'Assemble and train the model Pipeline',
             'description': 'Wrap the ColumnTransformer and a LogisticRegression(max_iter=1000) into a '
                            'single sklearn Pipeline and call fit(X_train, y_train). This guarantees '
                            'preprocessing is refit on each training fold and applied identically at '
                            'inference.',
             'acceptance_criteria': 'pipe.fit(X_train, y_train) completes without convergence warnings and '
                                    'pipe.predict(X_test) returns an array of length len(X_test).',
             'hint': "from sklearn.pipeline import Pipeline; pipe = Pipeline([('prep', preprocess), ('clf', "
                     'LogisticRegression(max_iter=1000))]); pipe.fit(X_train, y_train). If it fails to '
                     'converge, confirm scaling is inside the pipeline.',
             'order': 4,
             'depends_on': 'CLF-3'},
            {'jira_key': 'CLF-5',
             'title': 'Evaluate with a full classification report',
             'description': 'Generate predictions on X_test and print classification_report '
                            '(precision/recall/F1) plus a confusion_matrix. Explain in a comment why '
                            'accuracy is misleading on an imbalanced target.',
             'acceptance_criteria': 'The classification_report prints per-class precision, recall, and F1; '
                                    'the confusion matrix is a 2x2 array. A comment states the '
                                    'minority-class recall value.',
             'hint': 'from sklearn.metrics import classification_report, confusion_matrix; '
                     'print(classification_report(y_test, pipe.predict(X_test))). Watch the recall on the '
                     'survived=1 class, not just overall accuracy.',
             'order': 5,
             'depends_on': 'CLF-4'},
            {'jira_key': 'CLF-6',
             'title': 'Persist the trained pipeline to disk',
             'description': 'Save the fitted pipeline to models/titanic_clf.joblib with joblib.dump, then '
                            'reload it in a fresh process and confirm predictions match. This is the '
                            'artifact you will serve in later projects.',
             'acceptance_criteria': 'models/titanic_clf.joblib exists; loading it and calling predict on the '
                                    'first 5 rows of X_test yields identical output to the in-memory '
                                    'pipeline.',
             'hint': "import joblib; joblib.dump(pipe, 'models/titanic_clf.joblib'); loaded = "
                     "joblib.load('models/titanic_clf.joblib'); assert (loaded.predict(X_test[:5]) == "
                     'pipe.predict(X_test[:5])).all().',
             'order': 6,
             'depends_on': 'CLF-5'}]},
 {'technology_slug': 'ai-ml',
  'title': 'Feature Engineering & Regression: Predict Housing Prices',
  'slug': 'ai-ml-feature-engineering-regression',
  'architecture_type': 'custom',
  'description': 'Engineer meaningful features from a housing dataset and train regression models to predict '
                 'sale price. You will craft derived and interaction features, handle skewed targets with a '
                 'log transform, cross-validate a RandomForestRegressor, and rank feature importance to '
                 'explain the model.',
  'objectives': ['Create derived, interaction, and binned features that improve signal',
                 'Apply a log transform to a skewed target and correctly invert it for metrics',
                 'Compare a linear baseline against RandomForestRegressor with cross-validation',
                 'Measure regression error with RMSE and MAE and interpret the gap',
                 'Rank and interpret feature importances to explain predictions'],
  'difficulty': 'beginner',
  'estimated_hours': 4,
  'order': 2,
  'tasks': [{'jira_key': 'REG-1',
             'title': 'Profile the target and detect skew',
             'description': 'Load data/housing.csv, plot or compute the skew of SalePrice with '
                            "df['SalePrice'].skew(), and identify numeric features most correlated with the "
                            'target using the correlation matrix.',
             'acceptance_criteria': 'The script prints the raw skew of SalePrice (should be strongly '
                                    'positive) and the top 8 features by absolute correlation with '
                                    'SalePrice.',
             'hint': "print(df['SalePrice'].skew()); corr = "
                     "df.corr(numeric_only=True)['SalePrice'].abs().sort_values(ascending=False); "
                     'print(corr.head(9)). A skew above ~1 signals a log transform is warranted.',
             'order': 1},
            {'jira_key': 'REG-2',
             'title': 'Log-transform the target',
             'description': 'Create y = np.log1p(SalePrice) so the target is closer to normal. Record that '
                            'all metrics must be computed after inverting with np.expm1 to report dollars, '
                            'not log-dollars.',
             'acceptance_criteria': 'A log1p-transformed target column exists with skew closer to 0 than the '
                                    'raw target, and a helper inverts predictions via np.expm1.',
             'hint': "import numpy as np; y = np.log1p(df['SalePrice']); print(y.skew()). At scoring time: "
                     'preds_dollars = np.expm1(model.predict(X_test)).',
             'order': 2,
             'depends_on': 'REG-1'},
            {'jira_key': 'REG-3',
             'title': 'Engineer derived and interaction features',
             'description': 'Add TotalSF = TotalBsmtSF + 1stFlrSF + 2ndFlrSF, HouseAge = YrSold - YearBuilt, '
                            'and a TotalBath interaction combining full and half baths. Bin YearBuilt into '
                            'decade buckets.',
             'acceptance_criteria': 'The feature frame contains TotalSF, HouseAge, TotalBath, and a decade '
                                    'bin column; none contain negative ages or NaNs introduced by the '
                                    'arithmetic.',
             'hint': "df['TotalSF'] = df['TotalBsmtSF'] + df['1stFlrSF'] + df['2ndFlrSF']; df['HouseAge'] = "
                     "df['YrSold'] - df['YearBuilt']; df['TotalBath'] = df['FullBath'] + 0.5*df['HalfBath']. "
                     'Use pd.cut for decade bins.',
             'order': 3,
             'depends_on': 'REG-2'},
            {'jira_key': 'REG-4',
             'title': 'Train a linear baseline with cross-validation',
             'description': 'Build a preprocessing pipeline (impute + scale numerics, one-hot categoricals) '
                            'with LinearRegression and run 5-fold cross_val_score using '
                            'neg_root_mean_squared_error on the log target.',
             'acceptance_criteria': 'cross_val_score returns 5 RMSE values; the mean CV RMSE (in log space) '
                                    'is printed as the baseline to beat.',
             'hint': 'from sklearn.model_selection import cross_val_score; scores = cross_val_score(pipe, X, '
                     "y, cv=5, scoring='neg_root_mean_squared_error'); print(-scores.mean()). Keep "
                     'preprocessing inside the pipeline so each fold refits.',
             'order': 4,
             'depends_on': 'REG-3'},
            {'jira_key': 'REG-5',
             'title': 'Train RandomForestRegressor and compare error',
             'description': 'Swap the estimator for RandomForestRegressor(n_estimators=300, '
                            'random_state=42), re-run cross-validation, then fit on the full training set '
                            'and report test RMSE and MAE in dollars after expm1 inversion.',
             'acceptance_criteria': 'Test RMSE and MAE are printed in dollar units (post-expm1), and the '
                                    'RandomForest CV RMSE is lower than the linear baseline from REG-4.',
             'hint': 'from sklearn.metrics import mean_squared_error, mean_absolute_error; rmse = '
                     'mean_squared_error(np.expm1(y_test), np.expm1(preds), squared=False). A large '
                     'RMSE-vs-MAE gap indicates a few big-error outliers.',
             'order': 5,
             'depends_on': 'REG-4'},
            {'jira_key': 'REG-6',
             'title': 'Rank and interpret feature importances',
             'description': 'Extract feature_importances_ from the fitted RandomForest, map them back to the '
                            'expanded feature names from the ColumnTransformer, and print the top 15 drivers '
                            'of price.',
             'acceptance_criteria': 'A sorted table of the top 15 features by importance is printed, and '
                                    'your engineered TotalSF or overall-quality feature appears near the '
                                    'top.',
             'hint': "names = pipe.named_steps['prep'].get_feature_names_out(); imp = "
                     "pipe.named_steps['model'].feature_importances_; pd.Series(imp, "
                     'index=names).sort_values(ascending=False).head(15).',
             'order': 6,
             'depends_on': 'REG-5'}]},
 {'technology_slug': 'ai-ml',
  'title': 'Hyperparameter Tuning & Model Selection with Cross-Validation',
  'slug': 'ai-ml-hyperparameter-tuning-cv',
  'architecture_type': 'custom',
  'description': 'Systematically tune a gradient-boosting classifier instead of guessing hyperparameters. '
                 'You will establish a baseline, run GridSearchCV then the faster RandomizedSearchCV, guard '
                 'against overfitting with a held-out test set, and lock in the best pipeline as a versioned '
                 'artifact.',
  'objectives': ['Establish a defensible baseline before any tuning',
                 'Run GridSearchCV with a parameter grid and read cv_results_',
                 'Use RandomizedSearchCV to explore a larger space efficiently',
                 'Detect overfitting by comparing CV score to held-out test score',
                 'Save the best_estimator_ with metadata for reproducibility'],
  'difficulty': 'intermediate',
  'estimated_hours': 5,
  'order': 3,
  'tasks': [{'jira_key': 'TUNE-1',
             'title': 'Establish an untuned baseline',
             'description': 'Split the dataset (stratified), fit a GradientBoostingClassifier with all '
                            'default hyperparameters, and record the ROC AUC on the test set as the number '
                            'every tuning run must beat.',
             'acceptance_criteria': 'A baseline test-set ROC AUC is printed and saved to a variable; the '
                                    'split uses random_state=42 and stratify=y for reproducibility.',
             'hint': 'from sklearn.ensemble import GradientBoostingClassifier; from sklearn.metrics import '
                     'roc_auc_score; roc_auc_score(y_test, model.predict_proba(X_test)[:,1]). Write the '
                     'baseline down before tuning.',
             'order': 1},
            {'jira_key': 'TUNE-2',
             'title': 'Define a parameter grid and run GridSearchCV',
             'description': 'Build a param_grid over n_estimators, learning_rate, and max_depth. Run '
                            "GridSearchCV(estimator, param_grid, cv=5, scoring='roc_auc', n_jobs=-1) on the "
                            'training set only.',
             'acceptance_criteria': 'grid.best_params_ and grid.best_score_ are printed; total fits equals '
                                    '(grid combinations x 5 folds) and the search never touches X_test.',
             'hint': "param_grid = {'n_estimators':[100,300], 'learning_rate':[0.05,0.1], "
                     "'max_depth':[2,3,4]}; GridSearchCV(clf, param_grid, cv=5, scoring='roc_auc', "
                     'n_jobs=-1).fit(X_train, y_train).',
             'order': 2,
             'depends_on': 'TUNE-1'},
            {'jira_key': 'TUNE-3',
             'title': 'Inspect cv_results_ to understand sensitivity',
             'description': 'Convert grid.cv_results_ to a DataFrame, sort by mean_test_score, and identify '
                            'which hyperparameter moved the score the most. Note the std of the top '
                            'configurations.',
             'acceptance_criteria': 'A sorted DataFrame of mean_test_score and std_test_score per param '
                                    'combo is printed, and you name the single most impactful hyperparameter '
                                    'in a comment.',
             'hint': "res = pd.DataFrame(grid.cv_results_).sort_values('mean_test_score', ascending=False); "
                     "print(res[['params','mean_test_score','std_test_score']].head()). A high std means an "
                     'unstable config.',
             'order': 3,
             'depends_on': 'TUNE-2'},
            {'jira_key': 'TUNE-4',
             'title': 'Explore a wider space with RandomizedSearchCV',
             'description': 'Replace the discrete grid with distributions (e.g. scipy randint / uniform) and '
                            'run RandomizedSearchCV with n_iter=30. Compare its best score and wall-clock '
                            'time against GridSearchCV.',
             'acceptance_criteria': 'RandomizedSearchCV completes 30 sampled configs, prints best_params_ '
                                    'and best_score_, and you report whether it matched grid search in less '
                                    'time.',
             'hint': 'from scipy.stats import randint, uniform; param_dist = '
                     "{'n_estimators':randint(100,500), 'learning_rate':uniform(0.01,0.2), "
                     "'max_depth':randint(2,6)}; RandomizedSearchCV(clf, param_dist, n_iter=30, cv=5, "
                     "scoring='roc_auc', random_state=42).",
             'order': 4,
             'depends_on': 'TUNE-3'},
            {'jira_key': 'TUNE-5',
             'title': 'Check for overfitting on the held-out test set',
             'description': 'Take the best_estimator_ from the winning search and score it on X_test. '
                            'Compare the test ROC AUC to the CV best_score_; a gap larger than a few points '
                            'signals overfitting to the validation folds.',
             'acceptance_criteria': 'Both the CV best_score_ and the held-out test ROC AUC are printed side '
                                    'by side, and the tuned test score beats the TUNE-1 baseline.',
             'hint': 'best = search.best_estimator_; test_auc = roc_auc_score(y_test, '
                     'best.predict_proba(X_test)[:,1]); print(search.best_score_, test_auc). If test << CV, '
                     'reduce max_depth or n_estimators.',
             'order': 5,
             'depends_on': 'TUNE-4'},
            {'jira_key': 'TUNE-6',
             'title': 'Persist the best model with metadata',
             'description': 'Save best_estimator_ to models/best_gbc.joblib alongside a JSON sidecar '
                            'recording best_params_, CV score, test score, sklearn version, and the training '
                            'date for reproducibility.',
             'acceptance_criteria': 'Both models/best_gbc.joblib and models/best_gbc.meta.json exist; the '
                                    'JSON contains best_params, cv_auc, test_auc, and library versions.',
             'hint': "import json, sklearn, datetime; json.dump({'best_params':search.best_params_, "
                     "'cv_auc':search.best_score_, 'test_auc':test_auc, 'sklearn':sklearn.__version__, "
                     "'trained':str(datetime.date.today())}, open('models/best_gbc.meta.json','w')).",
             'order': 6,
             'depends_on': 'TUNE-5'}]},
 {'technology_slug': 'ai-ml',
  'title': 'Serve a Model Behind a FastAPI Prediction API',
  'slug': 'ai-ml-serve-model-fastapi',
  'architecture_type': '2tier',
  'description': 'Wrap a trained model artifact in a production-style FastAPI service. You will load the '
                 'model once at startup, validate requests with Pydantic, expose /predict and /health '
                 'endpoints, containerize the service with Docker, and load-test it to confirm latency and '
                 'correctness.',
  'objectives': ['Load a joblib model once at app startup, not per request',
                 'Validate and document request/response schemas with Pydantic',
                 'Expose /predict, /health, and interactive OpenAPI docs',
                 'Containerize the service with a slim Docker image',
                 'Load-test the endpoint and confirm latency and correct outputs'],
  'difficulty': 'intermediate',
  'estimated_hours': 5,
  'order': 4,
  'tasks': [{'jira_key': 'SERVE-1',
             'title': 'Scaffold the FastAPI app and load the model at startup',
             'description': 'Create app/main.py with a FastAPI instance. Load models/titanic_clf.joblib '
                            'inside a lifespan/startup handler so the artifact is deserialized once and '
                            'reused across requests rather than reloaded per call.',
             'acceptance_criteria': 'uvicorn app.main:app --reload starts cleanly and logs a message '
                                    'confirming the model loaded exactly once, before serving the first '
                                    'request.',
             'hint': 'Use the lifespan context manager: @asynccontextmanager async def lifespan(app): '
                     "app.state.model = joblib.load('models/titanic_clf.joblib'); yield. Attach app = "
                     'FastAPI(lifespan=lifespan).',
             'order': 1},
            {'jira_key': 'SERVE-2',
             'title': 'Define Pydantic request and response schemas',
             'description': 'Create a PredictRequest model with typed fields matching the training features '
                            '(Pclass, Sex, Age, Fare, Embarked, etc.) and a PredictResponse with prediction '
                            '(int) and probability (float).',
             'acceptance_criteria': 'Posting a payload with a wrong type (e.g. Age as a string that cannot '
                                    'cast) returns a 422 with a descriptive validation error automatically.',
             'hint': 'from pydantic import BaseModel, Field; class PredictRequest(BaseModel): Pclass:int; '
                     'Sex:str; Age:float = Field(ge=0); Fare:float; Embarked:str. FastAPI enforces types '
                     'before your handler runs.',
             'order': 2,
             'depends_on': 'SERVE-1'},
            {'jira_key': 'SERVE-3',
             'title': 'Implement the /predict endpoint',
             'description': 'Add POST /predict that converts the validated request into a single-row '
                            "DataFrame with the exact training column order, calls the pipeline's predict "
                            'and predict_proba, and returns the PredictResponse.',
             'acceptance_criteria': 'curl -X POST /predict with a valid JSON body returns 200 with '
                                    '{prediction, probability}; probability is between 0 and 1 and matches '
                                    'predict_proba for that row.',
             'hint': 'row = pd.DataFrame([req.model_dump()]); proba = '
                     'app.state.model.predict_proba(row)[0,1]; pred = int(proba >= 0.5). Return '
                     "{'prediction': pred, 'probability': round(float(proba),4)}.",
             'order': 3,
             'depends_on': 'SERVE-2'},
            {'jira_key': 'SERVE-4',
             'title': 'Add /health and verify OpenAPI docs',
             'description': "Add GET /health returning {status:'ok', model_loaded: bool}. Open "
                            'http://localhost:8000/docs and confirm the auto-generated Swagger UI shows both '
                            'endpoints with the correct schemas.',
             'acceptance_criteria': 'curl /health returns 200 with model_loaded true, and the /docs page '
                                    'renders /predict with the PredictRequest schema and example values.',
             'hint': "@app.get('/health') def health(): return {'status':'ok','model_loaded': "
                     "hasattr(app.state,'model')}. Use /docs (Swagger) or /redoc for the generated docs.",
             'order': 4,
             'depends_on': 'SERVE-3'},
            {'jira_key': 'SERVE-5',
             'title': 'Containerize the service with Docker',
             'description': 'Write a Dockerfile FROM python:3.12-slim that installs requirements, copies '
                            'app/ and models/, and runs uvicorn with gunicorn workers. Build and run it, '
                            'mapping port 8000.',
             'acceptance_criteria': 'docker build -t titanic-api . succeeds and docker run -p 8000:8000 '
                                    'titanic-api serves /health with a 200 from inside the container.',
             'hint': 'CMD '
                     '["gunicorn","-k","uvicorn.workers.UvicornWorker","-w","2","-b","0.0.0.0:8000","app.main:app"]. '
                     'Copy models/ into the image so the artifact ships with the service.',
             'order': 5,
             'depends_on': 'SERVE-4'},
            {'jira_key': 'SERVE-6',
             'title': 'Load-test the endpoint and measure latency',
             'description': 'Use a small script (or hey/locust) to fire ~500 concurrent POST /predict '
                            'requests. Record p50/p95 latency and confirm every response is valid and '
                            'deterministic for the same input.',
             'acceptance_criteria': 'A load-test report shows p95 latency and a 0% error rate; identical '
                                    'payloads return identical predictions across all requests.',
             'hint': "hey -n 500 -c 20 -m POST -H 'Content-Type: application/json' -d '{...}' "
                     'http://localhost:8000/predict. Or write an asyncio + httpx client. Watch p95, not just '
                     'the mean.',
             'order': 6,
             'depends_on': 'SERVE-5'}]},
 {'technology_slug': 'ai-ml',
  'title': 'Production ML: Monitor Data Drift and Trigger Retraining',
  'slug': 'ai-ml-monitor-drift-retraining',
  'architecture_type': 'microservices',
  'description': 'Close the MLOps loop by monitoring a deployed model for data and prediction drift. You '
                 'will capture a reference distribution, compute PSI and Kolmogorov-Smirnov drift on live '
                 'traffic, expose Prometheus metrics scraped into Grafana, and wire an automated retraining '
                 'job that promotes a new model only if it beats the incumbent.',
  'objectives': ['Capture a reference distribution baseline from training data',
                 'Detect feature drift with PSI and the Kolmogorov-Smirnov test',
                 'Emit drift and prediction metrics to Prometheus and visualize in Grafana',
                 'Alert when drift crosses a threshold sustained over a window',
                 'Automate a retraining job that only promotes a better model (champion/challenger)'],
  'difficulty': 'advanced',
  'estimated_hours': 8,
  'order': 5,
  'tasks': [{'jira_key': 'DRIFT-1',
             'title': 'Capture the reference distribution baseline',
             'description': 'From the training set, compute and serialize per-feature reference statistics: '
                            'histogram bin edges and frequencies for numeric features and category '
                            'frequencies for categoricals. Store as reference/baseline.json.',
             'acceptance_criteria': 'reference/baseline.json contains per-feature bins/frequencies that sum '
                                    'to ~1.0 and includes the reference prediction rate (mean positive '
                                    'class) from training.',
             'hint': 'For numeric: counts, edges = np.histogram(train[col], bins=10); store edges and '
                     'counts/counts.sum(). For categoricals: '
                     'train[col].value_counts(normalize=True).to_dict(). This is your ground truth for '
                     'drift.',
             'order': 1},
            {'jira_key': 'DRIFT-2',
             'title': 'Implement PSI and KS drift detection',
             'description': 'Write drift.py with a compute_psi(reference, current) using the standard '
                            'sum((cur-ref)*ln(cur/ref)) formula, and a ks_test using scipy.stats.ks_2samp '
                            'for numeric features. Bucket live requests into windows before scoring.',
             'acceptance_criteria': 'Feeding the reference data back in yields PSI near 0 and a '
                                    'non-significant KS p-value; feeding a deliberately shifted feature '
                                    'yields PSI > 0.2 and KS p < 0.05.',
             'hint': 'PSI < 0.1 = no drift, 0.1-0.25 = moderate, > 0.25 = significant. Add epsilon to avoid '
                     'log(0): psi = np.sum((cur - ref) * np.log((cur + 1e-6)/(ref + 1e-6))). Use '
                     'scipy.stats.ks_2samp for the two-sample test.',
             'order': 2,
             'depends_on': 'DRIFT-1'},
            {'jira_key': 'DRIFT-3',
             'title': 'Instrument the FastAPI service with Prometheus metrics',
             'description': 'Add prometheus_client to the prediction service: a Counter for total '
                            'predictions, a Histogram for latency, a Gauge for per-feature PSI, and a Gauge '
                            'for the rolling positive-prediction rate. Expose /metrics.',
             'acceptance_criteria': 'curl /metrics returns Prometheus text exposition including '
                                    'prediction_total, prediction_latency_seconds, feature_psi{feature=...}, '
                                    'and prediction_positive_rate.',
             'hint': 'from prometheus_client import Counter, Histogram, Gauge, make_asgi_app; '
                     "app.mount('/metrics', make_asgi_app()). Update the PSI gauge on each scoring window: "
                     'FEATURE_PSI.labels(feature=f).set(psi_value).',
             'order': 3,
             'depends_on': 'DRIFT-2'},
            {'jira_key': 'DRIFT-4',
             'title': 'Build a Grafana drift dashboard with alerts',
             'description': 'Point Prometheus at the service, import the metrics into Grafana, and build a '
                            'dashboard with panels for latency p95, prediction rate vs the reference rate, '
                            'and per-feature PSI. Add an alert rule when any feature_psi > 0.25 for 15 '
                            'minutes.',
             'acceptance_criteria': 'The Grafana dashboard renders all three panels from live scrapes, and '
                                    'simulating a drifted feature fires the PSI alert into the configured '
                                    'notification channel.',
             'hint': "PromQL: max(feature_psi) > 0.25 as the alert condition with a 15m 'for' duration to "
                     'avoid flapping. Overlay prediction_positive_rate against the baseline rate stored in '
                     'DRIFT-1.',
             'order': 4,
             'depends_on': 'DRIFT-3'},
            {'jira_key': 'DRIFT-5',
             'title': 'Automate a champion/challenger retraining job',
             'description': 'Write retrain.py that pulls recent labeled data, retrains the pipeline, '
                            'evaluates the challenger against the current champion on a frozen holdout, and '
                            "only writes models/current.joblib if the challenger's ROC AUC exceeds the "
                            'champion by a minimum margin.',
             'acceptance_criteria': 'Running retrain.py logs both champion and challenger AUC and promotes '
                                    'the model only when challenger_auc > champion_auc + 0.005; otherwise it '
                                    'keeps the champion and exits non-zero.',
             'hint': 'Compare on a fixed holdout set to keep the comparison fair. Guard promotion: if '
                     "challenger_auc - champion_auc > 0.005: joblib.dump(challenger,'models/current.joblib') "
                     'else keep champion. Log both numbers for the audit trail.',
             'order': 5,
             'depends_on': 'DRIFT-4'},
            {'jira_key': 'DRIFT-6',
             'title': 'Schedule retraining and add a rollback path',
             'description': 'Wire retrain.py into a scheduled job (cron or a CI pipeline) triggered on the '
                            'DRIFT-4 alert, versioning promoted models as models/model-<timestamp>.joblib '
                            'with a current symlink. Document and test rolling back by repointing the '
                            'symlink.',
             'acceptance_criteria': 'A scheduled trigger runs the job, promoted models are '
                                    "timestamp-versioned with a 'current' pointer, and repointing the "
                                    'symlink to a prior version is verified by the service serving the older '
                                    'model after reload.',
             'hint': 'ln -sfn model-20260710.joblib models/current.joblib for atomic swaps. Reload the '
                     'FastAPI model (restart or a /reload admin endpoint) after promotion. Keep the last N '
                     'versions for fast rollback.',
             'order': 6,
             'depends_on': 'DRIFT-5'}]},
 {'technology_slug': 'data-science',
  'title': 'Load and Clean a Messy Retail Dataset with pandas',
  'slug': 'data-science-load-and-clean-retail-dataset',
  'architecture_type': 'custom',
  'description': 'You inherit a raw CSV export of e-commerce orders full of nulls, inconsistent types, '
                 'duplicate rows, and dirty categorical values. Working entirely in a local Jupyter notebook '
                 'with pandas, you profile the data, fix each class of quality problem, and export a clean, '
                 'analysis-ready dataset. This is the foundational data-wrangling project every later '
                 'project builds on.',
  'objectives': ['Load CSV data into a pandas DataFrame and profile it with info(), describe(), and isna()',
                 'Diagnose and repair missing values, wrong dtypes, and duplicate records',
                 'Standardize messy categorical and string columns into consistent canonical values',
                 'Export a validated, reproducible clean dataset to disk (CSV and Parquet)'],
  'difficulty': 'beginner',
  'estimated_hours': 3,
  'order': 1,
  'tasks': [{'jira_key': 'DSCLEAN-1',
             'title': 'Load the raw CSV and profile its quality',
             'description': "Read raw_orders.csv into a DataFrame with pd.read_csv('raw_orders.csv'). "
                            "Inspect shape, df.head(), df.info(), and df.describe(include='all'). Compute "
                            'per-column null counts with df.isna().sum() and dtypes with df.dtypes to build '
                            'an inventory of every quality problem.',
             'acceptance_criteria': 'A markdown cell lists each column, its dtype, null count, and at least '
                                    "three concrete quality issues (e.g. 'order_date is object not "
                                    "datetime', 'price has nulls', 'country has mixed casing').",
             'hint': 'Use df.isna().sum().sort_values(ascending=False) to rank columns by missingness, and '
                     "df['country'].value_counts(dropna=False) to spot inconsistent categorical values.",
             'order': 1},
            {'jira_key': 'DSCLEAN-2',
             'title': 'Fix column dtypes',
             'description': "Convert order_date to datetime with pd.to_datetime(df['order_date'], "
                            "errors='coerce'), coerce price and quantity to numeric with pd.to_numeric(..., "
                            "errors='coerce'), and cast the low-cardinality status column to a pandas "
                            "'category' dtype.",
             'acceptance_criteria': 'df.dtypes shows order_date as datetime64[ns], price/quantity as float '
                                    'or int, and status as category; no conversion raises an exception.',
             'hint': "errors='coerce' turns unparseable values into NaT/NaN instead of raising — that "
                     'surfaces bad rows you then handle in DSCLEAN-3. Re-run df.isna().sum() after coercion '
                     'to see newly exposed nulls.',
             'depends_on': 'DSCLEAN-1',
             'order': 2},
            {'jira_key': 'DSCLEAN-3',
             'title': 'Handle missing values with a documented strategy',
             'description': 'Decide per column: drop rows missing a required key (order_id), impute numeric '
                            'gaps (fill quantity nulls with the median via '
                            "df['quantity'].fillna(df['quantity'].median())), and fill missing categorical "
                            "values with an explicit 'unknown' sentinel. Document why each choice was made.",
             'acceptance_criteria': 'df.isna().sum() returns 0 for all required columns, and a markdown cell '
                                    'justifies drop-vs-impute for each column that had nulls.',
             'hint': "Drop only where the value is truly required: df = df.dropna(subset=['order_id']). "
                     'Prefer median over mean for skewed numeric columns because it resists outliers.',
             'depends_on': 'DSCLEAN-2',
             'order': 3},
            {'jira_key': 'DSCLEAN-4',
             'title': 'Remove duplicates and standardize strings',
             'description': "Detect duplicate orders with df.duplicated(subset=['order_id']).sum(), drop "
                            "them keeping the first occurrence, then normalize text columns: df['country'] = "
                            "df['country'].str.strip().str.title() and map known variants (e.g. "
                            "'USA'/'U.S.'->'United States') with .replace().",
             'acceptance_criteria': "df.duplicated(subset=['order_id']).sum() == 0 and "
                                    "df['country'].value_counts() shows a small canonical set with no casing "
                                    'or whitespace variants.',
             'hint': "Build the variant map explicitly: country_map = {'USA':'United States','U.S.':'United "
                     "States'}; df['country'] = df['country'].replace(country_map). Chain .str.strip() "
                     'before .str.title() to kill trailing spaces first.',
             'depends_on': 'DSCLEAN-3',
             'order': 4},
            {'jira_key': 'DSCLEAN-5',
             'title': 'Validate invariants with assertions',
             'description': 'Add a validation cell that asserts the cleaned data holds business invariants: '
                            'no nulls in required columns, price >= 0, quantity > 0, and order_date within a '
                            'plausible range. Use assert statements so the notebook fails loudly if a rule '
                            'breaks.',
             'acceptance_criteria': 'All assertions pass on the cleaned DataFrame; assertions include at '
                                    'least null-check, non-negative price, positive quantity, and date-range '
                                    'checks.',
             'hint': "Write assert (df['price'] >= 0).all(), 'negative price found' — the message makes "
                     'failures self-explanatory. Run this cell last so it guards the export step.',
             'depends_on': 'DSCLEAN-4',
             'order': 5},
            {'jira_key': 'DSCLEAN-6',
             'title': 'Export the clean dataset',
             'description': 'Persist the validated DataFrame to both clean_orders.csv '
                            "(df.to_csv('clean_orders.csv', index=False)) and clean_orders.parquet "
                            "(df.to_parquet('clean_orders.parquet')). Reload each with read_csv/read_parquet "
                            'and confirm shape and dtypes round-trip correctly.',
             'acceptance_criteria': 'Both files exist on disk; reloading clean_orders.parquet reproduces '
                                    'identical shape and dtypes (Parquet preserves them), and the CSV reload '
                                    'matches on shape.',
             'hint': 'Parquet keeps dtypes (datetime, category) that CSV loses, so prefer it for downstream '
                     'projects. Verify with '
                     "pd.read_parquet('clean_orders.parquet').dtypes.equals(df.dtypes).",
             'depends_on': 'DSCLEAN-5',
             'order': 6}]},
 {'technology_slug': 'data-science',
  'title': 'Exploratory Data Analysis and Visualization of Bike-Share Trips',
  'slug': 'data-science-eda-and-visualization-bikeshare',
  'architecture_type': 'custom',
  'description': 'Starting from a clean bike-share trips dataset, you run a full exploratory data analysis '
                 'to understand demand: univariate distributions, group-by aggregations, correlations, and '
                 'time-based patterns. You produce a set of publication-quality matplotlib and seaborn '
                 'charts and write down the insights each one reveals. The output is an EDA notebook a '
                 'stakeholder could actually read.',
  'objectives': ['Summarize distributions and spot skew and outliers with histograms and box plots',
                 'Aggregate with groupby and pivot_table to compare segments',
                 'Build a correlation matrix and heatmap to find related variables',
                 'Uncover temporal demand patterns by hour, day-of-week, and season',
                 'Translate each chart into a written, decision-relevant insight'],
  'difficulty': 'beginner',
  'estimated_hours': 4,
  'order': 2,
  'tasks': [{'jira_key': 'DSEDA-1',
             'title': 'Load data and derive time features',
             'description': 'Load trips.parquet, confirm dtypes, and derive analysis features from the '
                            "timestamp: df['hour'] = df['started_at'].dt.hour, df['dow'] = "
                            "df['started_at'].dt.day_name(), and df['duration_min'] = (df['ended_at'] - "
                            "df['started_at']).dt.total_seconds() / 60.",
             'acceptance_criteria': 'The DataFrame has hour (0-23), dow (weekday names), and duration_min '
                                    '(positive float) columns, and '
                                    "df[['hour','dow','duration_min']].describe() runs without error.",
             'hint': 'The .dt accessor only works on datetime64 columns — if started_at is an object, run '
                     'pd.to_datetime first. Filter out non-positive durations before analysis: df = '
                     "df[df['duration_min'] > 0].",
             'order': 1},
            {'jira_key': 'DSEDA-2',
             'title': 'Analyze univariate distributions',
             'description': 'Plot the distribution of duration_min with a histogram (sns.histplot) and a box '
                            'plot (sns.boxplot). Note the skew, identify the median and IQR, and flag '
                            'extreme outliers (e.g. trips over the 99th percentile).',
             'acceptance_criteria': 'Two rendered charts exist for duration_min; a markdown note states the '
                                    'distribution is right-skewed and reports the median plus the '
                                    '99th-percentile cutoff.',
             'hint': 'Cap the x-axis for readability on skewed data: plt.xlim(0, '
                     "df['duration_min'].quantile(0.99)). Compute the cutoff with "
                     "df['duration_min'].quantile(0.99).",
             'depends_on': 'DSEDA-1',
             'order': 2},
            {'jira_key': 'DSEDA-3',
             'title': 'Compare segments with groupby and pivot_table',
             'description': 'Aggregate ride counts and mean duration by rider type and day-of-week. Use '
                            "df.groupby('member_type')['duration_min'].agg(['count','mean','median']) and a "
                            "pivot_table(index='dow', columns='member_type', values='duration_min', "
                            "aggfunc='mean').",
             'acceptance_criteria': 'A groupby summary table and a pivot_table are displayed, and a note '
                                    'compares casual vs member behavior (e.g. casual riders take longer '
                                    'trips).',
             'hint': "Order the weekday axis explicitly with a categorical: pd.Categorical(df['dow'], "
                     'categories=[...], ordered=True) so Monday..Sunday sort correctly instead of '
                     'alphabetically.',
             'depends_on': 'DSEDA-1',
             'order': 3},
            {'jira_key': 'DSEDA-4',
             'title': 'Build a correlation heatmap',
             'description': 'Select numeric columns, compute df.corr(numeric_only=True), and render it with '
                            "sns.heatmap(corr, annot=True, cmap='coolwarm', vmin=-1, vmax=1). Identify the "
                            'strongest positive and negative relationships.',
             'acceptance_criteria': 'An annotated correlation heatmap is displayed and a note names the two '
                                    'most correlated numeric variables with their coefficient.',
             'hint': 'annot=True prints the coefficient in each cell. Ignore the diagonal (always 1.0) and '
                     'remember correlation is not causation when you write the insight.',
             'depends_on': 'DSEDA-1',
             'order': 4},
            {'jira_key': 'DSEDA-5',
             'title': 'Visualize temporal demand patterns',
             'description': 'Plot rides-per-hour as a line chart and a dow-by-hour demand heatmap using a '
                            "pivot_table(index='dow', columns='hour', values='ride_id', aggfunc='count'). "
                            'Identify commuter peaks vs weekend patterns.',
             'acceptance_criteria': 'A rides-per-hour line chart and a day-by-hour heatmap are displayed, '
                                    'and a note calls out the morning/evening commuter peaks on weekdays.',
             'hint': "Use aggfunc='count' on any always-present column (ride_id) to count rides per cell. "
                     'Weekday commuter demand usually shows twin peaks around 8am and 5-6pm.',
             'depends_on': 'DSEDA-3',
             'order': 5},
            {'jira_key': 'DSEDA-6',
             'title': 'Write the insight summary',
             'description': "Add a top-of-notebook 'Key Findings' markdown section with 4-6 bullet insights, "
                            'each referencing a specific chart and stating a concrete number and a possible '
                            'business action (e.g. rebalance bikes before the 8am peak).',
             'acceptance_criteria': 'A Key Findings section lists 4-6 bullets; each bullet cites a chart, '
                                    'includes a quantitative detail, and suggests an action or hypothesis.',
             'hint': "Good EDA insights are falsifiable and quantitative — 'evening peak is ~2.3x the midday "
                     "trough' beats 'evenings are busy'. Put this section at the top so readers get the "
                     'payoff first.',
             'depends_on': 'DSEDA-5',
             'order': 6}]},
 {'technology_slug': 'data-science',
  'title': 'Statistical Analysis and A/B Test Evaluation',
  'slug': 'data-science-statistical-analysis-ab-testing',
  'architecture_type': 'custom',
  'description': 'A product team ran an A/B test on a new checkout flow and hands you the raw event data. '
                 'Using scipy and statsmodels, you frame hypotheses, check assumptions, run the right '
                 'significance tests, compute effect sizes and confidence intervals, and deliver a '
                 'defensible ship/no-ship recommendation. This project turns EDA charts into rigorous '
                 'statistical conclusions.',
  'objectives': ['Formulate null and alternative hypotheses and choose the correct test',
                 'Check normality and variance assumptions before testing',
                 'Run t-tests and chi-square tests and interpret p-values correctly',
                 'Report effect size and confidence intervals, not just significance',
                 'Reason about statistical power and multiple-comparison pitfalls'],
  'difficulty': 'intermediate',
  'estimated_hours': 5,
  'order': 3,
  'tasks': [{'jira_key': 'DSSTAT-1',
             'title': 'Frame the experiment and hypotheses',
             'description': 'Load ab_events.parquet, confirm clean random assignment by checking group sizes '
                            "(df['group'].value_counts()) and covariate balance. Write H0 and H1 for the "
                            'primary metric (conversion rate) and the secondary metric (mean order value).',
             'acceptance_criteria': 'Group sizes are reported and roughly balanced; markdown states H0/H1 '
                                    'for both conversion rate (proportions) and order value (means), with '
                                    'the chosen alpha (e.g. 0.05).',
             'hint': "State direction explicitly: H0 is 'p_treatment == p_control'. Balanced groups and "
                     'matched covariate means are evidence randomization worked — a big imbalance is a red '
                     'flag before you test anything.',
             'order': 1},
            {'jira_key': 'DSSTAT-2',
             'title': 'Check test assumptions',
             'description': 'For the order-value comparison, test normality with scipy.stats.shapiro on each '
                            "group's sample and equal variance with scipy.stats.levene. Decide between a "
                            "Student's t-test, Welch's t-test, or a nonparametric Mann-Whitney U based on "
                            'results.',
             'acceptance_criteria': 'Shapiro and Levene results are reported with a stated decision rule, '
                                    "and a note picks the appropriate test (e.g. Welch's t-test because "
                                    'variances differ).',
             'hint': "With unequal variances use Welch's: stats.ttest_ind(a, b, equal_var=False). If "
                     'normality fails badly on small samples, fall back to stats.mannwhitneyu. Large samples '
                     'make the CLT forgiving of mild non-normality.',
             'depends_on': 'DSSTAT-1',
             'order': 2},
            {'jira_key': 'DSSTAT-3',
             'title': 'Test the conversion-rate difference',
             'description': 'Compare conversion proportions between groups. Build a 2x2 contingency table '
                            '(converted vs not, by group) and run scipy.stats.chi2_contingency, or use '
                            'statsmodels.stats.proportion.proportions_ztest. Report the p-value and the '
                            'absolute lift.',
             'acceptance_criteria': 'A contingency table and a proportion test are shown; the p-value, '
                                    'absolute conversion lift, and a significance decision against alpha are '
                                    'reported.',
             'hint': 'For two proportions, proportions_ztest([conv_t, conv_c], [n_t, n_c]) is direct. '
                     'chi2_contingency works too but reports a two-sided association — report the lift '
                     'direction separately.',
             'depends_on': 'DSSTAT-1',
             'order': 3},
            {'jira_key': 'DSSTAT-4',
             'title': 'Test the order-value difference and quantify effect',
             'description': "Run the test chosen in DSSTAT-2 on mean order value, then compute Cohen's d "
                            'effect size and a 95% confidence interval for the difference in means. A '
                            'significant p-value with a tiny effect is not a real win.',
             'acceptance_criteria': "The chosen mean-comparison test is run; Cohen's d and a 95% CI for the "
                                    'mean difference are reported and interpreted (magnitude, not just '
                                    'direction).',
             'hint': "Cohen's d = (mean_a - mean_b) / pooled_std. Build the CI from the difference and its "
                     'standard error (diff +/- 1.96*SE for large samples). Interpret d ~0.2 small, ~0.5 '
                     'medium, ~0.8 large.',
             'depends_on': 'DSSTAT-2',
             'order': 4},
            {'jira_key': 'DSSTAT-5',
             'title': 'Address power and multiple comparisons',
             'description': 'Compute the achieved power / minimum detectable effect for the conversion test '
                            'using statsmodels.stats.power. Since two metrics were tested, apply a '
                            'Bonferroni or Benjamini-Hochberg correction to the alpha and re-evaluate '
                            'significance.',
             'acceptance_criteria': 'A power/MDE figure is reported, a multiple-comparison correction is '
                                    'applied to the two tests, and the significance conclusions are restated '
                                    'under the corrected alpha.',
             'hint': 'Use statsmodels.stats.power.NormalIndPower().solve_power to back out MDE. Bonferroni '
                     'is simple: alpha_adj = 0.05 / 2 = 0.025. An underpowered non-significant result means '
                     "'inconclusive', not 'no effect'.",
             'depends_on': 'DSSTAT-3',
             'order': 5},
            {'jira_key': 'DSSTAT-6',
             'title': 'Write the ship/no-ship recommendation',
             'description': 'Summarize results in a decision memo: point estimates with CIs for both '
                            'metrics, corrected significance, effect sizes, power caveats, and a clear '
                            'recommendation with the reasoning a PM needs to act.',
             'acceptance_criteria': 'A memo section states a recommendation (ship / do-not-ship / extend '
                                    'test) justified by effect size, CIs, corrected p-values, and power — '
                                    'not p-value alone.',
             'hint': "Lead with the business metric and its CI, then the statistics. 'Conversion lifted "
                     '1.8pp (95% CI 0.4-3.2pp), significant after correction, medium effect — recommend '
                     "ship' is the target shape.",
             'depends_on': 'DSSTAT-5',
             'order': 6}]},
 {'technology_slug': 'data-science',
  'title': 'Build and Evaluate a Predictive Churn Model with scikit-learn',
  'slug': 'data-science-predictive-churn-model-sklearn',
  'architecture_type': 'custom',
  'description': 'You build an end-to-end supervised classification model that predicts customer churn from '
                 'a cleaned telecom dataset. You engineer features, assemble a leakage-free scikit-learn '
                 'Pipeline with preprocessing, train and tune a model with cross-validation, and evaluate it '
                 'with the metrics that matter for imbalanced data. The deliverable is a validated, '
                 'serialized model plus an honest performance report.',
  'objectives': ['Engineer features and split data without leaking information',
                 'Build a scikit-learn Pipeline combining preprocessing and a classifier',
                 'Tune hyperparameters with cross-validated GridSearchCV',
                 'Evaluate with precision, recall, ROC-AUC, and a confusion matrix on imbalanced classes',
                 'Interpret feature importance and serialize the model for reuse'],
  'difficulty': 'intermediate',
  'estimated_hours': 6,
  'order': 4,
  'tasks': [{'jira_key': 'DSMODEL-1',
             'title': 'Define target, features, and a stratified split',
             'description': 'Load churn.parquet, define y = churn (binary) and X = feature columns, drop '
                            'identifiers that would leak. Split with train_test_split(X, y, test_size=0.2, '
                            'stratify=y, random_state=42) so class balance is preserved in both sets.',
             'acceptance_criteria': 'X_train/X_test/y_train/y_test exist; y_train and y_test have similar '
                                    'churn rates (stratify worked); no ID or post-outcome columns remain in '
                                    'X.',
             'hint': "Drop columns that reveal the outcome (e.g. a 'cancellation_date') or unique IDs — they "
                     'cause leakage or memorization. random_state makes the split reproducible for the whole '
                     'project.',
             'order': 1},
            {'jira_key': 'DSMODEL-2',
             'title': 'Engineer features',
             'description': 'Create informative features on the training schema: tenure buckets, a '
                            'total-charges-per-month ratio, and flags for month-to-month contracts. Keep all '
                            'transformations expressible so they can live inside the pipeline (no manual '
                            'test-set edits).',
             'acceptance_criteria': 'At least two engineered features are added and justified in markdown; '
                                    'the same transformation logic is applicable to unseen data without '
                                    'referencing test rows.',
             'hint': 'Fit any statistics (means, bins) on train only. Prefer transformations that '
                     'generalize: pd.cut for tenure buckets with fixed edges, not quantiles computed on the '
                     'full dataset.',
             'depends_on': 'DSMODEL-1',
             'order': 2},
            {'jira_key': 'DSMODEL-3',
             'title': 'Build a preprocessing + model Pipeline',
             'description': 'Use ColumnTransformer to StandardScaler numeric columns and '
                            "OneHotEncoder(handle_unknown='ignore') categorical columns, wired into a "
                            "Pipeline ending in LogisticRegression(class_weight='balanced') as a baseline. "
                            'Fit on train and score on test.',
             'acceptance_criteria': 'A single Pipeline object fits on X_train and predicts on X_test without '
                                    'manual preprocessing; baseline accuracy and ROC-AUC are reported.',
             'hint': 'Putting preprocessing inside the Pipeline is what prevents leakage during '
                     "cross-validation — the scaler refits on each fold's training portion only. "
                     "handle_unknown='ignore' avoids crashes on unseen categories.",
             'depends_on': 'DSMODEL-2',
             'order': 3},
            {'jira_key': 'DSMODEL-4',
             'title': 'Tune hyperparameters with cross-validation',
             'description': "Wrap the pipeline in GridSearchCV with cv=5, scoring='roc_auc', searching a "
                            'small grid (e.g. LogisticRegression C values, or swap in RandomForestClassifier '
                            'with n_estimators/max_depth). Refit the best estimator on all training data.',
             'acceptance_criteria': 'GridSearchCV runs over at least three parameter combinations; '
                                    'best_params_ and best_score_ (CV ROC-AUC) are reported and the best '
                                    'estimator is retained.',
             'hint': "Reference pipeline steps in the grid with the step__param syntax, e.g. {'clf__C': "
                     "[0.1, 1, 10]}. scoring='roc_auc' optimizes ranking quality, which suits imbalanced "
                     'churn better than accuracy.',
             'depends_on': 'DSMODEL-3',
             'order': 4},
            {'jira_key': 'DSMODEL-5',
             'title': 'Evaluate with imbalance-aware metrics',
             'description': 'On the held-out test set, produce classification_report (precision/recall/F1), '
                            'a confusion matrix, and the ROC-AUC with an ROC curve. Discuss the '
                            'precision-recall trade-off and pick an operating threshold aligned to the '
                            'business cost of a missed churner.',
             'acceptance_criteria': 'classification_report, a confusion matrix, and ROC-AUC are shown for '
                                    'the test set; a note explains why accuracy alone is misleading here and '
                                    'justifies a chosen threshold.',
             'hint': 'Get probabilities with predict_proba(X_test)[:,1] and move the 0.5 threshold to trade '
                     'recall for precision. On imbalanced data a model can hit 90% accuracy while catching '
                     'almost no churners — recall on the positive class is what matters.',
             'depends_on': 'DSMODEL-4',
             'order': 5},
            {'jira_key': 'DSMODEL-6',
             'title': 'Interpret and serialize the model',
             'description': 'Extract feature importance (coefficients or feature_importances_, mapped back '
                            'through the OneHotEncoder names) and report the top drivers of churn. Serialize '
                            "the fitted pipeline with joblib.dump(best_model, 'churn_model.joblib') and "
                            'verify a reload predicts identically.',
             'acceptance_criteria': 'Top 5 churn drivers are listed with direction/magnitude; '
                                    'churn_model.joblib is written and a reloaded model reproduces identical '
                                    'predictions on a sample.',
             'hint': "Recover encoded names via the fitted ColumnTransformer's get_feature_names_out(). "
                     'Serialize the whole Pipeline (not just the classifier) so preprocessing travels with '
                     'the model.',
             'depends_on': 'DSMODEL-5',
             'order': 6}]},
 {'technology_slug': 'data-science',
  'title': 'Turn a Notebook into a Reproducible, Tested ML Pipeline',
  'slug': 'data-science-notebook-to-reproducible-pipeline',
  'architecture_type': 'cicd',
  'description': 'Your churn analysis lives in a sprawling notebook that only runs on your laptop. You '
                 'refactor it into a modular, config-driven Python project with pinned dependencies, a CLI '
                 'entry point, unit tests, and a CI workflow that trains and validates the model on every '
                 'push. The result is a pipeline a teammate can clone and run with one command, and that CI '
                 'guards against regressions.',
  'objectives': ['Refactor notebook code into importable, single-responsibility modules',
                 'Pin dependencies and make runs deterministic with fixed seeds and versions',
                 'Externalize configuration and expose a reproducible CLI entry point',
                 'Write unit and data-validation tests with pytest',
                 'Automate training and testing with a CI workflow'],
  'difficulty': 'advanced',
  'estimated_hours': 8,
  'order': 5,
  'tasks': [{'jira_key': 'DSPIPE-1',
             'title': 'Scaffold the project and pin dependencies',
             'description': 'Create a package layout (src/churn/ with ingest.py, features.py, model.py, '
                            'evaluate.py, plus tests/), a pyproject.toml or requirements.txt with pinned '
                            'versions, and a fresh virtual environment. Install with pip and record exact '
                            'versions via pip freeze.',
             'acceptance_criteria': 'A clean venv installs the project from the manifest with no errors, and '
                                    'dependencies are pinned to exact versions (==), not floating ranges.',
             'hint': 'Pin exact versions (pandas==2.2.2, scikit-learn==1.5.1) so a clone reproduces your '
                     'environment. python -m venv .venv then pip install -e . makes the package importable '
                     'in tests.',
             'order': 1},
            {'jira_key': 'DSPIPE-2',
             'title': 'Refactor notebook cells into modules',
             'description': 'Move the load/clean, feature-engineering, training, and evaluation logic out of '
                            'the notebook into pure functions in the corresponding modules (e.g. '
                            'features.build_features(df) -> df, model.train(X, y) -> pipeline). Remove '
                            'global state and hardcoded paths.',
             'acceptance_criteria': 'Each pipeline stage is an importable function with typed inputs/outputs '
                                    'and no side effects beyond returns; the notebook is reduced to calls '
                                    'into these modules.',
             'hint': 'One function, one responsibility, no reliance on notebook-order globals. Functions '
                     'that take inputs and return outputs (rather than mutating module state) are what make '
                     'the pipeline testable in DSPIPE-4.',
             'depends_on': 'DSPIPE-1',
             'order': 2},
            {'jira_key': 'DSPIPE-3',
             'title': 'Externalize config and build a CLI',
             'description': 'Move paths, the random seed, split ratio, and hyperparameters into config.yaml. '
                            'Add a CLI (argparse or Typer) so `python -m churn.run --config config.yaml` '
                            'executes ingest -> features -> train -> evaluate and writes churn_model.joblib '
                            'plus a metrics.json.',
             'acceptance_criteria': 'Running the CLI with the config end-to-end produces the model artifact '
                                    'and metrics.json; changing the seed in config changes outputs '
                                    'deterministically with no code edits.',
             'hint': 'Set every seed from config (numpy, sklearn random_state) so runs are reproducible. '
                     'Load YAML once at the entry point and thread the config object down — modules should '
                     'not read files directly.',
             'depends_on': 'DSPIPE-2',
             'order': 3},
            {'jira_key': 'DSPIPE-4',
             'title': 'Write unit and data-validation tests',
             'description': 'Add pytest tests: unit tests for build_features on a tiny fixture DataFrame, a '
                            'data-validation test asserting schema/nulls/ranges on ingest output, and a '
                            'smoke test that trains on a small sample and asserts ROC-AUC exceeds a floor.',
             'acceptance_criteria': 'pytest passes locally with at least one feature unit test, one '
                                    'data-validation test, and one training smoke test with a metric-floor '
                                    'assertion.',
             'hint': 'Build small inline fixtures with pd.DataFrame({...}) so tests run in milliseconds and '
                     "don't depend on the full dataset. A metric-floor assert (assert auc > 0.7) catches "
                     'silent model regressions.',
             'depends_on': 'DSPIPE-3',
             'order': 4},
            {'jira_key': 'DSPIPE-5',
             'title': 'Add reproducibility guarantees and a Makefile',
             'description': 'Add a Makefile with setup/train/test/lint targets, ensure all randomness is '
                            'seeded from config, and write metrics.json plus a data hash on each run so '
                            'identical inputs yield identical outputs. Document the one-command run in the '
                            'README.',
             'acceptance_criteria': '`make train` run twice on the same data and config produces identical '
                                    'metrics.json; the README documents the clone-to-run steps.',
             'hint': 'Hash the input file (hashlib.sha256) and record it in metrics.json so you can prove '
                     'which data produced a result. Determinism means same seed + same data + same versions '
                     '-> byte-identical metrics.',
             'depends_on': 'DSPIPE-4',
             'order': 5},
            {'jira_key': 'DSPIPE-6',
             'title': 'Automate with CI',
             'description': 'Add a GitHub Actions workflow (.github/workflows/ci.yml) that on push installs '
                            'pinned deps, runs pytest, lints (ruff/flake8), and executes the training smoke '
                            "run, failing the build if tests fail or the metric floor isn't met.",
             'acceptance_criteria': 'The workflow runs on push, installs from the pinned manifest, and fails '
                                    'the build when a test fails or ROC-AUC drops below the floor; a passing '
                                    'run is green.',
             'hint': "Cache pip with actions/setup-python's cache option to speed runs. Run the smoke train "
                     'in CI on a small sample so the job stays fast while still guarding the metric floor.',
             'depends_on': 'DSPIPE-5',
             'order': 6}]},
 {'technology_slug': 'nmap',
  'title': 'Nmap Fundamentals: Discover and Map Your Authorized Lab Network',
  'slug': 'nmap-fundamentals-host-discovery-lab',
  'architecture_type': 'custom',
  'description': "Stand up an ethical scanning workflow against your own isolated lab subnet using Nmap's "
                 'host discovery and basic port scanning. You will learn to identify which hosts are alive, '
                 'enumerate open ports, and read Nmap output correctly, all while operating strictly within '
                 'an authorized environment.',
  'objectives': ['Confirm scope and authorization before any scan and interpret ethical boundaries',
                 'Run host discovery (ping sweeps) to build a live-host inventory of a lab subnet',
                 'Perform a default TCP SYN scan and read the port state table (open/closed/filtered)',
                 'Control scan scope with target specification and port selection flags',
                 'Adjust timing/verbosity and understand why aggressive timing is risky'],
  'difficulty': 'beginner',
  'estimated_hours': 3,
  'order': 1,
  'tasks': [{'jira_key': 'NMAPFUN-1',
             'title': 'Verify Nmap install and confirm authorized scope',
             'description': 'Confirm Nmap is installed and record the version, then write down the exact '
                            'authorized target range (e.g. your lab subnet 10.10.0.0/24) that you are '
                            'permitted to scan. Scanning anything outside this range is out of scope.',
             'acceptance_criteria': '`nmap --version` prints a version >= 7.x, and a scope note lists '
                                    'exactly one authorized CIDR/range you own or control.',
             'hint': 'Run `nmap --version`. If missing, install via `sudo apt install nmap` or `sudo dnf '
                     'install nmap`. Document scope in a scope.txt file, e.g. `AUTHORIZED: 10.10.0.0/24 (my '
                     'lab)`.',
             'order': 1},
            {'jira_key': 'NMAPFUN-2',
             'title': 'Run a host discovery ping sweep',
             'description': 'Use a no-port-scan ping sweep to find which hosts in the authorized subnet are '
                            'alive. This avoids touching ports and is the correct first step for building an '
                            'inventory.',
             'acceptance_criteria': 'A ping sweep of the authorized subnet completes and produces a list of '
                                    'at least one host reported as `Host is up`.',
             'hint': 'Use `nmap -sn 10.10.0.0/24`. The `-sn` flag disables port scanning and only performs '
                     'host discovery.',
             'order': 2,
             'depends_on': 'NMAPFUN-1'},
            {'jira_key': 'NMAPFUN-3',
             'title': 'Run a default TCP SYN scan on one live host',
             'description': 'Pick one live host from your inventory and run a default scan (top 1000 TCP '
                            'ports) to see which ports are open. Read the resulting port state table '
                            'carefully.',
             'acceptance_criteria': '`nmap <host>` completes and prints a PORT/STATE/SERVICE table; you can '
                                    'name at least one port and its reported state.',
             'hint': 'Run `sudo nmap 10.10.0.5` (SYN scan `-sS` is the default when run as root). Note the '
                     'STATE column shows open, closed, or filtered.',
             'order': 3,
             'depends_on': 'NMAPFUN-2'},
            {'jira_key': 'NMAPFUN-4',
             'title': 'Control port selection and target specification',
             'description': 'Scan a specific set of ports and a full port range on a host to understand '
                            'target/port syntax. Compare scanning the top ports vs a specific list.',
             'acceptance_criteria': 'You produce output from both a specific-port scan (e.g. `-p 22,80,443`) '
                                    'and a full-range scan (`-p-`), and can explain the difference in '
                                    'coverage.',
             'hint': 'Use `nmap -p 22,80,443 <host>` for a list and `nmap -p- <host>` for all 65535 ports. '
                     'Ranges like `-p 1-1024` also work.',
             'order': 4,
             'depends_on': 'NMAPFUN-3'},
            {'jira_key': 'NMAPFUN-5',
             'title': 'Tune timing and verbosity, then explain the tradeoffs',
             'description': 'Re-run a scan with increased verbosity and an explicit timing template, and '
                            'document why very aggressive timing (-T5) can cause dropped packets, inaccurate '
                            'results, or disruption on fragile lab devices.',
             'acceptance_criteria': 'A scan run with `-v` and a `-T` template completes, and a short note '
                                    'explains when a slower timing template is preferable.',
             'hint': 'Try `nmap -v -T3 <host>` (T3 is the default/normal). Compare against `-T4`. Note that '
                     '`-T5` (insane) trades reliability for speed.',
             'order': 5,
             'depends_on': 'NMAPFUN-4'}]},
 {'technology_slug': 'nmap',
  'title': 'Service and OS Fingerprinting: Build a Detailed Asset Profile',
  'slug': 'nmap-service-version-os-fingerprinting',
  'architecture_type': 'custom',
  'description': 'Go beyond open/closed ports and produce a rich fingerprint of authorized lab hosts, '
                 'including running service versions and a best-guess operating system. You will combine '
                 'version detection, OS detection, and UDP scanning into a repeatable profiling workflow and '
                 'learn how to read confidence levels honestly.',
  'objectives': ['Perform service/version detection and interpret the VERSION column and CPE strings',
                 'Run OS detection and reason about accuracy, fingerprint confidence, and guesses',
                 'Scan UDP services and understand why UDP scans are slow and often open|filtered',
                 'Combine flags into an aggressive-profile scan and read the extra data it returns',
                 'Assemble findings into a per-host asset profile'],
  'difficulty': 'beginner',
  'estimated_hours': 4,
  'order': 2,
  'tasks': [{'jira_key': 'NMAPFP-1',
             'title': 'Detect service versions on open ports',
             'description': 'Run version detection against a lab host so Nmap probes open ports and reports '
                            'the software and version behind each service (e.g. OpenSSH 8.9, nginx 1.24). '
                            'Note the CPE identifiers where present.',
             'acceptance_criteria': '`nmap -sV <host>` output shows a VERSION column populated for at least '
                                    'one open port, including product and version where detectable.',
             'hint': 'Use `nmap -sV 10.10.0.5`. Add `--version-intensity 9` for maximum probing if a service '
                     'is stubborn.',
             'order': 1},
            {'jira_key': 'NMAPFP-2',
             'title': 'Run OS detection and evaluate confidence',
             'description': 'Perform OS detection on a host and read the resulting OS guess(es). Because OS '
                            'detection relies on TCP/IP stack fingerprinting, capture the '
                            'accuracy/confidence and note when Nmap prints multiple guesses instead of a '
                            'definitive answer.',
             'acceptance_criteria': '`sudo nmap -O <host>` returns an OS match or ranked guesses; you record '
                                    'the reported accuracy percentage and whether it needed at least one '
                                    'open and one closed port.',
             'hint': 'Run `sudo nmap -O 10.10.0.5`. OS detection needs root and works best with '
                     '`--osscan-guess` when no exact match is found.',
             'order': 2},
            {'jira_key': 'NMAPFP-3',
             'title': 'Scan common UDP services',
             'description': 'Run a targeted UDP scan against well-known UDP ports (DNS 53, SNMP 161, NTP '
                            '123) on a lab host. Observe why UDP scanning is slow and why many results come '
                            'back as open|filtered.',
             'acceptance_criteria': '`sudo nmap -sU -p 53,123,161 <host>` completes and you can explain what '
                                    'open|filtered means for a UDP port.',
             'hint': 'Use `sudo nmap -sU -p 53,123,161 10.10.0.5`. UDP has no handshake, so no response is '
                     'ambiguous - hence open|filtered.',
             'order': 3},
            {'jira_key': 'NMAPFP-4',
             'title': 'Run the aggressive scan profile',
             'description': 'Combine version detection, OS detection, default scripts, and traceroute into a '
                            'single aggressive scan (-A) against an authorized host, and identify each '
                            'category of extra data it produces.',
             'acceptance_criteria': '`sudo nmap -A <host>` completes and you can point to version info, OS '
                                    'guess, at least one default-script result, and traceroute hops in the '
                                    'output.',
             'hint': 'Run `sudo nmap -A 10.10.0.5`. `-A` is equivalent to `-sV -O -sC --traceroute` '
                     'combined; it is loud, so only use in-scope.',
             'order': 4,
             'depends_on': 'NMAPFP-1'},
            {'jira_key': 'NMAPFP-5',
             'title': 'Assemble a per-host asset profile',
             'description': 'Consolidate the version, OS, and UDP findings for one host into a single asset '
                            'profile document capturing hostname/IP, open TCP/UDP ports, detected services '
                            'with versions, and the OS best guess with its confidence.',
             'acceptance_criteria': 'A profile document exists for one host listing IP, open ports, service '
                                    'versions, and an OS guess with the confidence level stated.',
             'hint': 'Save the aggressive scan to a file with `-oN host-profile.txt` and hand-edit it into a '
                     'clean summary, or start from `nmap -A -oN host-profile.txt 10.10.0.5`.',
             'order': 5,
             'depends_on': 'NMAPFP-4'}]},
 {'technology_slug': 'nmap',
  'title': 'NSE Scripting: Safe Enumeration with the Nmap Scripting Engine',
  'slug': 'nmap-nse-scripting-enumeration',
  'architecture_type': 'custom',
  'description': 'Learn to drive the Nmap Scripting Engine (NSE) to automate deeper, defensive enumeration '
                 'of authorized services. You will explore script categories, run safe discovery and '
                 'vuln-check scripts, pass script arguments, and interpret findings responsibly without '
                 'weaponizing them.',
  'objectives': ['Navigate NSE script categories (safe, default, discovery, vuln, auth) and locate scripts',
                 'Run default and category-selected scripts against authorized services',
                 'Pass script arguments with --script-args to control script behavior',
                 'Use safe vuln-category scripts to flag potential exposures without exploiting them',
                 'Read NSE output and update scripts responsibly with nmap --script-updatedb'],
  'difficulty': 'intermediate',
  'estimated_hours': 4,
  'order': 3,
  'tasks': [{'jira_key': 'NSE-1',
             'title': 'Explore the NSE script library and categories',
             'description': 'Locate the installed NSE scripts and list them by category so you understand '
                            'what is available. Identify which categories are considered safe versus '
                            'intrusive.',
             'acceptance_criteria': 'You can list scripts in the `safe` and `default` categories and name at '
                                    'least one script that is NOT in the safe category.',
             'hint': 'Scripts live under `/usr/share/nmap/scripts/`. Use `ls /usr/share/nmap/scripts/ | grep '
                     'http` to explore, and `nmap --script-help "safe"` to read category membership.',
             'order': 1},
            {'jira_key': 'NSE-2',
             'title': 'Run default scripts against a service',
             'description': 'Use the default script set (-sC) alongside version detection against an '
                            'authorized web or SSH host and read the enriched output (banners, headers, '
                            'supported methods).',
             'acceptance_criteria': '`nmap -sC -sV <host>` completes and shows at least one script result '
                                    'block (e.g. http-title, ssh-hostkey) under an open port.',
             'hint': 'Run `nmap -sC -sV 10.10.0.5`. `-sC` runs the `default` script category, which is a '
                     'curated safe-ish subset.',
             'order': 2,
             'depends_on': 'NSE-1'},
            {'jira_key': 'NSE-3',
             'title': 'Select scripts by name and category',
             'description': 'Run a specific script and a category selection to target enumeration. For '
                            'example enumerate HTTP methods and directories, or SMB shares, on the '
                            'appropriate authorized host.',
             'acceptance_criteria': 'You successfully run both a named script (e.g. `--script http-methods`) '
                                    'and a category (e.g. `--script discovery`) and capture their output.',
             'hint': 'Use `nmap --script http-methods -p 80 <host>` and `nmap --script discovery <host>`. '
                     'You can combine with `and`/`or` logic, e.g. `--script "http-* and safe"`.',
             'order': 3,
             'depends_on': 'NSE-2'},
            {'jira_key': 'NSE-4',
             'title': 'Pass arguments to a script with --script-args',
             'description': "Control a script's behavior by supplying arguments, for example setting an HTTP "
                            'path or limiting a brute-force wordlist size in your lab. Demonstrate reading '
                            'argument names from script help.',
             'acceptance_criteria': 'A scan runs a script with at least one `--script-args` key=value pair '
                                    'that visibly changes behavior versus the default run.',
             'hint': 'Read args via `nmap --script-help http-enum`. Then run e.g. `nmap --script http-enum '
                     '--script-args http-enum.basepath=/app/ -p 80 <host>`.',
             'order': 4,
             'depends_on': 'NSE-3'},
            {'jira_key': 'NSE-5',
             'title': 'Run safe vuln-category checks and interpret responsibly',
             'description': 'Run vuln-category scripts (which flag potential known exposures) against an '
                            'authorized host, then write a short note distinguishing detection from '
                            'exploitation and how you would validate a flagged finding.',
             'acceptance_criteria': '`nmap --script vuln <host>` completes, and a note explains that a '
                                    'flagged CVE is a lead to verify, not proof, and must not be exploited '
                                    'without authorization.',
             'hint': 'Run `nmap --script vuln 10.10.0.5`. Many vuln scripts are `safe`; treat any hit as a '
                     'lead for defensive follow-up, never as license to exploit.',
             'order': 5,
             'depends_on': 'NSE-4'},
            {'jira_key': 'NSE-6',
             'title': 'Refresh the script database',
             'description': 'After adding or updating scripts, rebuild the NSE script database so category '
                            'and name lookups resolve correctly, then confirm a category lookup still works.',
             'acceptance_criteria': '`sudo nmap --script-updatedb` completes without error and a subsequent '
                                    '`--script-help` category query resolves.',
             'hint': 'Run `sudo nmap --script-updatedb`. This regenerates '
                     '`/usr/share/nmap/scripts/script.db` used to resolve `--script` category names.',
             'order': 6,
             'depends_on': 'NSE-1'}]},
 {'technology_slug': 'nmap',
  'title': 'Output, Reporting, and Scan Comparison for Defensive Ops',
  'slug': 'nmap-output-reporting-scan-diff',
  'architecture_type': 'custom',
  'description': "Turn raw scans into durable, shareable defensive artifacts. You will master Nmap's output "
                 'formats, generate machine-readable XML, convert results to HTML reports, and use ndiff to '
                 'detect drift between two point-in-time scans, the core loop of continuous attack-surface '
                 'monitoring.',
  'objectives': ['Save scans in normal, grepable, and XML formats with -oA',
                 'Post-process grepable output to extract just the data you need',
                 'Convert XML scan results into a human-readable HTML report',
                 'Use ndiff to compare two scans and identify newly opened or closed ports',
                 'Establish a baseline-and-recheck workflow for attack-surface monitoring'],
  'difficulty': 'intermediate',
  'estimated_hours': 4,
  'order': 4,
  'tasks': [{'jira_key': 'NMAPRPT-1',
             'title': 'Capture a baseline scan in all output formats',
             'description': 'Run a service-detection scan against an authorized host or subnet and save it '
                            'in normal, grepable, and XML formats simultaneously to establish a baseline.',
             'acceptance_criteria': 'Running the scan produces three files (`.nmap`, `.gnmap`, `.xml`) '
                                    'sharing one basename via `-oA`.',
             'hint': 'Use `nmap -sV -oA baseline 10.10.0.0/24`. `-oA baseline` writes baseline.nmap, '
                     'baseline.gnmap, and baseline.xml at once.',
             'order': 1},
            {'jira_key': 'NMAPRPT-2',
             'title': 'Extract data from grepable output',
             'description': 'Parse the grepable (.gnmap) file to produce a clean list of hosts with a '
                            'specific open port, demonstrating why grepable output exists for pipeline use.',
             'acceptance_criteria': 'A command pipeline reads the .gnmap file and prints only the IPs that '
                                    'have a chosen port open.',
             'hint': 'Try `grep "open" baseline.gnmap | grep "80/open" | awk \'{print $2}\'`. Grepable '
                     'format keeps one host per line for easy filtering.',
             'order': 2,
             'depends_on': 'NMAPRPT-1'},
            {'jira_key': 'NMAPRPT-3',
             'title': 'Generate an HTML report from XML',
             'description': 'Transform the XML scan output into a styled HTML report using the bundled XSL '
                            'stylesheet so findings can be shared with stakeholders.',
             'acceptance_criteria': 'An HTML file is produced from baseline.xml and opens in a browser '
                                    'showing the scan results in a formatted layout.',
             'hint': 'Use `xsltproc baseline.xml -o baseline.html`. Nmap embeds a reference to nmap.xsl; if '
                     'styling is missing, copy nmap.xsl locally or use `--stylesheet`.',
             'order': 3,
             'depends_on': 'NMAPRPT-1'},
            {'jira_key': 'NMAPRPT-4',
             'title': 'Run a second scan after a change',
             'description': 'Introduce a deliberate, authorized change in the lab (e.g. start or stop a '
                            'service so a port opens or closes), then run an identical scan saved with a new '
                            'basename for comparison.',
             'acceptance_criteria': 'A second XML scan (`recheck.xml`) exists, taken with the same '
                                    'flags/targets as the baseline but after a known change.',
             'hint': 'Repeat `nmap -sV -oA recheck 10.10.0.0/24` after toggling a service. Keep flags and '
                     'targets identical so the diff is meaningful.',
             'order': 4,
             'depends_on': 'NMAPRPT-1'},
            {'jira_key': 'NMAPRPT-5',
             'title': 'Diff two scans with ndiff',
             'description': 'Compare the baseline and recheck XML files with ndiff to surface exactly what '
                            'changed, then interpret added/removed ports as attack-surface drift.',
             'acceptance_criteria': '`ndiff baseline.xml recheck.xml` output clearly shows the port(s) that '
                                    'were added or removed, matching the change you made.',
             'hint': 'Run `ndiff baseline.xml recheck.xml`. Lines prefixed with `+` are newly seen, `-` are '
                     'gone. This is your drift signal.',
             'order': 5,
             'depends_on': 'NMAPRPT-4'},
            {'jira_key': 'NMAPRPT-6',
             'title': 'Document a baseline-and-recheck monitoring workflow',
             'description': 'Write a short runbook describing how to schedule periodic scans, store dated '
                            'baselines, diff against the last known-good, and alert on unexpected new ports.',
             'acceptance_criteria': 'A runbook document describes the scan command, storage naming '
                                    'convention, the ndiff comparison step, and what constitutes an '
                                    'alert-worthy change.',
             'hint': 'Structure it as: 1) scan with `-oX scan-$(date +%F).xml`, 2) `ndiff previous.xml '
                     'scan-today.xml`, 3) escalate on any unexpected `+ ...open` line.',
             'order': 6,
             'depends_on': 'NMAPRPT-5'}]},
 {'technology_slug': 'nmap',
  'title': 'Advanced Nmap: Evasion Awareness and Firewall/IDS Reconnaissance',
  'slug': 'nmap-advanced-firewall-ids-recon',
  'architecture_type': 'custom',
  'description': 'In an isolated authorized lab with a firewall and an IDS/IPS in the path, study how Nmap '
                 'distinguishes filtered from closed ports and how various scan techniques and '
                 'packet-crafting options interact with defenses. The goal is defensive understanding: to '
                 'learn how your own perimeter responds and how a blue team detects noisy scans, never to '
                 'bypass systems you do not own.',
  'objectives': ['Differentiate filtered vs closed vs open|filtered using multiple scan types',
                 'Use ACK and Window scans to map firewall rule state (stateful vs stateless)',
                 'Apply packet-crafting options (fragmentation, decoys, source port) and understand '
                 'detectability',
                 "Correlate scans against IDS/firewall logs to see the defender's view",
                 'Produce a perimeter-response report recommending detection improvements'],
  'difficulty': 'advanced',
  'estimated_hours': 6,
  'order': 5,
  'tasks': [{'jira_key': 'NMAPADV-1',
             'title': 'Establish a firewalled lab and classify port states',
             'description': 'Against an authorized host sitting behind a lab firewall, run a SYN scan and '
                            'identify ports reported as filtered versus closed versus open, then explain '
                            'what the firewall response (or silence) implies for each state.',
             'acceptance_criteria': 'A `sudo nmap -sS <host>` scan shows at least one filtered and one '
                                    'non-filtered port, and you correctly explain why filtered differs from '
                                    'closed.',
             'hint': 'Run `sudo nmap -sS -p- 10.10.0.20`. Filtered means no/ICMP-unreachable response '
                     '(firewall drop/reject); closed means an RST came back.',
             'order': 1},
            {'jira_key': 'NMAPADV-2',
             'title': 'Map firewall statefulness with ACK and Window scans',
             'description': 'Use an ACK scan to classify ports as filtered vs unfiltered (revealing whether '
                            'a firewall is stateful), then a Window scan for extra fidelity, and compare '
                            'against the SYN scan results.',
             'acceptance_criteria': '`sudo nmap -sA <host>` and `sudo nmap -sW <host>` complete, and you '
                                    'explain what unfiltered vs filtered from an ACK scan says about the '
                                    "firewall's statefulness.",
             'hint': 'Run `sudo nmap -sA 10.10.0.20` then `sudo nmap -sW 10.10.0.20`. ACK scans never show '
                     'open - they only reveal whether a stateful firewall is filtering.',
             'order': 2,
             'depends_on': 'NMAPADV-1'},
            {'jira_key': 'NMAPADV-3',
             'title': 'Experiment with packet-crafting options',
             'description': 'Against your own authorized target, try fragmentation, a spoofed source port, '
                            'and decoy addresses (all decoys inside your own lab), observing how each '
                            'changes the packets on the wire. This is to understand detectability, not to '
                            'evade a third party.',
             'acceptance_criteria': 'You run scans using `-f`, `--source-port`, and `-D` (with in-scope '
                                    'decoys) and can describe what each option changes at the packet level.',
             'hint': 'Try `sudo nmap -f 10.10.0.20`, `sudo nmap --source-port 53 10.10.0.20`, and `sudo nmap '
                     '-D 10.10.0.21,10.10.0.22 10.10.0.20`. Only use decoy IPs you control.',
             'order': 3,
             'depends_on': 'NMAPADV-2'},
            {'jira_key': 'NMAPADV-4',
             'title': "Capture the defender's view in IDS/firewall logs",
             'description': 'While repeating a noisy scan, inspect the lab IDS (e.g. Suricata/Snort) alerts '
                            'and firewall logs to correlate which scan behaviors triggered detection. This '
                            'builds blue-team intuition about what scanning looks like from the other side.',
             'acceptance_criteria': 'IDS or firewall logs show alert/deny entries that you can tie back to a '
                                    'specific scan you ran (e.g. a SYN sweep or a fragmented scan).',
             'hint': 'Tail the IDS log during the scan, e.g. `sudo tail -f /var/log/suricata/fast.log`, and '
                     "watch firewall drops with `sudo journalctl -f` or your firewall's log. Note timestamps "
                     'to correlate.',
             'order': 4,
             'depends_on': 'NMAPADV-3'},
            {'jira_key': 'NMAPADV-5',
             'title': 'Compare timing templates against detection',
             'description': 'Run the same scan at a stealthy slow timing and at an aggressive fast timing, '
                            'and compare how each is (or is not) flagged by the IDS to understand the '
                            'speed-versus-noise tradeoff from a detection standpoint.',
             'acceptance_criteria': 'You run the scan with a slow template (e.g. `-T1`) and a fast one (e.g. '
                                    '`-T4`), and document the difference in IDS alert volume or completeness '
                                    'between them.',
             'hint': 'Compare `sudo nmap -T1 -p- 10.10.0.20` against `sudo nmap -T4 -p- 10.10.0.20`. Slower '
                     'scans (`-T0`/`-T1`) spread packets out and often generate fewer/rate-based alerts.',
             'order': 5,
             'depends_on': 'NMAPADV-4'},
            {'jira_key': 'NMAPADV-6',
             'title': 'Write a perimeter-response and detection report',
             'description': 'Synthesize the SYN/ACK/Window results, packet-crafting observations, and IDS '
                            'correlation into a defensive report that documents how the perimeter responded '
                            'and recommends concrete detection/hardening improvements.',
             'acceptance_criteria': 'A report documents observed port states, firewall statefulness '
                                    'findings, which scans evaded or triggered detection, and at least two '
                                    'actionable blue-team recommendations.',
             'hint': 'Frame recommendations defensively: e.g. add rate-based IDS rules for fragmented '
                     'packets, alert on ACK-scan patterns, and log dropped connections. Keep everything '
                     'scoped to systems you own.',
             'order': 6,
             'depends_on': 'NMAPADV-5'}]},
 {'technology_slug': 'sqlite',
  'title': 'Design and Build Your First SQLite Database',
  'slug': 'sqlite-bookshelf-schema-crud',
  'architecture_type': 'custom',
  'description': 'Create a single-file SQLite database for a personal bookshelf app from scratch, designing '
                 'a normalized schema with primary and foreign keys, then loading and querying real data. '
                 'You will finish with a working .db file you can inspect with the sqlite3 CLI and '
                 'understand every table, type affinity, and constraint you created.',
  'objectives': ['Create a SQLite database file and connect with the sqlite3 CLI',
                 'Design a normalized schema using PRIMARY KEY, FOREIGN KEY, NOT NULL, and UNIQUE '
                 'constraints',
                 'Understand SQLite type affinity and use appropriate column types',
                 'Perform INSERT, SELECT, UPDATE, and DELETE operations and verify results',
                 'Enforce referential integrity with PRAGMA foreign_keys=ON'],
  'difficulty': 'beginner',
  'estimated_hours': 3,
  'order': 1,
  'tasks': [{'jira_key': 'BOOK-1',
             'title': 'Create the database file and open a session',
             'description': 'Install/verify the sqlite3 CLI and create a new database file named '
                            'bookshelf.db. Open an interactive session and confirm the SQLite version. An '
                            'empty database file is created on first write, so create a throwaway table to '
                            'force the file to exist on disk.',
             'acceptance_criteria': "Running `sqlite3 bookshelf.db '.tables'` succeeds with no error, and "
                                    "`sqlite3 bookshelf.db 'SELECT sqlite_version();'` prints a version "
                                    'string like 3.x.',
             'hint': 'Run `sqlite3 bookshelf.db` to open a session. Inside, run `.databases` to confirm the '
                     'file path, then `SELECT sqlite_version();`. Use `.quit` to exit.',
             'order': 1},
            {'jira_key': 'BOOK-2',
             'title': 'Design the authors and books tables',
             'description': 'Create an `authors` table (id INTEGER PRIMARY KEY, name TEXT NOT NULL, country '
                            'TEXT) and a `books` table (id INTEGER PRIMARY KEY, title TEXT NOT NULL, '
                            'author_id INTEGER REFERENCES authors(id), published_year INTEGER, isbn TEXT '
                            'UNIQUE). Note that INTEGER PRIMARY KEY becomes an alias for the rowid.',
             'acceptance_criteria': '`.schema` shows both tables with the correct columns, the FOREIGN KEY '
                                    'on books.author_id, and the UNIQUE constraint on isbn.',
             'hint': 'Use `CREATE TABLE authors (id INTEGER PRIMARY KEY, name TEXT NOT NULL, country TEXT);` '
                     'then `CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT NOT NULL, author_id '
                     'INTEGER REFERENCES authors(id), published_year INTEGER, isbn TEXT UNIQUE);`. Verify '
                     'with `.schema`.',
             'order': 2,
             'depends_on': 'BOOK-1'},
            {'jira_key': 'BOOK-3',
             'title': 'Enable foreign key enforcement',
             'description': 'SQLite does NOT enforce foreign keys by default per connection. Turn '
                            'enforcement on and prove it by attempting an insert into books with a '
                            'non-existent author_id and observing the rejection.',
             'acceptance_criteria': 'After `PRAGMA foreign_keys=ON;`, inserting a book with author_id=999 '
                                    '(which does not exist) fails with a FOREIGN KEY constraint failed '
                                    'error.',
             'hint': 'Run `PRAGMA foreign_keys=ON;` first, then try `INSERT INTO books(title, author_id) '
                     "VALUES('Orphan', 999);`. You must re-run the PRAGMA on every new connection.",
             'order': 3,
             'depends_on': 'BOOK-2'},
            {'jira_key': 'BOOK-4',
             'title': 'Load seed data with INSERT',
             'description': 'Insert at least 3 authors, then insert at least 6 books referencing those '
                            'authors using the correct author_id values. Use a multi-row VALUES insert to '
                            'practice batch loading.',
             'acceptance_criteria': '`SELECT COUNT(*) FROM authors;` returns >= 3 and `SELECT COUNT(*) FROM '
                                    "books;` returns >= 6, with every book's author_id matching a real "
                                    'author.',
             'hint': "Insert authors first: `INSERT INTO authors(name,country) VALUES('Le "
                     "Guin','USA'),('Adichie','Nigeria');`. Then reference their ids in the books insert. "
                     'Check ids with `SELECT id,name FROM authors;`.',
             'order': 4,
             'depends_on': 'BOOK-3'},
            {'jira_key': 'BOOK-5',
             'title': 'Query, update, and delete records',
             'description': 'Write a JOIN to list each book title alongside its author name. Then UPDATE one '
                            "book's published_year and DELETE one book, verifying each change with a "
                            'follow-up SELECT.',
             'acceptance_criteria': 'The JOIN query returns book titles with matching author names; the '
                                    'UPDATE changes exactly one row; the DELETE removes exactly one row '
                                    'confirmed by row counts before and after.',
             'hint': 'Join with `SELECT b.title, a.name FROM books b JOIN authors a ON a.id=b.author_id;`. '
                     "Update with `UPDATE books SET published_year=2001 WHERE title='...';` and confirm with "
                     '`SELECT changes();`.',
             'order': 5,
             'depends_on': 'BOOK-4'},
            {'jira_key': 'BOOK-6',
             'title': 'Inspect the database and export as SQL',
             'description': 'Use CLI dot-commands to inspect the schema and data, then dump the entire '
                            'database to a portable .sql text file that could recreate it from scratch. This '
                            'teaches how SQLite databases are inspected and shared.',
             'acceptance_criteria': '`.dump` produces a SQL script containing CREATE TABLE and INSERT '
                                    'statements; running `sqlite3 bookshelf.db .dump > bookshelf.sql` '
                                    'creates a non-empty file, and `.schema books` shows the table '
                                    'definition.',
             'hint': 'Inside the session run `.mode column` and `.headers on` for readable output, then '
                     '`.dump` to see the full script. From the shell: `sqlite3 bookshelf.db .dump > '
                     'bookshelf.sql`.',
             'order': 6,
             'depends_on': 'BOOK-5'}]},
 {'technology_slug': 'sqlite',
  'title': 'Transactions and Data Integrity for a Ledger App',
  'slug': 'sqlite-ledger-transactions-integrity',
  'architecture_type': 'custom',
  'description': 'Build the persistence layer for a simple money-transfer ledger where correctness is '
                 'non-negotiable. You will use explicit transactions, savepoints, and CHECK constraints to '
                 'guarantee that balances never go negative and that transfers are atomic even under errors.',
  'objectives': ['Use BEGIN, COMMIT, and ROLLBACK to make multi-statement operations atomic',
                 'Enforce business rules with CHECK constraints and triggers',
                 'Use SAVEPOINT for nested/partial rollback within a transaction',
                 "Understand SQLite's default deferred transactions vs IMMEDIATE/EXCLUSIVE",
                 'Verify integrity invariants after simulated failures'],
  'difficulty': 'beginner',
  'estimated_hours': 4,
  'order': 2,
  'tasks': [{'jira_key': 'LEDG-1',
             'title': 'Create accounts and transfers schema',
             'description': 'Create an `accounts` table (id INTEGER PRIMARY KEY, owner TEXT NOT NULL, '
                            'balance_cents INTEGER NOT NULL CHECK(balance_cents >= 0)) and a `transfers` '
                            'table logging (id, from_id, to_id, amount_cents, created_at TEXT DEFAULT '
                            'CURRENT_TIMESTAMP). Store money as integer cents to avoid floating-point '
                            'errors.',
             'acceptance_criteria': '`.schema accounts` shows the CHECK(balance_cents >= 0) constraint, and '
                                    'inserting an account with balance_cents = -100 fails.',
             'hint': 'Use `CREATE TABLE accounts(id INTEGER PRIMARY KEY, owner TEXT NOT NULL, balance_cents '
                     'INTEGER NOT NULL CHECK(balance_cents >= 0));`. Test the constraint with `INSERT INTO '
                     "accounts(owner,balance_cents) VALUES('x',-100);`.",
             'order': 1},
            {'jira_key': 'LEDG-2',
             'title': 'Seed two accounts with starting balances',
             'description': 'Insert two accounts, e.g. Alice with 10000 cents and Bob with 0 cents. Record '
                            'the initial total balance across all accounts; this sum must stay constant '
                            'through every valid transfer.',
             'acceptance_criteria': '`SELECT SUM(balance_cents) FROM accounts;` returns 10000, and both '
                                    'accounts exist with the expected owners.',
             'hint': "Run `INSERT INTO accounts(owner,balance_cents) VALUES('Alice',10000),('Bob',0);` then "
                     '`SELECT owner,balance_cents FROM accounts;`.',
             'order': 2,
             'depends_on': 'LEDG-1'},
            {'jira_key': 'LEDG-3',
             'title': 'Perform an atomic transfer with an explicit transaction',
             'description': 'Transfer 3000 cents from Alice to Bob inside a single transaction: debit one '
                            'account, credit the other, and log the transfer, then COMMIT. All three '
                            'statements must succeed or none of them should apply.',
             'acceptance_criteria': 'After COMMIT, Alice has 7000 and Bob has 3000, a row exists in '
                                    'transfers, and SUM(balance_cents) is still 10000.',
             'hint': "`BEGIN; UPDATE accounts SET balance_cents=balance_cents-3000 WHERE owner='Alice'; "
                     "UPDATE accounts SET balance_cents=balance_cents+3000 WHERE owner='Bob'; INSERT INTO "
                     'transfers(from_id,to_id,amount_cents) VALUES(1,2,3000); COMMIT;`',
             'order': 3,
             'depends_on': 'LEDG-2'},
            {'jira_key': 'LEDG-4',
             'title': 'Trigger a rollback on an overdraft attempt',
             'description': 'Attempt to transfer 50000 cents from Alice (who lacks the funds) inside a '
                            'transaction. The debit should violate the CHECK(balance_cents >= 0) constraint; '
                            'catch the failure and ROLLBACK so no partial change is applied.',
             'acceptance_criteria': 'After the failed transfer and ROLLBACK, balances are unchanged (Alice '
                                    '7000, Bob 3000) and no new transfers row was committed.',
             'hint': "`BEGIN; UPDATE accounts SET balance_cents=balance_cents-50000 WHERE owner='Alice';` "
                     'will raise CHECK constraint failed. Then issue `ROLLBACK;` and re-check balances with '
                     'a SELECT.',
             'order': 4,
             'depends_on': 'LEDG-3'},
            {'jira_key': 'LEDG-5',
             'title': 'Use a SAVEPOINT for partial rollback',
             'description': 'Open a transaction, apply a valid transfer, create a SAVEPOINT, attempt a '
                            'second risky transfer, then ROLLBACK TO the savepoint to undo only the second '
                            'operation while keeping the first, and COMMIT.',
             'acceptance_criteria': 'The first transfer within the transaction persists after COMMIT while '
                                    'the operation after the savepoint is discarded, verified by final '
                                    'balances and transfers rows.',
             'hint': '`BEGIN; UPDATE...; SAVEPOINT sp1; UPDATE...(risky); ROLLBACK TO sp1; RELEASE sp1; '
                     'COMMIT;`. Only work before SAVEPOINT sp1 survives.',
             'order': 5,
             'depends_on': 'LEDG-4'},
            {'jira_key': 'LEDG-6',
             'title': 'Add a trigger to enforce a transfer-logging invariant',
             'description': 'Create an AFTER UPDATE trigger (or a CHECK via a trigger) that prevents a '
                            'balance from being changed without validation, or a trigger that auto-stamps an '
                            'audit column. Demonstrate that the trigger fires by inspecting its effect after '
                            'an update.',
             'acceptance_criteria': "`SELECT name FROM sqlite_master WHERE type='trigger';` lists the new "
                                    "trigger, and performing an update produces the trigger's documented "
                                    'side effect (e.g., an audit row or blocked invalid change).',
             'hint': 'Example: `CREATE TRIGGER log_balance AFTER UPDATE OF balance_cents ON accounts BEGIN '
                     'INSERT INTO transfers(from_id,to_id,amount_cents) '
                     'VALUES(NEW.id,NEW.id,NEW.balance_cents-OLD.balance_cents); END;`. Use '
                     "`RAISE(ABORT,'...')` inside a trigger to block invalid changes.",
             'order': 6,
             'depends_on': 'LEDG-5'}]},
 {'technology_slug': 'sqlite',
  'title': 'Query Optimization: Indexes and EXPLAIN QUERY PLAN',
  'slug': 'sqlite-index-query-optimization',
  'architecture_type': 'custom',
  'description': 'Take a slow analytics query over a large events table and make it fast using the right '
                 'indexes. You will read EXPLAIN QUERY PLAN output, distinguish table scans from index '
                 'searches, build single-column, composite, and covering indexes, and measure the difference '
                 'with real timing.',
  'objectives': ['Read and interpret EXPLAIN QUERY PLAN output (SCAN vs SEARCH)',
                 'Create single-column, composite, and partial indexes to satisfy queries',
                 'Design a covering index that avoids table lookups',
                 'Use ANALYZE and sqlite_stat1 so the planner picks good indexes',
                 'Measure query performance before and after optimization'],
  'difficulty': 'intermediate',
  'estimated_hours': 5,
  'order': 3,
  'tasks': [{'jira_key': 'IDX-1',
             'title': 'Generate a large events table',
             'description': 'Create an `events` table (id INTEGER PRIMARY KEY, user_id INTEGER, event_type '
                            'TEXT, created_at TEXT, amount REAL) and populate it with ~200,000 rows using a '
                            'recursive CTE so you have a realistic dataset to optimize against.',
             'acceptance_criteria': '`SELECT COUNT(*) FROM events;` returns at least 100000 rows spread '
                                    'across multiple user_id and event_type values.',
             'hint': 'Use a recursive CTE: `WITH RECURSIVE seq(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM seq '
                     'WHERE n<200000) INSERT INTO events(user_id,event_type,created_at,amount) SELECT '
                     "abs(random()%1000), CASE abs(random()%3) WHEN 0 THEN 'view' WHEN 1 THEN 'click' ELSE "
                     "'purchase' END, date('now',(-abs(random()%365))||' days'), abs(random()%10000)/100.0 "
                     'FROM seq;`',
             'order': 1},
            {'jira_key': 'IDX-2',
             'title': 'Measure the baseline with EXPLAIN QUERY PLAN',
             'description': 'Run a target query filtering by user_id and event_type, and inspect its plan. '
                            'With no indexes it should report a full SCAN. Turn on timing to capture the '
                            'baseline latency.',
             'acceptance_criteria': '`EXPLAIN QUERY PLAN SELECT * FROM events WHERE user_id=42 AND '
                                    "event_type='purchase';` reports SCAN events (a full table scan), and "
                                    '`.timer on` shows a measurable runtime.',
             'hint': 'Run `.timer on`, then `EXPLAIN QUERY PLAN SELECT * FROM events WHERE user_id=42 AND '
                     "event_type='purchase';`. A line containing `SCAN events` means no usable index.",
             'order': 2,
             'depends_on': 'IDX-1'},
            {'jira_key': 'IDX-3',
             'title': 'Add a single-column index and re-check the plan',
             'description': 'Create an index on user_id and re-run EXPLAIN QUERY PLAN. Observe that the '
                            'planner now uses SEARCH via the index for the user_id predicate but still '
                            'filters event_type in the row body.',
             'acceptance_criteria': 'After `CREATE INDEX idx_events_user ON events(user_id);`, the plan for '
                                    'the target query shows SEARCH events USING INDEX idx_events_user, and '
                                    'runtime drops noticeably.',
             'hint': '`CREATE INDEX idx_events_user ON events(user_id);` then re-run the EXPLAIN QUERY PLAN. '
                     'Look for `SEARCH` replacing `SCAN`.',
             'order': 3,
             'depends_on': 'IDX-2'},
            {'jira_key': 'IDX-4',
             'title': 'Build a composite index matching the WHERE clause',
             'description': 'Replace the single-column index with a composite index on (user_id, event_type) '
                            'so both equality predicates are satisfied by the index. Confirm the planner '
                            'prefers the composite index and that column order matters.',
             'acceptance_criteria': 'After creating idx_events_user_type on (user_id, event_type), EXPLAIN '
                                    'QUERY PLAN shows SEARCH using that composite index, and the query is '
                                    'faster than the single-column version.',
             'hint': '`CREATE INDEX idx_events_user_type ON events(user_id, event_type);`. Column order '
                     'matters: leading column must appear in the WHERE clause for the index to be used.',
             'order': 4,
             'depends_on': 'IDX-3'},
            {'jira_key': 'IDX-5',
             'title': 'Create a covering index to eliminate table lookups',
             'description': 'For a query that selects only amount for a given user_id and event_type, build '
                            'a covering index that includes amount so SQLite answers entirely from the index '
                            '(USING COVERING INDEX) without touching the table.',
             'acceptance_criteria': 'EXPLAIN QUERY PLAN for `SELECT amount FROM events WHERE user_id=42 AND '
                                    "event_type='purchase';` reports USING COVERING INDEX after the covering "
                                    'index is created.',
             'hint': '`CREATE INDEX idx_cover ON events(user_id, event_type, amount);`. When the SELECT list '
                     'and WHERE columns all live in the index, the plan says `USING COVERING INDEX`.',
             'order': 5,
             'depends_on': 'IDX-4'},
            {'jira_key': 'IDX-6',
             'title': 'Run ANALYZE and validate planner statistics',
             'description': 'Run ANALYZE to populate sqlite_stat1 with data distribution statistics, which '
                            'helps the planner choose between multiple candidate indexes on selective vs '
                            'non-selective predicates. Inspect the collected stats.',
             'acceptance_criteria': 'After `ANALYZE;`, `SELECT * FROM sqlite_stat1;` returns rows describing '
                                    'the events indexes, and the planner continues to choose the most '
                                    'selective index for the target query.',
             'hint': 'Run `ANALYZE;` then `SELECT tbl, idx, stat FROM sqlite_stat1;`. Compare EXPLAIN QUERY '
                     'PLAN choices before and after ANALYZE on a query that could use more than one index.',
             'order': 6,
             'depends_on': 'IDX-5'}]},
 {'technology_slug': 'sqlite',
  'title': 'Schema Migrations and Versioning with user_version',
  'slug': 'sqlite-migrations-versioning',
  'architecture_type': 'cicd',
  'description': 'Build a repeatable, forward-only migration system for a SQLite-backed app using PRAGMA '
                 'user_version as the schema version counter and idempotent migration scripts. You will '
                 'handle the tricky ALTER TABLE limitations of SQLite, including the 12-step table rebuild '
                 'required to change or drop columns safely.',
  'objectives': ['Use PRAGMA user_version to track and gate schema migrations',
                 'Write forward-only, idempotent migration scripts wrapped in transactions',
                 'Apply the safe 12-step table rebuild to alter columns SQLite cannot ALTER directly',
                 'Use ALTER TABLE ADD COLUMN and RENAME where supported',
                 'Verify schema integrity after each migration step'],
  'difficulty': 'intermediate',
  'estimated_hours': 5,
  'order': 4,
  'tasks': [{'jira_key': 'MIG-1',
             'title': 'Create the v1 baseline schema and set user_version',
             'description': 'Create an initial `customers` table (id INTEGER PRIMARY KEY, name TEXT NOT '
                            'NULL, email TEXT). Establish the migration convention: each successful '
                            'migration bumps PRAGMA user_version. Set the baseline to 1.',
             'acceptance_criteria': '`PRAGMA user_version;` returns 1 after the baseline migration, and the '
                                    'customers table exists with the expected columns.',
             'hint': 'Create the table inside a transaction, then run `PRAGMA user_version = 1;`. Read it '
                     'back with `PRAGMA user_version;` (note: reading takes no value, setting uses `= n`).',
             'order': 1},
            {'jira_key': 'MIG-2',
             'title': 'Write a version-gated migration runner pattern',
             'description': 'Establish a pattern where each migration checks the current user_version and '
                            'only applies if the DB is at the expected prior version. Document the guard so '
                            'migrations are idempotent and forward-only (re-running does nothing).',
             'acceptance_criteria': 'Running the v1 baseline migration a second time is a no-op (it detects '
                                    'user_version is already >= 1 and skips), and user_version stays at 1.',
             'hint': 'Read `PRAGMA user_version;` in your script/app; if it is already >= the target, skip. '
                     'In a shell wrapper: `v=$(sqlite3 app.db \'PRAGMA user_version;\'); [ "$v" -lt 2 ] && '
                     'sqlite3 app.db < 002_migration.sql`.',
             'order': 2,
             'depends_on': 'MIG-1'},
            {'jira_key': 'MIG-3',
             'title': 'Migration v2: add a column with ADD COLUMN',
             'description': 'Apply a migration that adds a `created_at TEXT DEFAULT CURRENT_TIMESTAMP` '
                            'column to customers using ALTER TABLE ADD COLUMN (which SQLite supports '
                            'directly), then bump user_version to 2 inside the same transaction.',
             'acceptance_criteria': 'After the migration, customers has a created_at column, existing rows '
                                    'have the default value, and `PRAGMA user_version;` returns 2.',
             'hint': '`BEGIN; ALTER TABLE customers ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP; '
                     'PRAGMA user_version = 2; COMMIT;`. Verify with `PRAGMA table_info(customers);`.',
             'order': 3,
             'depends_on': 'MIG-2'},
            {'jira_key': 'MIG-4',
             'title': 'Migration v3: rename a column',
             'description': 'Rename the `name` column to `full_name` using ALTER TABLE RENAME COLUMN '
                            '(supported in modern SQLite 3.25+). Bump user_version to 3. This demonstrates a '
                            'lightweight schema change that does not require a rebuild.',
             'acceptance_criteria': '`PRAGMA table_info(customers);` shows full_name instead of name, '
                                    'existing data is preserved, and user_version is 3.',
             'hint': '`BEGIN; ALTER TABLE customers RENAME COLUMN name TO full_name; PRAGMA user_version = '
                     '3; COMMIT;`. If your SQLite is older than 3.25, you must use the table-rebuild '
                     'approach instead.',
             'order': 4,
             'depends_on': 'MIG-3'},
            {'jira_key': 'MIG-5',
             'title': 'Migration v4: the 12-step rebuild to change a constraint',
             'description': "SQLite cannot drop a column's constraint or change its type in place on older "
                            'versions. Perform the safe rebuild: create a new table with the desired '
                            'definition (e.g., email TEXT NOT NULL UNIQUE), copy data, drop the old table, '
                            'and rename the new one, all inside one transaction with foreign_keys '
                            'temporarily off.',
             'acceptance_criteria': 'customers now enforces UNIQUE NOT NULL on email, all prior rows are '
                                    'preserved, `PRAGMA foreign_key_check;` returns no violations, and '
                                    'user_version is 4.',
             'hint': '`PRAGMA foreign_keys=OFF; BEGIN; CREATE TABLE customers_new(...desired schema...); '
                     'INSERT INTO customers_new SELECT ... FROM customers; DROP TABLE customers; ALTER TABLE '
                     'customers_new RENAME TO customers; PRAGMA foreign_key_check; PRAGMA user_version=4; '
                     'COMMIT; PRAGMA foreign_keys=ON;`',
             'order': 5,
             'depends_on': 'MIG-4'},
            {'jira_key': 'MIG-6',
             'title': 'Validate the migrated schema end to end',
             'description': 'Confirm the full migration chain produced the intended schema and that '
                            'integrity is intact. Run integrity and foreign-key checks, confirm the final '
                            'version, and prove the new UNIQUE constraint works by attempting a duplicate '
                            'email.',
             'acceptance_criteria': "`PRAGMA integrity_check;` returns 'ok', `PRAGMA user_version;` returns "
                                    '4, and inserting a duplicate email fails with a UNIQUE constraint '
                                    'error.',
             'hint': 'Run `PRAGMA integrity_check;`, `PRAGMA foreign_key_check;`, and test the constraint '
                     'with two inserts sharing the same email. The second should fail.',
             'order': 6,
             'depends_on': 'MIG-5'}]},
 {'technology_slug': 'sqlite',
  'title': 'Production-Grade SQLite: WAL, Backup, and Integrity for an Embedded App',
  'slug': 'sqlite-embedded-app-backup-wal',
  'architecture_type': '2tier',
  'description': "Harden a Python application's embedded SQLite database for production use, tuning it for "
                 'concurrent reads with WAL mode, implementing online backups that run while the app is '
                 'live, and building an automated integrity + recovery checklist. You will finish with a '
                 'small app plus operational scripts that back up safely and detect corruption.',
  'objectives': ['Enable and tune WAL mode for concurrent read/write access',
                 'Implement a hot online backup using the SQLite backup API and .backup',
                 'Run integrity_check and quick_check and interpret the results',
                 'Recover data from a corrupted database using .recover',
                 'Tune PRAGMAs (synchronous, cache_size, busy_timeout) for durability vs speed'],
  'difficulty': 'advanced',
  'estimated_hours': 7,
  'order': 5,
  'tasks': [{'jira_key': 'PROD-1',
             'title': 'Embed SQLite in a small Python app',
             'description': 'Write a small Python script using the built-in sqlite3 module that creates an '
                            'app.db, defines a `tasks` table, and exposes add/list functions. Set a '
                            'busy_timeout so the connection waits instead of failing immediately on a locked '
                            'database.',
             'acceptance_criteria': 'Running the script creates app.db, inserts rows, and lists them; the '
                                    'connection sets `PRAGMA busy_timeout=5000;` verified by reading it '
                                    'back.',
             'hint': "`import sqlite3; con=sqlite3.connect('app.db'); con.execute('PRAGMA "
                     "busy_timeout=5000'); con.execute('CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY "
                     "KEY, title TEXT, done INTEGER DEFAULT 0)');`. Commit and close cleanly.",
             'order': 1},
            {'jira_key': 'PROD-2',
             'title': 'Enable WAL mode and verify concurrency behavior',
             'description': 'Switch the database to Write-Ahead Logging mode so readers do not block the '
                            'writer. Confirm the mode persists and observe the -wal and -shm sidecar files '
                            'appear next to app.db during activity.',
             'acceptance_criteria': "`PRAGMA journal_mode;` returns 'wal', and after a write the app.db-wal "
                                    'and app.db-shm files exist on disk.',
             'hint': 'Run `PRAGMA journal_mode=WAL;` once (it persists in the database file). List the '
                     'directory after a write to see `app.db-wal` and `app.db-shm`. Use `PRAGMA '
                     'wal_checkpoint(TRUNCATE);` to flush.',
             'order': 2,
             'depends_on': 'PROD-1'},
            {'jira_key': 'PROD-3',
             'title': 'Tune durability and performance PRAGMAs',
             'description': 'Configure a sensible production PRAGMA set: synchronous=NORMAL (safe with WAL), '
                            'a larger cache_size, and foreign_keys=ON. Document the durability trade-off of '
                            'each setting versus the FULL/OFF alternatives.',
             'acceptance_criteria': 'Reading back `PRAGMA synchronous;` returns 1 (NORMAL), `PRAGMA '
                                    'foreign_keys;` returns 1, and cache_size reflects the configured value.',
             'hint': '`PRAGMA synchronous=NORMAL; PRAGMA cache_size=-20000; PRAGMA foreign_keys=ON;`. '
                     'Negative cache_size is in KiB. Note synchronous=NORMAL is durable across app crashes '
                     'in WAL, but a power loss can lose the last transaction.',
             'order': 3,
             'depends_on': 'PROD-2'},
            {'jira_key': 'PROD-4',
             'title': 'Take a hot online backup while the app is live',
             'description': 'Implement an online backup that copies a consistent snapshot without stopping '
                            'the app. Do it two ways: the sqlite3 CLI `.backup` command, and the Python '
                            'sqlite3 Connection.backup() API which uses the online backup API safely with '
                            'WAL.',
             'acceptance_criteria': '`sqlite3 app.db ".backup backup.db"` produces a valid backup.db, and a '
                                    'Python `src.backup(dst)` call produces an identical-row snapshot; both '
                                    'open cleanly and pass integrity_check.',
             'hint': 'CLI: `sqlite3 app.db ".backup \'backup.db\'"`. Python: '
                     "`dst=sqlite3.connect('backup.db'); con.backup(dst); dst.close()`. Never copy a "
                     'WAL-mode file with cp while writes are in flight; use the backup API.',
             'order': 4,
             'depends_on': 'PROD-3'},
            {'jira_key': 'PROD-5',
             'title': 'Run integrity checks and interpret results',
             'description': 'Add an operational health check that runs PRAGMA integrity_check and the faster '
                            "PRAGMA quick_check against app.db and the backup. Wire it so a non-'ok' result "
                            'is treated as an alarm.',
             'acceptance_criteria': "`PRAGMA integrity_check;` returns exactly 'ok' on a healthy database, "
                                    'and your script exits non-zero (or flags an error) if the result is '
                                    "anything other than 'ok'.",
             'hint': 'In shell: `res=$(sqlite3 app.db \'PRAGMA integrity_check;\'); [ "$res" = ok ] || echo '
                     'CORRUPT. quick_check is faster and skips index consistency; use integrity_check for '
                     'the thorough scan.',
             'order': 5,
             'depends_on': 'PROD-4'},
            {'jira_key': 'PROD-6',
             'title': 'Simulate corruption and recover with .recover',
             'description': 'Deliberately damage a throwaway copy of the database (e.g., overwrite bytes in '
                            'the file), confirm integrity_check now reports errors, then salvage the '
                            'readable data using the sqlite3 `.recover` command into a fresh database.',
             'acceptance_criteria': 'integrity_check on the damaged copy reports corruption, and `.recover` '
                                    "produces a new database that opens, passes integrity_check 'ok', and "
                                    'contains the recoverable tasks rows.',
             'hint': 'Copy app.db to broken.db, corrupt it (e.g. `dd if=/dev/urandom of=broken.db bs=1 '
                     'seek=100 count=200 conv=notrunc`), confirm with integrity_check, then `sqlite3 '
                     'broken.db .recover | sqlite3 recovered.db` and verify with integrity_check on '
                     'recovered.db.',
             'order': 6,
             'depends_on': 'PROD-5'}]},
 {'technology_slug': 'peoplesoft',
  'title': 'Stand Up Your First PeopleSoft Environment: Domains and Components',
  'slug': 'peoplesoft-environment-domain-bootstrap',
  'architecture_type': '3tier',
  'description': 'Bring a PeopleSoft environment online end to end by configuring and booting the three '
                 'server tiers: the Application Server domain (Tuxedo), the Process Scheduler domain, and '
                 'the PIA web server domain. You will edit psappsrv.cfg, connect to the database via the '
                 'Connect ID, and verify a clean sign-on through the browser.',
  'objectives': ['Explain the PeopleSoft 3-tier architecture (Web/PIA, App Server, Process Scheduler, '
                 'Database)',
                 'Create and configure an Application Server domain with psadmin and PSADMIN.CFG',
                 'Boot and validate the Tuxedo-based App Server and verify a working Connect ID / Access ID',
                 'Configure the PIA web server domain and sign on to the browser front end',
                 'Diagnose a failed boot using APPSRV.LOG and TUXLOG'],
  'difficulty': 'beginner',
  'estimated_hours': 4,
  'order': 1,
  'tasks': [{'jira_key': 'PSENV-1',
             'title': 'Verify database connectivity and the Connect ID',
             'description': 'Before any server tier can boot, the App Server must be able to log into the '
                            'database. Confirm the database is reachable and that the Connect ID (the '
                            'low-privilege bootstrap login, e.g. people/peop1e) and the Access ID (SYSADM) '
                            'are valid.',
             'acceptance_criteria': 'A test connection using the Connect ID succeeds, and querying PSDBOWNER '
                                    'returns the SYSADM owner ID. The database name, Access ID, and Connect '
                                    'ID are recorded for domain config.',
             'hint': 'For Oracle, use `sqlplus people/peop1e@ORCL` to prove the Connect ID works, then '
                     '`sqlplus SYSADM/<pw>@ORCL` and run `SELECT * FROM PSDBOWNER;`. The Connect ID only '
                     'needs SELECT on PSSTATUS, PSOPRDEFN, and PSACCESSPRFL.',
             'order': 1},
            {'jira_key': 'PSENV-2',
             'title': 'Create the Application Server domain with psadmin',
             'description': 'Launch the psadmin utility and create a new App Server domain (e.g. HRDMO). '
                            "Choose the 'small' template and let psadmin generate PSAPPSRV, PSSAMSRV, and "
                            'PSQCKSRV entries.',
             'acceptance_criteria': "psadmin lists the new domain under 'Administer a domain', and the "
                                    'domain directory contains a generated psappsrv.cfg and psappsrv.ubx.',
             'hint': 'Run `psadmin` -> Application Server -> Administer a domain -> Create a domain. Name it '
                     "HRDMO and pick the 'small' developer template so it starts fewer PSAPPSRV instances.",
             'order': 2,
             'depends_on': 'PSENV-1'},
            {'jira_key': 'PSENV-3',
             'title': 'Configure psappsrv.cfg with DB and Connect settings',
             'description': 'Edit the domain configuration so the App Server can reach the database. Set '
                            'DBName, DBType, UserId (a valid operator like PS), UserPswd, ConnectId, and '
                            'ConnectPswd, then run a configure pass to regenerate the Tuxedo binaries.',
             'acceptance_criteria': 'psappsrv.cfg contains the correct DBName/DBType and Connect ID; the '
                                    "'Load config as shown' + configure step completes without errors and "
                                    'rewrites the .ubb/.ubx files.',
             'hint': "In psadmin choose 'Configure this domain'. Set `DBName`, `DBType=ORACLE`, `UserId=PS`, "
                     '`ConnectId=people`. After editing, always let psadmin run the configure pass so '
                     'PSTUXCFG is regenerated.',
             'order': 3,
             'depends_on': 'PSENV-2'},
            {'jira_key': 'PSENV-4',
             'title': 'Boot the App Server domain and confirm the processes',
             'description': 'Start the HRDMO domain and confirm the Tuxedo processes (BBL, PSWATCHSRV, '
                            'PSAPPSRV, PSSAMSRV) come up cleanly. Use the psadmin server status view to '
                            'confirm queue counts.',
             'acceptance_criteria': "psadmin 'Domain status' shows BBL and at least one PSAPPSRV process "
                                    "RUNNING with no restart loop; APPSRV.LOG shows a successful 'Server "
                                    "started' message.",
             'hint': "Use psadmin -> 'Boot this domain' -> Boot (serial). Then 'Server status' should list "
                     'PSAPPSRV, PSSAMSRV, PSMONITORSRV. If a process cycles, open APPSRV.LOG in the LOGS '
                     'directory for the SQL error.',
             'order': 4,
             'depends_on': 'PSENV-3'},
            {'jira_key': 'PSENV-5',
             'title': 'Configure the PIA web domain and sign on',
             'description': 'Set up the PeopleSoft Internet Architecture (PIA) web server domain '
                            "(WebLogic/Tomcat), point it at the App Server's JSL listener host/port, deploy "
                            'the PIA, and sign on through the browser.',
             'acceptance_criteria': 'Browsing to http://<host>:<port>/ps/signon.html renders the sign-on '
                                    'page and logging in as PS reaches the PeopleSoft homepage with no '
                                    "'application server unavailable' error.",
             'hint': "Run the PIA install/setup, set the App Server 'machine name' to the JSL host and port "
                     "(default 9000) from psappsrv.cfg [JOLT Listener]. The web profile 'PROD' or 'DEV' "
                     'controls caching.',
             'order': 5,
             'depends_on': 'PSENV-4'},
            {'jira_key': 'PSENV-6',
             'title': 'Break-fix drill: diagnose a failed boot from the logs',
             'description': 'Intentionally set a wrong ConnectPswd, attempt a boot, observe the failure, '
                            'then read APPSRV.LOG and TUXLOG to identify the root cause and correct it. This '
                            'builds the log-reading muscle every PeopleSoft admin needs.',
             'acceptance_criteria': 'You can point to the specific APPSRV.LOG line indicating the Connect ID '
                                    'authentication failure, restore the correct password, reconfigure, and '
                                    'boot cleanly again.',
             'hint': "The tell-tale is a 'Could not sign on to database' or ORA-01017 in APPSRV.LOG; "
                     'Tuxedo-level boot ordering issues show in TUXLOG. Always reconfigure (regenerate '
                     'PSTUXCFG) after changing the .cfg, not just re-boot.',
             'order': 6,
             'depends_on': 'PSENV-5'}]},
 {'technology_slug': 'peoplesoft',
  'title': 'Security Foundations: Permission Lists, Roles, and User Profiles',
  'slug': 'peoplesoft-security-roles-permission-lists',
  'architecture_type': 'custom',
  'description': 'Build PeopleSoft application security from the ground up using the layered model: '
                 'Permission Lists grant page and process access, Roles bundle Permission Lists, and User '
                 "Profiles receive Roles. You will create a self-service employee's access, grant page-level "
                 'authorization, and prove access is denied when a Permission List is missing.',
  'objectives': ['Explain the Permission List -> Role -> User Profile security model',
                 'Create a Permission List that authorizes a specific menu, component, and pages',
                 'Bundle Permission Lists into a Role and assign the Role to a User Profile',
                 'Configure sign-on times and password controls on a Permission List',
                 'Verify authorized access and confirm denial when access is removed'],
  'difficulty': 'beginner',
  'estimated_hours': 3,
  'order': 2,
  'tasks': [{'jira_key': 'PSSEC-1',
             'title': 'Create a Permission List for employee self-service',
             'description': 'In PeopleTools > Security > Permissions & Roles > Permission Lists, create a '
                            'new Permission List (e.g. HCSPPGES) that will hold self-service page access. '
                            'Give it a description and a General tab with a default sign-on time.',
             'acceptance_criteria': 'A Permission List HCSPPGES exists and can be opened; the General page '
                                    'shows a valid sign-on time window (e.g. 00:00 to 23:59 for all days).',
             'hint': 'Navigate PeopleTools > Security > Permissions & Roles > Permission Lists > Add a New '
                     "Value. On the 'General' tab set 'Can Start Application Server' off (not needed for a "
                     'page-only list) and set the Time-out.',
             'order': 1},
            {'jira_key': 'PSSEC-2',
             'title': 'Authorize a menu, component, and pages',
             'description': "On the Permission List's Pages tab, add the menu (e.g. SELF_SERVICE), then open "
                            'the component permissions and grant access to the specific component and its '
                            'pages (View/Update actions). This is where page-level authorization actually '
                            'happens.',
             'acceptance_criteria': "The Pages tab lists the target menu; clicking 'Edit Components' shows "
                                    "the component with 'Authorized' pages and the correct "
                                    'Add/Update/Correction actions checked.',
             'hint': "On the Pages tab click the menu's 'Edit Components' link, then 'Edit Pages'. Check "
                     "'Authorized' for each page and select the display actions (Add, Update/Display). Save.",
             'order': 2,
             'depends_on': 'PSSEC-1'},
            {'jira_key': 'PSSEC-3',
             'title': 'Create a Role and attach the Permission List',
             'description': 'In Security > Permissions & Roles > Roles, create a Role (e.g. EE Self Service) '
                            'and add the HCSPPGES Permission List to it on the Permission Lists tab. Roles '
                            'are the reusable bundle that gets assigned to users.',
             'acceptance_criteria': "A Role 'EE Self Service' exists and its Permission Lists tab shows "
                                    "HCSPPGES; the Role's Members tab is initially empty.",
             'hint': 'PeopleTools > Security > Permissions & Roles > Roles > Add a New Value. On the '
                     "'Permission Lists' tab, add HCSPPGES. Save.",
             'order': 3,
             'depends_on': 'PSSEC-2'},
            {'jira_key': 'PSSEC-4',
             'title': 'Assign the Role to a User Profile',
             'description': 'Create or edit a test User Profile (e.g. TESTEE), set the Symbolic ID and a '
                            "valid Access Profile, then on the Roles tab add the 'EE Self Service' Role. "
                            'Confirm the User ID Alias / Permission List defaults resolve.',
             'acceptance_criteria': "User Profile TESTEE has the 'EE Self Service' Role on the Roles tab and "
                                    'a valid Primary/Process Profile Permission List assigned; the profile '
                                    "saves without a 'symbolic ID' error.",
             'hint': "PeopleTools > Security > User Profiles > User Profiles. On the 'General' tab pick the "
                     "Symbolic ID (maps to the Access ID). On the 'Roles' tab add EE Self Service. Set "
                     "'Process Profile' and 'Primary Permission List' on the General tab.",
             'order': 4,
             'depends_on': 'PSSEC-3'},
            {'jira_key': 'PSSEC-5',
             'title': 'Verify authorized access and confirm denial',
             'description': 'Sign on as TESTEE and confirm the self-service component is reachable. Then '
                            'remove HCSPPGES from the Role (or the page authorization), clear the '
                            'cache/re-login, and confirm the component is now denied.',
             'acceptance_criteria': 'As TESTEE the component opens when authorized; after removing the '
                                    "Permission List's page access the same navigation returns 'You are not "
                                    "authorized to access this component'.",
             'hint': 'Security changes can be cached — use PeopleTools > Security > Security Objects or sign '
                     'out/in. The denial message proves page-level authorization is enforced by the '
                     'Permission List, not the Role name.',
             'order': 5,
             'depends_on': 'PSSEC-4'}]},
 {'technology_slug': 'peoplesoft',
  'title': 'Run and Monitor a Batch Job with Process Scheduler',
  'slug': 'peoplesoft-process-scheduler-batch-job',
  'architecture_type': '3tier',
  'description': 'Configure the Process Scheduler server, define a Process Definition and a run control, '
                 'then submit, monitor, and troubleshoot a batch process through Process Monitor. You will '
                 "trace a job from 'Queued' to 'Success', post output to the Report Repository, and diagnose "
                 "a 'No Success' failure from the process logs.",
  'objectives': ['Configure and boot a Process Scheduler server domain (PSNT/PSUNX)',
                 'Understand Process Type, Process Definition, and run control relationships',
                 'Submit a job and follow its run status through Process Monitor',
                 'Configure output distribution to the Report Repository (Report Manager)',
                 'Diagnose a failed process using the process detail log and Message Log'],
  'difficulty': 'intermediate',
  'estimated_hours': 4,
  'order': 3,
  'tasks': [{'jira_key': 'PSJOB-1',
             'title': 'Configure and boot the Process Scheduler server',
             'description': 'Using psadmin, create/configure a Process Scheduler domain, set its ServerName '
                            '(e.g. PSUNX or PSNT), point it at the same database as the App Server, and '
                            'enable the Master Scheduler if this is the primary node.',
             'acceptance_criteria': 'psadmin shows the Process Scheduler domain booted with PSPRCSRV '
                                    'RUNNING; the Server List page (PeopleTools > Process Scheduler > '
                                    "Servers) shows the server status as 'Running'.",
             'hint': '`psadmin` -> Process Scheduler -> Create/Configure a domain. Set '
                     '`PrcsServerName=PSUNX`, DB settings, and Master Scheduler = Yes on one server. Boot '
                     'it, then confirm in the online Server List.',
             'order': 1},
            {'jira_key': 'PSJOB-2',
             'title': 'Review the Process Type and Process Definition',
             'description': 'Inspect an existing delivered Process Definition (e.g. the Application Engine '
                            "'PTPDBTST' or an SQR) under PeopleTools > Process Scheduler > Processes. Note "
                            'its Process Type, the server it can run on, and its Override Options / output '
                            'destination.',
             'acceptance_criteria': 'You can state the Process Name, its Process Type (e.g. Application '
                                    "Engine, SQR Report), and confirm on the 'Process Definition Options' "
                                    'tab which Component/Process Groups authorize it.',
             'hint': "PeopleTools > Process Scheduler > Processes. Open the process; the 'Process Definition "
                     "Options' tab lists the Process Groups — a run control can only launch it if the "
                     "operator's Process Profile includes one of those groups.",
             'order': 2},
            {'jira_key': 'PSJOB-3',
             'title': 'Grant process security via a Process Group',
             'description': "Ensure the operator can actually submit the job by adding the process's Process "
                            "Group to the operator's Process Profile Permission List (Process > Process "
                            'Group Permissions) and confirming the Process Profile allows the right server.',
             'acceptance_criteria': "The operator's Process Profile Permission List contains the Process "
                                    'Group used by the target Process Definition; the operator sees the '
                                    'process in the Process Scheduler Request lookup.',
             'hint': 'PeopleTools > Security > Permissions & Roles > Permission Lists > (Process Profile PL) '
                     "> 'Process' link > Process Group Permissions. Add the group (e.g. TLSALL). The Process "
                     "Profile PL is set on the User Profile's General tab.",
             'order': 3,
             'depends_on': 'PSJOB-2'},
            {'jira_key': 'PSJOB-4',
             'title': 'Create a run control and submit the job',
             'description': "Navigate to the process's run control page, add a run control ID, choose the "
                            'Process Scheduler server and output type/format on the Process Scheduler '
                            'Request page, and click OK to submit.',
             'acceptance_criteria': 'The submission returns a Process Instance number; Process Monitor lists '
                                    "the new instance with a Run Status starting at 'Queued'/'Initiated'.",
             'hint': "On the run control page click 'Run', pick Server Name = PSUNX, Type = Web, Format = "
                     'PDF/TXT, check the process, then OK. Note the Process Instance number shown.',
             'order': 4,
             'depends_on': 'PSJOB-3'},
            {'jira_key': 'PSJOB-5',
             'title': 'Monitor the run to Success and view output',
             'description': 'In Process Monitor, refresh and watch the Run Status transition Queued -> '
                            'Processing -> Success and Distribution Status go to Posted. Then open the '
                            'output in Report Manager / via the Details > View Log/Trace.',
             'acceptance_criteria': "The Process Instance reaches Run Status 'Success' and Distribution "
                                    "Status 'Posted'; the generated report/output is viewable from Details > "
                                    'View Log/Trace or the Report Manager Explorer.',
             'hint': 'PeopleTools > Process Scheduler > Process Monitor. Use the Refresh button (do not rely '
                     "on auto-refresh). 'Posted' means the file reached the Report Repository via the "
                     'distribution agent.',
             'order': 5,
             'depends_on': 'PSJOB-4'},
            {'jira_key': 'PSJOB-6',
             'title': "Break-fix drill: diagnose a 'No Success' or 'Error' run",
             'description': 'Submit a run that fails (e.g. a run control with a missing required parameter '
                            'or a stopped scheduler), then use Process Monitor > Details > View Log/Trace '
                            'and the Message Log to determine why it did not complete.',
             'acceptance_criteria': "You can identify from the log why the run status is 'No "
                                    "Success'/'Error' (e.g. scheduler down = stays Queued; SQL/parameter "
                                    'error appears in the trace), correct it, and rerun to Success.',
             'hint': "A job stuck in 'Queued' usually means the scheduler isn't running or the process can't "
                     "run on the chosen server. 'No Success' means it ran but errored — read Details > View "
                     'Log/Trace (.LOG file) and the Message Log for the actual message set/number.',
             'order': 6,
             'depends_on': 'PSJOB-5'}]},
 {'technology_slug': 'peoplesoft',
  'title': 'Build an Application Engine Program and an SQR Report',
  'slug': 'peoplesoft-app-engine-sqr-report',
  'architecture_type': 'custom',
  'description': 'Author reporting logic two ways: a set-based Application Engine program in App Designer '
                 'that stages and updates data using state records and Do actions, and a classic SQR report '
                 'that queries and formats output. You will register both as Process Definitions, run them '
                 'through Process Scheduler, and validate the results.',
  'objectives': ['Build an Application Engine program with sections, steps, and SQL/PeopleCode actions',
                 'Use a state record and %BIND/%SELECT to pass values between steps',
                 'Write an SQR report that queries the database and formats printed output',
                 'Register both programs as Process Definitions and run them via Process Scheduler',
                 'Validate output correctness and read the AE trace (AET) for debugging'],
  'difficulty': 'intermediate',
  'estimated_hours': 6,
  'order': 4,
  'tasks': [{'jira_key': 'PSDEV-1',
             'title': 'Create the Application Engine program and state record',
             'description': 'In Application Designer, create a new App Engine program (e.g. XX_EMPL_LOAD) '
                            "and a derived/work state record (e.g. XX_AET) with the fields you'll pass "
                            'between steps (e.g. EMPLID, PROCESS_INSTANCE). Save both into a project.',
             'acceptance_criteria': 'The AE program XX_EMPL_LOAD opens in App Designer with a MAIN section; '
                                    "the state record XX_AET is added to the program's State Records and "
                                    'includes PROCESS_INSTANCE.',
             'hint': "File > New > App Engine Program. Add the state record via 'Insert > State Record...'. "
                     'Every AE state record must include PROCESS_INSTANCE so the run is tied to the Process '
                     'Instance.',
             'order': 1},
            {'jira_key': 'PSDEV-2',
             'title': 'Add a section, steps, and a set-based SQL action',
             'description': 'In the MAIN section add a Step with a SQL action that performs a set-based '
                            'INSERT/UPDATE (e.g. populate a staging table from PS_JOB), using %BIND(field) '
                            'to reference state fields. Add a second step with a PeopleCode action for '
                            'control logic.',
             'acceptance_criteria': 'The MAIN section has ordered steps; the SQL action uses at least one '
                                    '%BIND(XX_AET.field) and a Do When/Do Select is used to drive iteration '
                                    'or guard a step.',
             'hint': 'Set-based is preferred over row-by-row: write one `INSERT ... SELECT ...` in the SQL '
                     'action rather than looping. Reference state fields with `%BIND(EMPLID)` and read a '
                     'value into state with `%SELECT(field) SELECT ...`.',
             'order': 2,
             'depends_on': 'PSDEV-1'},
            {'jira_key': 'PSDEV-3',
             'title': 'Register the AE program as a Process Definition and run it',
             'description': "Create a Process Type 'Application Engine' Process Definition for XX_EMPL_LOAD, "
                            'assign it to a Process Group, build a run control, and submit it through '
                            'Process Scheduler.',
             'acceptance_criteria': "XX_EMPL_LOAD runs to Run Status 'Success' in Process Monitor and the "
                                    'target/staging table contains the expected rows.',
             'hint': "PeopleTools > Process Scheduler > Processes > Add, Process Type = 'Application "
                     "Engine', Process Name = XX_EMPL_LOAD. You can also test from App Designer with the "
                     "'Run Program' toolbar for quick iteration before scheduling.",
             'order': 3,
             'depends_on': 'PSDEV-2'},
            {'jira_key': 'PSDEV-4',
             'title': 'Write the SQR report',
             'description': 'Create an SQR (.sqr) that opens a heading, runs a SELECT against your table, '
                            'and prints formatted rows. Use begin-setup for page size, begin-heading for '
                            'column titles, and a begin-select with printed columns and totals.',
             'acceptance_criteria': 'Running the SQR from the command line (sqrw/sqr) against the database '
                                    'produces an output file (.lis/.pdf) with a heading and correctly '
                                    'formatted data rows.',
             'hint': 'Structure: `begin-program` -> `do Setup` -> `do Heading` -> `do Main`. Inside '
                     '`begin-select ... end-select` print columns with position `(row,col)`. Use `#include '
                     "'setenv.sqc'` and standard SQCs for headers.",
             'order': 4},
            {'jira_key': 'PSDEV-5',
             'title': 'Register the SQR as a Process Definition and run it',
             'description': "Place the .sqr in the SQR source path, create a Process Type 'SQR Report' "
                            'Process Definition, wire its Process Group and output format, then submit it '
                            'via Process Scheduler and view the report in Report Manager.',
             'acceptance_criteria': "The SQR Process Definition runs to 'Success', Distribution Status "
                                    "'Posted', and the report opens from Report Manager with the expected "
                                    'content.',
             'hint': "The .sqr must live in a directory on the Process Scheduler's SQR search path "
                     "(SQRBIN/PS_HOME/sqr or a custom PS_APP_HOME sqr dir). Process Type = 'SQR Report', "
                     'Type = Web, Format = PDF.',
             'order': 5,
             'depends_on': 'PSDEV-4'},
            {'jira_key': 'PSDEV-6',
             'title': 'Debug with the AE trace and validate results',
             'description': 'Re-run the AE program with tracing enabled (TraceAE) to capture the .AET file, '
                            "then read it to confirm each step's SQL, bind values, and row counts. "
                            'Cross-check the AE staging output against the SQR report for consistency.',
             'acceptance_criteria': 'An .AET trace is produced showing the compiled SQL and %BIND '
                                    'substitutions per step; the row counts in the trace match what the SQR '
                                    'report prints.',
             'hint': 'Add `-TRACE 7 -TOOLSTRACESQL 31` (or set TraceAE=1099 in the Process Scheduler config '
                     '/ run control) to capture the AET. The AET shows the actual SQL after %BIND resolution '
                     '— the fastest way to catch a bad bind or empty result set.',
             'order': 6,
             'depends_on': 'PSDEV-5'}]},
 {'technology_slug': 'peoplesoft',
  'title': 'Integration Broker: Publish and Consume a Real-Time Service',
  'slug': 'peoplesoft-integration-broker-service-setup',
  'architecture_type': 'microservices',
  'description': 'Configure PeopleSoft Integration Broker (IB) end to end and expose a synchronous '
                 'REST/service operation, then invoke it and trace the message. You will activate the '
                 'gateway and domain, define nodes, build a service and service operation with routings and '
                 'handlers, and troubleshoot delivery using the Service Operations Monitor.',
  'objectives': ['Configure the Integration Gateway and activate the messaging domain (Pub/Sub)',
                 'Define local and remote Nodes and set the default local node',
                 'Create a Service, Service Operation, message, and handler',
                 'Configure inbound/outbound routings and provide the service as REST/SOAP',
                 'Invoke the operation and trace/troubleshoot it in the Service Operations Monitor'],
  'difficulty': 'advanced',
  'estimated_hours': 8,
  'order': 5,
  'tasks': [{'jira_key': 'PSIB-1',
             'title': 'Configure the Integration Gateway and load connectors',
             'description': 'In PeopleTools > Integration Broker > Configuration > Gateways, set the '
                            'Integration Gateway URL (PSIGW servlet), load the gateway connectors, and enter '
                            'the App Server connection info (host, JOLT port, App Server domain password) so '
                            'the gateway can reach this node.',
             'acceptance_criteria': "'Ping Gateway' returns ACTIVE and 'Load Gateway Connectors' lists "
                                    'connectors (HttpTargetConnector, PSFT81TargetConnector, etc.); the '
                                    "gateway's default app server node is configured and passes the "
                                    'connection test.',
             'hint': 'Gateway URL is typically `http://<web>:<port>/PSIGW/PeopleSoftListeningConnector`. '
                     "Click 'Load Gateway Connectors', then 'Gateway Setup Properties' "
                     '(integrationGateway.properties) to set the app server URL and domain password.',
             'order': 1},
            {'jira_key': 'PSIB-2',
             'title': 'Activate the messaging domain (Pub/Sub servers)',
             'description': 'Ensure the App Server domain has Pub/Sub servers enabled (PSBRKDSP/PSBRKHND, '
                            'PSPUBDSP/PSPUBHND, PSSUBDSP/PSSUBHND), then in Integration Broker > Service '
                            'Operations Monitor > Administration > Domain Status, activate the domain.',
             'acceptance_criteria': "Domain Status shows the domain 'Active'; the dispatcher/handler "
                                    'processes are listed and the queues are not paused.',
             'hint': "In psadmin, the domain must be configured with 'Pub/Sub servers = Yes' (regen PSTUXCFG "
                     'and reboot). Then Domain Status page > set Domain to Active and Update. Grace period + '
                     'purge settings live here too.',
             'order': 2,
             'depends_on': 'PSIB-1'},
            {'jira_key': 'PSIB-3',
             'title': 'Define nodes and set the default local node',
             'description': 'Under Integration Broker > Integration Setup > Nodes, confirm the default local '
                            'node (Node Type = PIA, Default Local Node = Yes, Local Node = Yes) has an '
                            'active single sign-on / authentication option set, and create a remote node for '
                            'the external partner if consuming.',
             'acceptance_criteria': "Exactly one node is marked 'Default Local Node = Yes'; its Connectors "
                                    'tab and authentication (e.g. Password / node password) are set; any '
                                    'remote node has a valid gateway/connector and portal URI.',
             'hint': "There must be one and only one Default Local Node. On the node's Connectors tab set "
                     "the Gateway ID (LOCAL) and connector (PSFTTARGET). Set 'Authentication Option' "
                     'consistently on both ends (None/Password/Cert).',
             'order': 3,
             'depends_on': 'PSIB-2'},
            {'jira_key': 'PSIB-4',
             'title': 'Create the Service, Service Operation, message, and handler',
             'description': 'Create a Service (e.g. XX_GET_EMPLOYEE), add a synchronous Service Operation '
                            'with a request and response Message (rowset-based or nonrowset), set it Active, '
                            'and attach an OnRequest handler (Application Class or PeopleCode) that returns '
                            'the response.',
             'acceptance_criteria': 'The Service Operation is Active, has request/response messages '
                                    "assigned, and a handler of type 'OnRequest' implementing the response; "
                                    "the operation's default routing shows the local node.",
             'hint': "Integration Broker > Integration Setup > Services > add Service, then 'Add Service "
                     "Operation'. Operation Type = Synchronous. On the Handlers tab add an OnRequest "
                     "Application Class implementing the IRequestHandler interface's OnRequest method.",
             'order': 4,
             'depends_on': 'PSIB-3'},
            {'jira_key': 'PSIB-5',
             'title': 'Configure routings and provide the operation as REST/SOAP',
             'description': 'On the Routings tab, generate/activate the any-to-local routing for inbound '
                            "calls, then use 'Provide Web Service' to expose the operation as a WSDL/REST "
                            'endpoint. Confirm the endpoint URL and required permission list access.',
             'acceptance_criteria': 'An active routing exists (sender/receiver nodes correct, status Active) '
                                    "and the 'Provide Web Service' wizard publishes a WSDL/endpoint "
                                    'reachable at the PSIGW REST/SOAP URL.',
             'hint': "Routings must be Active or the message is 'not routed'. Use Integration Setup > "
                     "'Provide Web Service' to generate the WSDL. Grant the service operation's Permission "
                     'List (Web Service Access) so the caller is authorized.',
             'order': 5,
             'depends_on': 'PSIB-4'},
            {'jira_key': 'PSIB-6',
             'title': 'Invoke, trace, and troubleshoot in the Service Operations Monitor',
             'description': 'Call the endpoint (from Handler Tester, SoapUI/curl, or a consuming node), then '
                            'open Service Operations Monitor > Monitoring > Asynchronous/Synchronous '
                            'Services to inspect the transaction, view the request/response XML, and resolve '
                            "any 'Error' or 'Timeout' status.",
             'acceptance_criteria': 'The invocation returns the expected response payload; the Service '
                                    "Operations Monitor shows the transaction as 'Done'/'Received' (not "
                                    'Error), and you can open the request and response XML for that '
                                    'transaction.',
             'hint': 'Handler Tester (Integration Broker > Service Utilities) is the fastest local invoke. '
                     "In the Monitor, a 'New/Working->Error' chain usually means a routing or auth problem; "
                     'click the Details/Error link to see the exception. Check the gateway messageLog if it '
                     'never reaches the node.',
             'order': 6,
             'depends_on': 'PSIB-5'}]},
 {'technology_slug': 'wireshark',
  'title': 'First Capture: Read the Wire from Zero',
  'slug': 'wireshark-first-capture-from-zero',
  'architecture_type': 'custom',
  'description': 'You are a new NOC analyst who has never opened a packet analyzer. In this project you '
                 'install Wireshark, identify the right capture interface, record a live trace of everyday '
                 'web browsing, and learn to read the packet list, detail, and byte panes. By the end you '
                 'can capture, save, and reopen a trace with confidence.',
  'objectives': ['Identify the correct capture interface and start/stop a live capture',
                 'Read the three Wireshark panes (packet list, details tree, hex bytes)',
                 'Distinguish protocol layers (Ethernet, IP, TCP/UDP, application) in a single frame',
                 'Save a capture to .pcapng and reopen it for later analysis'],
  'difficulty': 'beginner',
  'estimated_hours': 2,
  'order': 1,
  'tasks': [{'jira_key': 'WSCAP-1',
             'title': 'Install Wireshark and verify the capture stack',
             'description': 'Install Wireshark (GUI) plus the tshark CLI. Confirm the packet capture library '
                            'is present and that your user can capture without root by joining the capture '
                            'group. On Linux verify with `dumpcap --version` and `tshark -D` to list '
                            'interfaces; on macOS/Windows confirm the Npcap/ChmodBPF helper is installed.',
             'acceptance_criteria': '`tshark -D` prints at least one numbered interface and `wireshark '
                                    "--version` (or Help > About) reports a version with 'with libpcap' / "
                                    'Npcap listed.',
             'hint': 'Linux: `sudo apt install wireshark tshark` then `sudo usermod -aG wireshark $USER` and '
                     're-login. Verify with `tshark -D`. macOS: `brew install --cask wireshark` installs the '
                     'ChmodBPF helper.',
             'order': 1},
            {'jira_key': 'WSCAP-2',
             'title': 'Pick the right interface and start a live capture',
             'description': 'Interfaces with a moving sparkline in the welcome screen are carrying traffic. '
                            'Select the active interface (e.g. eth0/en0/Wi-Fi), start a capture, generate a '
                            'little traffic by loading a plain HTTP or HTTPS page, then stop the capture '
                            'after ~20 seconds.',
             'acceptance_criteria': 'A live capture produces at least a few hundred packets and stops '
                                    'cleanly, showing a non-empty packet list.',
             'hint': 'Double-click the interface with the busiest sparkline, or from CLI: `tshark -i en0 -a '
                     'duration:20 -w /tmp/first.pcapng`. Trigger traffic with `curl http://example.com` in '
                     'another terminal.',
             'order': 2,
             'depends_on': 'WSCAP-1'},
            {'jira_key': 'WSCAP-3',
             'title': 'Read the three panes on a single frame',
             'description': 'Click one TCP packet and expand the detail tree. Walk down the encapsulation: '
                            'Frame > Ethernet II (MAC addresses) > Internet Protocol (src/dst IP, TTL) > '
                            'Transmission Control Protocol (ports, flags, seq/ack). Watch the byte pane '
                            'highlight the same field you click in the tree.',
             'acceptance_criteria': 'You can point to the source IP, destination port, and TCP flags for a '
                                    'chosen packet and see the corresponding bytes highlighted in the hex '
                                    'pane.',
             'hint': 'Click a packet, then in the details pane expand each protocol layer with the arrow. '
                     "Right-click any field > 'Apply as Column' to surface it in the packet list.",
             'order': 3,
             'depends_on': 'WSCAP-2'},
            {'jira_key': 'WSCAP-4',
             'title': 'Add useful columns and read the Info column',
             'description': 'The default Info column already summarizes each packet (e.g. `SYN`, `GET /`, '
                            '`Standard query A example.com`). Add a custom column for TCP stream index and '
                            'one for delta time, so you can start correlating conversations and timing at a '
                            'glance.',
             'acceptance_criteria': 'The packet list shows added columns for `tcp.stream` and frame delta '
                                    'time, and you can describe what the Info column says for a SYN packet '
                                    'and a DNS query.',
             'hint': 'Preferences > Appearance > Columns, add Custom fields `tcp.stream` and '
                     '`frame.time_delta_displayed`. Or right-click a field in the detail tree and choose '
                     "'Apply as Column'.",
             'order': 4,
             'depends_on': 'WSCAP-3'},
            {'jira_key': 'WSCAP-5',
             'title': 'Save, close, and reopen the capture',
             'description': 'Save the trace as .pcapng (the native format that preserves interface metadata '
                            'and comments). Close the file, reopen it, and add a capture comment describing '
                            'what you did. Confirm the packet count and timestamps survived the round trip.',
             'acceptance_criteria': 'The saved .pcapng reopens with identical packet count and timestamps, '
                                    'and a capture comment is visible under Statistics > Capture File '
                                    'Properties.',
             'hint': 'File > Save As > pcapng. Add a note via Statistics > Capture File Properties > '
                     "'Capture comments'. From CLI verify with `capinfos /tmp/first.pcapng`.",
             'order': 5,
             'depends_on': 'WSCAP-2'}]},
 {'technology_slug': 'wireshark',
  'title': 'Master Capture and Display Filters',
  'slug': 'wireshark-capture-and-display-filters',
  'architecture_type': 'custom',
  'description': 'Filtering is the single most important Wireshark skill. In this project you learn the two '
                 'very different filter languages: BPF capture filters that discard traffic before it is '
                 'written, and Wireshark display filters that hide packets from an existing trace. You '
                 'practice building precise expressions to isolate a single conversation, protocol, or error '
                 'condition.',
  'objectives': ['Explain the difference between capture (BPF) and display filters and when to use each',
                 'Write BPF capture filters to scope a capture by host, port, and protocol',
                 'Write display filters using comparison, logical, and membership operators',
                 "Use right-click 'Apply as Filter' and 'Follow Stream' to build filters quickly",
                 'Save and reuse filter buttons and filter macros'],
  'difficulty': 'beginner',
  'estimated_hours': 3,
  'order': 2,
  'tasks': [{'jira_key': 'WSFLT-1',
             'title': 'Scope a capture with a BPF capture filter',
             'description': 'Capture filters run in libpcap/Npcap and permanently drop non-matching traffic, '
                            'keeping trace files small. Capture only DNS and web traffic to a specific host '
                            'using BPF syntax, and note that the grammar (`host`, `port`, `tcp`, `and`/`or`) '
                            'is NOT the same as display filters.',
             'acceptance_criteria': 'The resulting trace contains only packets to/from the target host on '
                                    'ports 53, 80, and 443, and no unrelated background traffic.',
             'hint': "Capture > Options > 'Capture filter' field: `host 93.184.216.34 and (port 53 or port "
                     '80 or port 443)`. CLI: `tshark -i en0 -f "host example.com and port 443" -w '
                     '/tmp/scoped.pcapng`.',
             'order': 1},
            {'jira_key': 'WSFLT-2',
             'title': 'Write your first display filters',
             'description': "Display filters operate on an existing trace and use Wireshark's own protocol "
                            'field names. Filter the trace down to only DNS, then only TCP SYN packets, then '
                            'a single IP conversation. Learn that the filter bar turns green for valid '
                            'syntax and red for invalid.',
             'acceptance_criteria': 'You can produce three working filters: one showing only DNS, one '
                                    'showing only TCP SYN packets, and one showing a single '
                                    'source/destination IP pair.',
             'hint': 'Try `dns`, then `tcp.flags.syn == 1 && tcp.flags.ack == 0`, then `ip.addr == 10.0.0.5 '
                     '&& ip.addr == 93.184.216.34`. Note `ip.addr ==` matches either direction.',
             'order': 2,
             'depends_on': 'WSFLT-1'},
            {'jira_key': 'WSFLT-3',
             'title': 'Use operators, membership, and slices',
             'description': 'Go beyond equality. Use comparison operators, the `in {}` membership set, '
                            'contains/matches for payload search, and byte slicing. Build a filter that '
                            'finds HTTP requests to any of several hosts, and one that finds TCP packets '
                            'with a non-empty payload.',
             'acceptance_criteria': 'A filter using `in {}` correctly matches multiple ports/hosts, and a '
                                    '`matches` or `contains` filter locates packets whose payload holds a '
                                    'target string.',
             'hint': 'Examples: `tcp.port in {80 443 8080}`, `http.host contains "example"`, `frame contains '
                     '"password"`, `tcp.len > 0`. Use `!(arp or icmp)` to exclude noise.',
             'order': 3,
             'depends_on': 'WSFLT-2'},
            {'jira_key': 'WSFLT-4',
             'title': 'Build filters by right-clicking and following streams',
             'description': 'The fastest way to build a filter is to let Wireshark write it. Right-click a '
                            "field and choose 'Apply as Filter > Selected', then use 'Follow > TCP Stream' "
                            'to isolate an entire conversation and auto-generate its `tcp.stream eq N` '
                            'filter.',
             'acceptance_criteria': 'You isolate one full TCP conversation via Follow TCP Stream and confirm '
                                    'the display filter bar was auto-populated with a `tcp.stream eq` '
                                    'expression.',
             'hint': 'Right-click a packet > Follow > TCP Stream. The reassembled conversation opens and the '
                     "filter becomes `tcp.stream eq 7`. Right-click any field > 'Prepare as Filter' to "
                     'compose without applying.',
             'order': 4,
             'depends_on': 'WSFLT-2'},
            {'jira_key': 'WSFLT-5',
             'title': 'Save reusable filter buttons and color rules',
             'description': 'Operationalize your filters. Create filter buttons for the expressions you use '
                            "daily (e.g. 'TCP resets', 'DNS errors') and add a coloring rule so problem "
                            'packets stand out in any future capture.',
             'acceptance_criteria': 'At least two filter buttons appear in the toolbar and a custom coloring '
                                    'rule visibly highlights matching packets (e.g. TCP RST) in the packet '
                                    'list.',
             'hint': "Click the '+' at the right of the display filter bar to save a button for "
                     "`tcp.flags.reset == 1`. Add color via View > Coloring Rules > '+' with filter "
                     '`dns.flags.rcode != 0` in red.',
             'order': 5,
             'depends_on': 'WSFLT-3'}]},
 {'technology_slug': 'wireshark',
  'title': 'Dissect the TCP Handshake and Retransmissions',
  'slug': 'wireshark-tcp-handshake-and-retransmissions',
  'architecture_type': 'custom',
  'description': 'TCP problems hide in the sequence numbers. This project teaches you to read the three-way '
                 'handshake, verify window scaling and MSS negotiation, and recognize the difference between '
                 'retransmissions, duplicate ACKs, and out-of-order packets. You use the expert system and '
                 'I/O graphs to quantify packet loss and its impact.',
  'objectives': ['Identify the SYN, SYN/ACK, ACK handshake and the negotiated MSS and window scale',
                 'Interpret relative vs absolute sequence and acknowledgment numbers',
                 'Distinguish retransmissions, fast retransmissions, duplicate ACKs, and out-of-order frames',
                 'Use the Expert Information panel to triage TCP anomalies',
                 'Quantify loss and throughput impact with I/O and TCP stream graphs'],
  'difficulty': 'intermediate',
  'estimated_hours': 4,
  'order': 3,
  'tasks': [{'jira_key': 'WSTCP-1',
             'title': 'Trace and verify a clean three-way handshake',
             'description': 'Capture a fresh TCP connection and isolate its handshake. Confirm SYN then '
                            'SYN/ACK then ACK, and read the options each side advertises: Maximum Segment '
                            'Size, Window Scale, SACK-permitted, and timestamps. These options are only '
                            'exchanged in the SYN/SYN-ACK.',
             'acceptance_criteria': 'You point to all three handshake packets in one stream and state the '
                                    'negotiated MSS and the window scale multiplier for each direction.',
             'hint': 'Filter `tcp.flags.syn == 1`, then Follow > TCP Stream to lock onto one connection. '
                     "Expand TCP > Options in the SYN to read MSS and 'Window scale: N (multiply by ...)'.",
             'order': 1},
            {'jira_key': 'WSTCP-2',
             'title': 'Read relative vs absolute sequence numbers',
             'description': 'By default Wireshark shows relative sequence numbers (SYN = 0) for readability. '
                            'Turn relative sequence numbers off to see the real initial sequence number '
                            '(ISN), then back on. Understand how SEQ and ACK advance by payload length so '
                            'you can spot gaps.',
             'acceptance_criteria': 'You can toggle relative sequence numbers and correctly state both the '
                                    'relative and absolute ISN for a connection, and explain why ACK = last '
                                    'SEQ + bytes received.',
             'hint': "Preferences > Protocols > TCP > uncheck 'Relative sequence numbers' to reveal the ISN. "
                     'Watch how a 1448-byte segment bumps the next SEQ by 1448.',
             'order': 2,
             'depends_on': 'WSTCP-1'},
            {'jira_key': 'WSTCP-3',
             'title': 'Classify retransmissions vs duplicate ACKs vs out-of-order',
             'description': 'Load a lossy capture. Use TCP analysis flags to tell apart a Retransmission '
                            '(data resent after RTO), a Fast Retransmission (resent after 3 dup ACKs), '
                            'Duplicate ACKs (receiver asking for the missing segment), and Out-Of-Order '
                            '(arrived late, not actually lost). Misreading these leads to wrong conclusions.',
             'acceptance_criteria': 'You produce filtered views for retransmissions, duplicate ACKs, and '
                                    'out-of-order packets and correctly explain what each indicates about '
                                    'the path.',
             'hint': 'Filters: `tcp.analysis.retransmission`, `tcp.analysis.fast_retransmission`, '
                     '`tcp.analysis.duplicate_ack`, `tcp.analysis.out_of_order`. These are '
                     'Wireshark-computed, under TCP > [SEQ/ACK analysis].',
             'order': 3,
             'depends_on': 'WSTCP-2'},
            {'jira_key': 'WSTCP-4',
             'title': 'Triage anomalies with Expert Information',
             'description': 'Open Analyze > Expert Information to get a severity-grouped summary (Errors, '
                            'Warnings, Notes, Chats) of every anomaly Wireshark detected: zero windows, '
                            'resets, retransmissions, and more. Use it as a fast triage dashboard before '
                            'diving into individual packets.',
             'acceptance_criteria': 'You open the Expert panel, identify the highest-severity finding, and '
                                    'jump to the offending packet by clicking the entry.',
             'hint': "Analyze > Expert Information. Watch for 'TCP Zero Window' (receiver buffer full) and "
                     "'Connection reset (RST)'. Click a group to expand, click a packet to navigate.",
             'order': 4,
             'depends_on': 'WSTCP-3'},
            {'jira_key': 'WSTCP-5',
             'title': 'Quantify impact with I/O and TCP stream graphs',
             'description': 'Numbers beat impressions. Use Statistics > I/O Graph to plot retransmissions '
                            'over time against total throughput, and Statistics > TCP Stream Graphs > '
                            'Time/Sequence (Stevens) to see the sawtooth of loss and recovery for one '
                            'connection.',
             'acceptance_criteria': 'An I/O graph shows a retransmission spike correlated with a throughput '
                                    'dip, and a Time/Sequence graph visibly shows stalled/recovered segments '
                                    'for the chosen stream.',
             'hint': 'Statistics > I/O Graph: add a line with filter `tcp.analysis.retransmission`. For one '
                     'stream, select a packet then Statistics > TCP Stream Graphs > Time Sequence (Stevens).',
             'order': 5,
             'depends_on': 'WSTCP-4'},
            {'jira_key': 'WSTCP-6',
             'title': 'Diagnose a stalled transfer end to end',
             'description': 'Put it together on a slow file transfer capture. Decide whether the bottleneck '
                            'is loss (retransmissions), a full receive buffer (zero window), or an '
                            'application that simply stopped sending. Write a one-paragraph root cause tied '
                            'to specific packet numbers.',
             'acceptance_criteria': 'A written root cause names the mechanism (loss / zero window / app '
                                    'stall), cites the packet numbers that prove it, and states which '
                                    'endpoint is responsible.',
             'hint': 'Check `tcp.analysis.zero_window` and `tcp.analysis.window_update` for buffer stalls; '
                     "correlate the last data packet's time with the next to spot an app-side pause via "
                     '`tcp.time_delta`.',
             'order': 6,
             'depends_on': 'WSTCP-5'}]},
 {'technology_slug': 'wireshark',
  'title': 'Diagnose a Slow App: DNS, TCP, and TLS Latency',
  'slug': 'wireshark-diagnose-slow-app-dns-tls',
  'architecture_type': '3tier',
  'description': "A user reports 'the app is slow' with no other detail. Working only from a capture of the "
                 'page load, you decompose the wall-clock latency into its parts: DNS resolution, TCP '
                 'connect, TLS handshake, and server think-time. You pinpoint which layer owns the delay and '
                 'produce evidence, mirroring how a real support escalation is resolved.',
  'objectives': ['Decompose page-load latency into DNS, TCP connect, TLS, and server response time',
                 'Measure DNS query-to-response time and spot retries or NXDOMAIN',
                 'Measure the TLS handshake duration and identify the negotiated version and SNI',
                 'Isolate server think-time using time-since-request and time deltas',
                 'Attribute the dominant delay to a specific layer with packet-level evidence'],
  'difficulty': 'intermediate',
  'estimated_hours': 5,
  'order': 4,
  'tasks': [{'jira_key': 'WSSLOW-1',
             'title': 'Establish the timeline of one page load',
             'description': 'Isolate the connection(s) behind a single slow request. Add columns for delta '
                            'time and time-since-previous-frame, and use the packet timestamps to bracket '
                            'the total user-perceived latency from first DNS query to last content byte.',
             'acceptance_criteria': 'You state the total wall-clock time for the request and identify the '
                                    'first (DNS query) and last (final data) packets that bound it.',
             'hint': "Set Time Display Format > 'Seconds Since Beginning of Capture' (View menu). Add column "
                     '`frame.time_delta_displayed`. Note the timestamp of the initial `dns` query and the '
                     'final response segment.',
             'order': 1},
            {'jira_key': 'WSSLOW-2',
             'title': 'Measure DNS resolution time',
             'description': "Match each DNS query to its response and read Wireshark's computed response "
                            'time. Look for slow resolvers, retried queries (same transaction ID re-sent), '
                            'SERVFAIL/NXDOMAIN rcodes, or CNAME chains that add round trips.',
             'acceptance_criteria': 'You report the DNS resolution time in milliseconds for the target name '
                                    'and flag any retries or non-zero rcode.',
             'hint': "Filter `dns`. Expand the response > 'Time' field (dns.time) which Wireshark computes "
                     'as response minus query. Check `dns.flags.rcode != 0` for errors and duplicate '
                     '`dns.id` for retries.',
             'order': 2,
             'depends_on': 'WSSLOW-1'},
            {'jira_key': 'WSSLOW-3',
             'title': 'Measure TCP connect (SYN to ACK) time',
             'description': 'The TCP handshake round trip is a clean proxy for network RTT to the server. '
                            "Measure the time from the client SYN to the client's completing ACK, and "
                            'compare it across connections to rule in or out a slow or distant path.',
             'acceptance_criteria': 'You report the SYN-to-ACK handshake time and state whether network RTT '
                                    'is a plausible contributor to the slowness.',
             'hint': 'Follow the stream, note the SYN timestamp and the final ACK timestamp. Or add column '
                     '`tcp.time_relative` and read the value on the SYN/ACK. High values here point at the '
                     'network, not the app.',
             'order': 3,
             'depends_on': 'WSSLOW-1'},
            {'jira_key': 'WSSLOW-4',
             'title': 'Measure the TLS handshake and read ClientHello/ServerHello',
             'description': 'For HTTPS, TLS setup adds one to two round trips before any app data flows. '
                            'Measure from ClientHello to the point encrypted application data begins. Read '
                            'the SNI (server name) in ClientHello and the negotiated version/cipher in '
                            "ServerHello to confirm you're looking at the right service.",
             'acceptance_criteria': 'You report the TLS handshake duration, the SNI from ClientHello, and '
                                    'the negotiated TLS version, and note whether it was a full or resumed '
                                    'handshake.',
             'hint': 'Filter `tls.handshake`. ClientHello carries `tls.handshake.extensions_server_name` '
                     '(SNI). Time from ClientHello to first `tls.record` app-data. TLS 1.3 is 1-RTT; a '
                     'session ticket resume is faster.',
             'order': 4,
             'depends_on': 'WSSLOW-3'},
            {'jira_key': 'WSSLOW-5',
             'title': 'Isolate server think-time',
             'description': 'After the request leaves the client, the gap before the first response byte is '
                            "server processing time (plus one RTT). Use HTTP's time-since-request or the "
                            'delta between the last request packet and the first response packet to size the '
                            "server's contribution.",
             'acceptance_criteria': 'You report server think-time in milliseconds and separate it cleanly '
                                    'from network RTT already measured in the handshake step.',
             'hint': 'For cleartext HTTP: expand HTTP > `http.time` (time since request). For HTTPS: measure '
                     "delta between the request's last app-data packet and the first server app-data packet; "
                     'subtract the RTT you measured from the handshake.',
             'order': 5,
             'depends_on': 'WSSLOW-4'},
            {'jira_key': 'WSSLOW-6',
             'title': 'Attribute the dominant delay and write the finding',
             'description': 'Combine the four measurements (DNS + TCP connect + TLS + server think-time) '
                            'into a latency budget. Determine which layer dominates and write a crisp '
                            'finding a non-analyst could act on, citing the packet numbers and millisecond '
                            'values that prove it.',
             'acceptance_criteria': 'A latency breakdown sums to roughly the total wall-clock time, names '
                                    'the dominant layer, and cites specific packets/times as evidence.',
             'hint': 'Make a small table: DNS X ms, TCP Y ms, TLS Z ms, server W ms, total ~= sum. If server '
                     "think-time dwarfs the rest, the network is fine and it's an app/backend issue.",
             'order': 6,
             'depends_on': 'WSSLOW-5'}]},
 {'technology_slug': 'wireshark',
  'title': 'Forensic Extraction, Export, and Incident Report',
  'slug': 'wireshark-forensic-export-and-report',
  'architecture_type': 'custom',
  'description': "You've found the problem in a capture — now you must prove it and hand it off. This "
                 'advanced project covers profiles, statistics-driven triage, object and stream extraction, '
                 'TLS decryption with a key log file, and producing a defensible written report with '
                 'exported evidence. This is the workflow that turns raw packets into an artifact a team can '
                 'act on.',
  'objectives': ['Build a reusable Wireshark profile with columns, colors, and filter buttons',
                 'Triage an unknown capture with the Statistics suite (conversations, endpoints, protocol '
                 'hierarchy)',
                 'Extract files and full conversations via Export Objects and Follow Stream',
                 'Decrypt TLS using an SSLKEYLOGFILE to inspect application data',
                 'Export a filtered evidence subset and write a structured incident report'],
  'difficulty': 'advanced',
  'estimated_hours': 6,
  'order': 5,
  'tasks': [{'jira_key': 'WSFOR-1',
             'title': 'Create an analysis profile and triage with Statistics',
             'description': "Create a dedicated Wireshark profile so your investigation settings don't "
                            'pollute defaults. Then triage an unknown capture top-down: Protocol Hierarchy '
                            'for the traffic mix, Conversations sorted by bytes to find the heavy hitters, '
                            'and Endpoints to spot unexpected peers.',
             'acceptance_criteria': 'A named profile is active, and you identify the top talker conversation '
                                    'and the dominant application protocol from the Statistics views.',
             'hint': 'Right-click the profile name in the status bar > New. Then Statistics > Protocol '
                     "Hierarchy, Statistics > Conversations (sort by Bytes, tick 'Limit to display filter'), "
                     'Statistics > Endpoints.',
             'order': 1},
            {'jira_key': 'WSFOR-2',
             'title': 'Extract transferred files with Export Objects',
             'description': 'Pull the actual payload out of the wire. Use File > Export Objects to '
                            'reconstruct and save files transferred over HTTP (or SMB/FTP/TFTP), then verify '
                            'integrity by hashing the extracted file and comparing to what the trace claims.',
             'acceptance_criteria': 'At least one file is reconstructed via Export Objects and saved to '
                                    "disk, and its content type/size matches the capture's HTTP headers.",
             'hint': 'File > Export Objects > HTTP, select the object, Save. Verify with `sha256sum '
                     'extracted.bin` and cross-check the `Content-Length` / `Content-Type` in the matching '
                     'HTTP response.',
             'order': 2,
             'depends_on': 'WSFOR-1'},
            {'jira_key': 'WSFOR-3',
             'title': 'Decrypt TLS with a key log file',
             'description': 'You cannot read HTTPS payloads without keys. Configure Wireshark to use an '
                            'SSLKEYLOGFILE (the pre-master/session secrets a browser or curl can export) so '
                            'TLS 1.2/1.3 sessions decrypt into readable HTTP/2. Confirm the decryption by '
                            'seeing the (decrypted) app data.',
             'acceptance_criteria': 'After pointing Wireshark at the key log, previously-encrypted TLS '
                                    'records show a decrypted protocol (e.g. HTTP2) tab, and you can read a '
                                    'request path or response.',
             'hint': 'Capture with `SSLKEYLOGFILE=/tmp/keys.log curl https://...` (or set the env var for '
                     "the browser). Then Preferences > Protocols > TLS > '(Pre)-Master-Secret log filename' "
                     "> /tmp/keys.log. A 'Decrypted TLS' tab appears.",
             'order': 3,
             'depends_on': 'WSFOR-2'},
            {'jira_key': 'WSFOR-4',
             'title': 'Carve a clean evidence subset',
             'description': 'A 2 GB capture is not evidence; a scoped 200-packet extract is. Apply a display '
                            'filter that captures exactly the conversation that proves the issue, then '
                            'export only those packets to a new pcapng with a capture comment describing the '
                            'finding.',
             'acceptance_criteria': 'A new .pcapng contains only the displayed (filtered) packets for the '
                                    'relevant conversation and carries a capture comment stating the '
                                    'finding.',
             'hint': 'Apply your filter (e.g. `tcp.stream eq 12`), then File > Export Specified Packets > '
                     "choose 'Displayed'. Add a note via Statistics > Capture File Properties. CLI: `tshark "
                     "-r big.pcapng -Y 'tcp.stream==12' -w evidence.pcapng`.",
             'order': 4,
             'depends_on': 'WSFOR-3'},
            {'jira_key': 'WSFOR-5',
             'title': 'Export packet dissections for the report body',
             'description': "Turn packets into text your report can quote. Export the key packets' "
                            'dissection as plain text or CSV so exact fields, timestamps, and hex can be '
                            'pasted into the write-up without needing the reader to open Wireshark.',
             'acceptance_criteria': 'A text/CSV export of the selected packets exists showing frame numbers, '
                                    'timestamps, and the fields relevant to the finding.',
             'hint': "File > Export Packet Dissections > 'As Plain Text' (choose 'Displayed', include "
                     'detail). For tabular output: `tshark -r evidence.pcapng -T fields -e frame.number -e '
                     'frame.time -e ip.src -e tcp.flags -E header=y > packets.csv`.',
             'order': 5,
             'depends_on': 'WSFOR-4'},
            {'jira_key': 'WSFOR-6',
             'title': 'Write the structured incident report',
             'description': 'Assemble a defensible report: summary, timeline, root cause with packet-level '
                            'evidence, scope/impact, and remediation. Reference the exported evidence pcapng '
                            'and the dissection export so a reviewer can reproduce every claim.',
             'acceptance_criteria': 'A written report contains summary, timeline, evidenced root cause '
                                    '(packet numbers + values), impact, and remediation, and links to the '
                                    'exported evidence artifacts.',
             'hint': 'Structure: 1) TL;DR, 2) Timeline (UTC timestamps from packets), 3) Root cause with '
                     'frame numbers, 4) Impact, 5) Remediation, 6) Artifacts (evidence.pcapng sha256, '
                     'packets.csv). Every claim cites a packet.',
             'order': 6,
             'depends_on': 'WSFOR-5'}]},

    # ── AI Infrastructure Engineering (slug: ai-infra) — 5 projects ──
    {
        'technology_slug': 'ai-infra',
        'title': 'MAAS Commission & Deploy an H100 Node',
        'slug': 'ai-infra-maas-commission-h100',
        'architecture_type': 'custom',
        'description': (
            'Onboard a GPU bare-metal server end to end: BMC reachability, MAAS enlistment, '
            'commissioning scripts, PXE deploy of Ubuntu, and post-install nvidia-smi validation.'
        ),
        'objectives': [
            'Enlist and commission a machine in MAAS',
            'Deploy Ubuntu via PXE/Curtin/cloud-init',
            'Verify GPUs with nvidia-smi after deploy',
            'Document Ready → Deployed lifecycle',
        ],
        'difficulty': 'intermediate',
        'estimated_hours': 5,
        'order': 1,
        'tasks': [
            {'jira_key': 'AII-1', 'title': 'Reach the BMC and verify power', 'description': 'Confirm out-of-band reachability and power state before MAAS commission.', 'acceptance_criteria': '`ipmitool power status` / LAN print succeed against the BMC.', 'hint': 'Use ipmitool chassis power status and lan print; fix credentials if auth fails.', 'order': 1},
            {'jira_key': 'AII-2', 'title': 'Enlist the machine in MAAS', 'description': 'Add the node so MAAS can PXE it; confirm New/Ready inventory.', 'acceptance_criteria': '`maas admin machines read` lists the hostname.', 'hint': 'maas login, then machines read — look for serial/BMC power type.', 'order': 2, 'depends_on': 'AII-1'},
            {'jira_key': 'AII-3', 'title': 'Commission hardware', 'description': 'Run commissioning scripts and wait for Ready.', 'acceptance_criteria': 'Machine status is Ready after commission.', 'hint': 'maas admin machine commission <name> — watch BMC power + PXE ephemeral.', 'order': 3, 'depends_on': 'AII-2'},
            {'jira_key': 'AII-4', 'title': 'Deploy Ubuntu jammy', 'description': 'Deploy an approved Ubuntu image via PXE.', 'acceptance_criteria': 'Machine status Deployed with a management IP.', 'hint': 'maas admin machine deploy — Curtin + cloud-init must finish.', 'order': 4, 'depends_on': 'AII-3'},
            {'jira_key': 'AII-5', 'title': 'Validate GPUs on the node', 'description': 'SSH to the node and confirm all GPUs enumerate.', 'acceptance_criteria': '`nvidia-smi -L` lists the expected GPU count.', 'hint': 'ssh to the deployed IP; lspci | grep -i nvidia then nvidia-smi.', 'order': 5, 'depends_on': 'AII-4'},
            {'jira_key': 'AII-6', 'title': 'Hand off with inventory notes', 'description': 'Record hostname, serial, rack/U, image, and GPU SKU for CMDB.', 'acceptance_criteria': 'A short inventory note covers identity + deploy image + GPU model.', 'hint': 'Pull serial from ipmitool fru / dmidecode; SKU from nvidia-smi.', 'order': 6, 'depends_on': 'AII-5'},
        ],
    },
    {
        'technology_slug': 'ai-infra',
        'title': 'DCGM Health & Exporter for GPU Fleet',
        'slug': 'ai-infra-dcgm-exporter-fleet',
        'architecture_type': 'custom',
        'description': (
            'Stand up DCGM diagnostics and dcgm-exporter so Prometheus/Grafana can scrape GPU '
            'health. Cover discovery, diag levels 1–4, and blank-metrics triage.'
        ),
        'objectives': [
            'Run dcgmi discovery and health checks',
            'Execute diag run levels appropriately',
            'Deploy/verify dcgm-exporter metrics',
            'Triage blank or missing GPU metrics',
        ],
        'difficulty': 'intermediate',
        'estimated_hours': 4,
        'order': 2,
        'tasks': [
            {'jira_key': 'AII2-1', 'title': 'Discover GPUs with dcgmi', 'description': 'Confirm DCGM sees every GPU on the node.', 'acceptance_criteria': '`dcgmi discovery -l` lists all GPUs.', 'hint': 'If discovery fails, check nvidia driver and nv-hostengine.', 'order': 1},
            {'jira_key': 'AII2-2', 'title': 'Run deployment-level diagnostics', 'description': 'Execute a level-1/2 diagnostic and capture pass/fail.', 'acceptance_criteria': '`dcgmi diag -r 1` (or 2) completes with Pass.', 'hint': 'Start with -r 1; escalate to 2/3/4 only as needed.', 'order': 2, 'depends_on': 'AII2-1'},
            {'jira_key': 'AII2-3', 'title': 'Start dcgm-exporter', 'description': 'Run the exporter and confirm it listens on :9400.', 'acceptance_criteria': 'Exporter log shows Listening on :9400 and sample metrics render.', 'hint': 'dcgm-exporter; curl localhost:9400/metrics | grep DCGM_FI_DEV_GPU_UTIL.', 'order': 3, 'depends_on': 'AII2-1'},
            {'jira_key': 'AII2-4', 'title': 'Triage blank metrics', 'description': 'Diagnose a node that exports process but no GPU gauges.', 'acceptance_criteria': 'Root cause documented (driver/hostengine/field group) with fix applied.', 'hint': 'Check nv-hostengine, DCGM field groups, and nvidia-smi health first.', 'order': 4, 'depends_on': 'AII2-3'},
            {'jira_key': 'AII2-5', 'title': 'Wire a scrape target note', 'description': 'Document the Prometheus scrape job for this exporter.', 'acceptance_criteria': 'Scrape config snippet or runbook entry for :9400 exists.', 'hint': 'job_name: dcgm; metrics_path /metrics; targets node:9400.', 'order': 5, 'depends_on': 'AII2-3'},
        ],
    },
    {
        'technology_slug': 'ai-infra',
        'title': 'AWX Driver Rollout for GPU Nodes',
        'slug': 'ai-infra-awx-gpu-driver-rollout',
        'architecture_type': 'custom',
        'description': (
            'Use AWX to roll NVIDIA drivers across a MAAS inventory group safely: inventory sync, '
            'credentials, job template, rolling run, and verification with nvidia-smi.'
        ),
        'objectives': [
            'Sync inventory from MAAS GPU pool',
            'Author/run a driver install job template',
            'Verify drivers on sample nodes',
            'Capture job history evidence',
        ],
        'difficulty': 'intermediate',
        'estimated_hours': 4,
        'order': 3,
        'tasks': [
            {'jira_key': 'AII3-1', 'title': 'Confirm AWX inventory group', 'description': 'Ensure maas-gpu-nodes (or equivalent) exists and is populated.', 'acceptance_criteria': 'Inventory lists expected GPU hosts.', 'hint': 'awx inventories / hosts; sync from MAAS source if empty.', 'order': 1},
            {'jira_key': 'AII3-2', 'title': 'Create driver job template', 'description': 'Point a job template at the driver playbook and credentials.', 'acceptance_criteria': 'Job template is saved and launchable.', 'hint': 'Project + playbook + machine cred + inventory.', 'order': 2, 'depends_on': 'AII3-1'},
            {'jira_key': 'AII3-3', 'title': 'Launch a canary run', 'description': 'Run against one host first.', 'acceptance_criteria': 'Canary job is successful.', 'hint': 'Limit to a single hostname; watch live stdout.', 'order': 3, 'depends_on': 'AII3-2'},
            {'jira_key': 'AII3-4', 'title': 'Roll remaining nodes', 'description': 'Complete the fleet with rolling batch size.', 'acceptance_criteria': 'All target hosts show successful job status.', 'hint': 'Use forks/serial; fail fast on nvidia-smi errors.', 'order': 4, 'depends_on': 'AII3-3'},
            {'jira_key': 'AII3-5', 'title': 'Verify with nvidia-smi', 'description': 'Spot-check driver version consistency.', 'acceptance_criteria': 'Sample nodes report the expected driver version.', 'hint': 'nvidia-smi --query-gpu=driver_version --format=csv.', 'order': 5, 'depends_on': 'AII3-4'},
        ],
    },
    {
        'technology_slug': 'ai-infra',
        'title': 'Packer GPU Image Factory',
        'slug': 'ai-infra-packer-gpu-image-factory',
        'architecture_type': 'custom',
        'description': (
            'Build a custom H100/H200 jammy image with Packer: base upstream image, driver/CUDA layer, '
            'CVE gate, and publish into MAAS boot-resources — no manual bake.'
        ),
        'objectives': [
            'Author Packer HCL for GPU image',
            'Run a build with streamed logs',
            'Pass a CVE/SBOM gate',
            'Publish artifact to MAAS boot-resources',
        ],
        'difficulty': 'advanced',
        'estimated_hours': 6,
        'order': 4,
        'tasks': [
            {'jira_key': 'AII4-1', 'title': 'Define Packer template', 'description': 'HCL for jammy + NVIDIA driver layer targeting H100.', 'acceptance_criteria': 'packer validate succeeds on the template.', 'hint': 'Source upstream cloud image; provisioner shell for driver install.', 'order': 1},
            {'jira_key': 'AII4-2', 'title': 'Run packer build', 'description': 'Execute the build and capture artifact path.', 'acceptance_criteria': 'Build completes and prints artifact location.', 'hint': 'packer build gpu-h100.pkr.hcl — watch CVE gate step.', 'order': 2, 'depends_on': 'AII4-1'},
            {'jira_key': 'AII4-3', 'title': 'Clear vulnerability gate', 'description': 'Ensure high/critical CVEs are remediated or waived with rationale.', 'acceptance_criteria': 'Gate report shows allowed ship state.', 'hint': 'Rebuild after package bumps; document waivers.', 'order': 3, 'depends_on': 'AII4-2'},
            {'jira_key': 'AII4-4', 'title': 'Publish to MAAS', 'description': 'Upload custom boot resource for deploy.', 'acceptance_criteria': '`maas boot-resources read` shows custom/h100-jammy (or equivalent).', 'hint': 'maas boot-resources create / upload API.', 'order': 4, 'depends_on': 'AII4-3'},
            {'jira_key': 'AII4-5', 'title': 'Deploy from custom image', 'description': 'Deploy one Ready machine using the new image.', 'acceptance_criteria': 'Node reaches Deployed on the custom series.', 'hint': 'Specify distro_series/osystem for the custom resource.', 'order': 5, 'depends_on': 'AII4-4'},
        ],
    },
    {
        'technology_slug': 'ai-infra',
        'title': 'DCOps Thermal Incident on H100 Tray',
        'slug': 'ai-infra-dcops-h100-thermal-rma',
        'architecture_type': 'custom',
        'description': (
            'Work a realistic DCOPS thermal ticket: locate the rack, confirm GPU thermals, '
            'reseat/replace SXM tray or fans, burn-in with DCGM, and close the RMA.'
        ),
        'objectives': [
            'Locate asset in the datacenter twin',
            'Confirm thermal/power evidence',
            'Execute FRU/tray replacement workflow',
            'Burn-in and close the ticket',
        ],
        'difficulty': 'advanced',
        'estimated_hours': 5,
        'order': 5,
        'tasks': [
            {'jira_key': 'AII5-1', 'title': 'Badge in and locate the rack', 'description': 'Enter the DC twin and find the failing H100 node.', 'acceptance_criteria': 'Server selected in the correct rack/U.', 'hint': 'Search hostname/serial; confirm row/aisle from ticket.', 'order': 1},
            {'jira_key': 'AII5-2', 'title': 'Collect thermal evidence', 'description': 'Capture nvidia-smi / dcgmi temps and BMC sensors.', 'acceptance_criteria': 'Evidence shows which GPU(s) violate thresholds.', 'hint': 'nvidia-smi -q -d TEMPERATURE; ipmitool sensor.', 'order': 2, 'depends_on': 'AII5-1'},
            {'jira_key': 'AII5-3', 'title': 'Open RMA / pull spare', 'description': 'Order or pull the correct FRU from inventory.', 'acceptance_criteria': 'Parts ticket references correct FRU and availability.', 'hint': 'Match SXM tray / fan FRU to vendor BOM.', 'order': 3, 'depends_on': 'AII5-2'},
            {'jira_key': 'AII5-4', 'title': 'Replace and reseat', 'description': 'Power down via BMC, swap FRU, reseat power/data cables.', 'acceptance_criteria': 'Node powers on; all GPUs enumerate.', 'hint': 'ipmitool power cycle after tray seat; nvidia-smi -L.', 'order': 4, 'depends_on': 'AII5-3'},
            {'jira_key': 'AII5-5', 'title': 'Burn-in diagnostics', 'description': 'Run DCGM diag and a short stress window.', 'acceptance_criteria': 'Diag Pass and thermals stay within limit.', 'hint': 'dcgmi diag -r 3 or 4; watch dmon for 5–10 minutes.', 'order': 5, 'depends_on': 'AII5-4'},
            {'jira_key': 'AII5-6', 'title': 'Close ticket with evidence', 'description': 'Attach before/after metrics and return node to production pool.', 'acceptance_criteria': 'Ticket closed with evidence pack linked.', 'hint': 'Include nvidia-smi, dcgmi, and BMC sensor snippets.', 'order': 6, 'depends_on': 'AII5-5'},
        ],
    },
    {
        'technology_slug': 'ai-infra',
        'title': 'ImageDev cloud-init GPU First Boot',
        'slug': 'ai-infra-imagedev-cloud-init-gpu',
        'architecture_type': 'custom',
        'description': (
            'Own the ImageDev first-boot path: Packer userdata with DataSourceMAAS, '
            'nvidia-persistenced, and gpu-sanity hooks so Deployed nodes finish cloud-init cleanly.'
        ),
        'objectives': [
            'Validate cloud-init datasource and status',
            'Confirm GPU runcmd hooks on first boot',
            'Verify nvidia-smi after cloud-init final',
        ],
        'difficulty': 'intermediate',
        'estimated_hours': 4,
        'order': 6,
        'tasks': [
            {'jira_key': 'AII6-1', 'title': 'Inspect cloud-init status', 'description': 'Confirm DataSourceMAAS and status done on a Deployed GPU node.', 'acceptance_criteria': '`cloud-init status` shows done; `cloud-id` returns maas.', 'hint': 'cloud-init status --long; cloud-id.', 'order': 1},
            {'jira_key': 'AII6-2', 'title': 'Validate GPU userdata', 'description': 'Ensure runcmd enables persistenced and runs sanity.', 'acceptance_criteria': 'Userdata includes nvidia-persistenced and gpu-sanity.', 'hint': 'Review Packer write_files / cloud-init snippets.', 'order': 2, 'depends_on': 'AII6-1'},
            {'jira_key': 'AII6-3', 'title': 'Confirm GPUs after final', 'description': 'After cloud-init final, enumerate GPUs.', 'acceptance_criteria': '`nvidia-smi -L` lists expected SKUs.', 'hint': 'Wait for final_message then nvidia-smi -L.', 'order': 3, 'depends_on': 'AII6-2'},
            {'jira_key': 'AII6-4', 'title': 'Document ImageDev handoff', 'description': 'Record image name, cloud-init version, and sanity note for CMDB.', 'acceptance_criteria': 'Handoff note lists boot resource + cloud-init done + GPU count.', 'hint': 'Pull image from MAAS Images; paste cloud-init status snippet.', 'order': 4, 'depends_on': 'AII6-3'},
        ],
    },
    {
        'technology_slug': 'ai-infra',
        'title': 'ImageDev GPU Sanity Gate',
        'slug': 'ai-infra-imagedev-gpu-sanity-suite',
        'architecture_type': 'custom',
        'description': (
            'Run the ImageDev GPU sanity suite (deviceQuery, bandwidthTest, nvidia-smi, '
            'dcgmi diag -r 1) before publishing Packer artifacts to MAAS.'
        ),
        'objectives': [
            'Execute gpu-sanity harness',
            'Pass DCGM level-1 diagnostics',
            'Clear the MAAS publish gate',
        ],
        'difficulty': 'intermediate',
        'estimated_hours': 3,
        'order': 7,
        'tasks': [
            {'jira_key': 'AII7-1', 'title': 'Run gpu-sanity', 'description': 'Execute the ImageDev sanity harness on the baked image.', 'acceptance_criteria': 'Report shows ALL PASS.', 'hint': 'gpu-sanity or deviceQuery + bandwidthTest.', 'order': 1},
            {'jira_key': 'AII7-2', 'title': 'DCGM r1 gate', 'description': 'Run dcgmi diag -r 1 as the release gate.', 'acceptance_criteria': 'All diagnostic rows Pass.', 'hint': 'dcgmi diag -r 1', 'order': 2, 'depends_on': 'AII7-1'},
            {'jira_key': 'AII7-3', 'title': 'Publish to MAAS', 'description': 'Upload boot resource only after gate green.', 'acceptance_criteria': 'custom GPU image listed in MAAS Images.', 'hint': 'Packer Publish to MAAS / maas boot-resources.', 'order': 3, 'depends_on': 'AII7-2'},
            {'jira_key': 'AII7-4', 'title': 'Deploy canary from image', 'description': 'Deploy one Ready machine on the published series.', 'acceptance_criteria': 'Node reaches Deployed on the custom image.', 'hint': 'Bare Metal Deploy with boot resource picker.', 'order': 4, 'depends_on': 'AII7-3'},
        ],
    },
    {
        'technology_slug': 'ai-infra',
        'title': 'vLLM on H100 Inference Bring-Up',
        'slug': 'ai-infra-vllm-h100-serve',
        'architecture_type': 'custom',
        'description': (
            'AI Infra bring-up of vLLM on a MAAS-deployed H100 node: tensor parallel serve, '
            'OpenAI-compatible API on :8000, optional throughput bench — infra path, not app ML.'
        ),
        'objectives': [
            'Validate GPU health on Deployed node',
            'Start vLLM with tensor parallelism',
            'Confirm OpenAI API readiness',
        ],
        'difficulty': 'advanced',
        'estimated_hours': 5,
        'order': 8,
        'tasks': [
            {'jira_key': 'AII8-1', 'title': 'Confirm H100 inventory', 'description': 'nvidia-smi -L matches expected SXM count.', 'acceptance_criteria': 'All GPUs listed and driver healthy.', 'hint': 'nvidia-smi -L; dcgmi discovery.', 'order': 1},
            {'jira_key': 'AII8-2', 'title': 'Launch vLLM serve', 'description': 'Start vllm serve with tensor-parallel-size = GPU count.', 'acceptance_criteria': 'Log shows Uvicorn on :8000 and READY.', 'hint': 'vllm serve <model> --tensor-parallel-size 8', 'order': 2, 'depends_on': 'AII8-1'},
            {'jira_key': 'AII8-3', 'title': 'Smoke the API', 'description': 'Optional bench or curl /v1/models style check.', 'acceptance_criteria': 'Endpoint responds or bench Result PASS.', 'hint': 'vllm bench throughput --model …', 'order': 3, 'depends_on': 'AII8-2'},
            {'jira_key': 'AII8-4', 'title': 'Hand off inference endpoint', 'description': 'Document host:8000, model, and TP size for the platform team.', 'acceptance_criteria': 'Handoff note includes endpoint URL + model + tensor parallel.', 'hint': 'Capture vllm READY line and nvidia-smi GPU count.', 'order': 4, 'depends_on': 'AII8-3'},
        ],
    },
    {
        'technology_slug': 'ai-infra',
        'title': 'E2E Image Factory to Inference',
        'slug': 'ai-infra-e2e-image-to-inference',
        'architecture_type': 'custom',
        'description': (
            'Full Bare Metal + ImageDev handoff: Packer build → MAAS publish/deploy → '
            'cloud-init + GPU sanity → vLLM serve. End-to-end AI Infra Engineering project.'
        ),
        'objectives': [
            'Publish Packer GPU image to MAAS',
            'Deploy and pass ImageDev gates',
            'Serve inference with vLLM',
        ],
        'difficulty': 'advanced',
        'estimated_hours': 8,
        'order': 9,
        'tasks': [
            {'jira_key': 'AII9-1', 'title': 'Packer build + publish', 'description': 'Build GPU image and publish boot resource.', 'acceptance_criteria': 'MAAS Images lists custom GPU series.', 'hint': 'Packer IDE → Publish to MAAS.', 'order': 1},
            {'jira_key': 'AII9-2', 'title': 'MAAS deploy', 'description': 'Deploy Ready node with custom image.', 'acceptance_criteria': 'Machine Deployed; cloud-init done.', 'hint': 'Deploy with boot_resource picker; cloud-init status.', 'order': 2, 'depends_on': 'AII9-1'},
            {'jira_key': 'AII9-3', 'title': 'Sanity gate', 'description': 'gpu-sanity + dcgmi diag -r 1 PASS.', 'acceptance_criteria': 'ALL PASS report.', 'hint': 'gpu-sanity; dcgmi diag -r 1.', 'order': 3, 'depends_on': 'AII9-2'},
            {'jira_key': 'AII9-4', 'title': 'vLLM ready', 'description': 'Start vLLM and confirm :8000 READY.', 'acceptance_criteria': 'OpenAI-compatible server ready.', 'hint': 'vllm serve … --tensor-parallel-size N', 'order': 4, 'depends_on': 'AII9-3'},
        ],
    },
]
