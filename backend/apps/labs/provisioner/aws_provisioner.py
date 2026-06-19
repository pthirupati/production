"""
AWS EC2 provisioner for FixitLab.
Launches EC2 instances for scenarios that need full Linux servers
(filesystem operations, kernel modules, LVM, real systemd, etc.)
"""
import logging
import time
import io
import threading
import paramiko
from django.conf import settings

logger = logging.getLogger(__name__)


class EC2Provisioner:
    """
    Manages AWS EC2 instances for lab sessions.

    Lifecycle:
      1. provision() — launch EC2 instance with user-data setup script
      2. create_exec_stream() — SSH interactive channel for terminal
      3. execute_command() / run_validation() — SSH command execution
      4. terminate() — terminate and clean up EC2 instance

    Required settings:
      AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION,
      AWS_LAB_SUBNET_ID, AWS_LAB_SECURITY_GROUP_ID, AWS_LAB_KEY_PAIR,
      AWS_LAB_KEY_PEM (private key content or path)
    """

    def __init__(self):
        import boto3
        self.ec2_client = boto3.client(
            "ec2",
            region_name=getattr(settings, "AWS_REGION", "us-east-1"),
            aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", ""),
            aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", ""),
        )
        self.ec2_resource = boto3.resource(
            "ec2",
            region_name=getattr(settings, "AWS_REGION", "us-east-1"),
            aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", ""),
            aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", ""),
        )
        self._ssh_connections = {}  # instance_id -> paramiko.SSHClient
        self._ssh_lock = threading.Lock()  # Thread-safe SSH cache access

    def _get_ami(self, scenario):
        """
        Get the AMI for a scenario.
        First checks scenario.cloud_ami, then falls back to configured base AMI.
        """
        if hasattr(scenario, "cloud_ami") and scenario.cloud_ami:
            return scenario.cloud_ami

        return getattr(settings, "AWS_LAB_BASE_AMI", "ami-0c7217cdde317cfec")

    def _get_ssh_user_for_ami(self, ami_id):
        """
        Detect the default SSH username for an AMI by inspecting its name/description.
        - Ubuntu → ubuntu
        - Amazon Linux / AL2 → ec2-user
        - RHEL / CentOS / Fedora → ec2-user
        - Debian → admin
        - SUSE → ec2-user
        Falls back to ec2-user (works for most non-Ubuntu AMIs).
        """
        try:
            resp = self.ec2_client.describe_images(ImageIds=[ami_id])
            images = resp.get("Images", [])
            if not images:
                return "ec2-user"
            name = (images[0].get("Name") or "").lower()
            desc = (images[0].get("Description") or "").lower()
            combined = f"{name} {desc}"

            if "ubuntu" in combined:
                return "ubuntu"
            elif "debian" in combined:
                return "admin"
            elif any(kw in combined for kw in ["rhel", "red hat", "centos", "fedora", "amazon", "suse", "al2"]):
                return "ec2-user"
            else:
                return "ec2-user"  # safe default
        except Exception as e:
            logger.warning(f"Could not detect SSH user for AMI {ami_id}: {e}")
            return "ec2-user"

    def _build_user_data(self, lab_session):
        """
        Build the cloud-init user-data script.

        Auto-detects package manager (apt vs dnf/yum) so it works on
        Ubuntu, RHEL, Amazon Linux, CentOS, etc.

        When using the golden AMI (recommended), all base packages are
        pre-installed so this script only writes metadata + scenario setup.
        """
        scenario = lab_session.scenario
        setup_script = getattr(scenario, "cloud_setup_script", "") or ""
        validation_script = scenario.validation_script or ""

        user_data = f"""#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive

# Tag this as a FixitLab instance
mkdir -p /opt/fixitlab
echo "FIXITLAB_SESSION_ID={lab_session.id}" > /opt/fixitlab_env
echo "FIXITLAB_SCENARIO={scenario.slug}" >> /opt/fixitlab_env

# If golden AMI marker exists, skip base package install (already pre-baked)
if [ ! -f /opt/fixitlab/.ami-ready ]; then
    echo "Installing base packages..." >> /var/log/fixitlab-setup.log
    # Auto-detect package manager
    if command -v apt-get &>/dev/null; then
        apt-get update -qq
        apt-get install -y -qq vim nano less procps net-tools curl wget htop 2>>/var/log/fixitlab-setup.log
    elif command -v dnf &>/dev/null; then
        dnf install -y -q vim-enhanced nano less procps-ng net-tools curl wget htop 2>>/var/log/fixitlab-setup.log
    elif command -v yum &>/dev/null; then
        yum install -y -q vim-enhanced nano less procps-ng net-tools curl wget htop 2>>/var/log/fixitlab-setup.log
    fi
fi

# Write validation script
cat > /opt/fixitlab/check.sh << 'CHECKEOF'
{validation_script}
CHECKEOF
chmod +x /opt/fixitlab/check.sh

# Disable set -e for scenario setup (setup scripts intentionally break things,
# and some commands may fail as part of the broken state)
set +e

# Run scenario setup (creates the broken state)
{setup_script}

# Re-enable strict mode
set -e

# Signal readiness
touch /opt/fixitlab/.ready
echo "FixitLab setup complete" >> /var/log/fixitlab-setup.log
"""
        return user_data

    def provision(self, lab_session):
        """
        Launch an EC2 instance for the lab session.
        Returns (instance_id, instance_name).

        Idempotent: if lab_session already has an instance_id, checks
        that instance status instead of launching a new one.
        """
        # Human-readable name: fixitlab-{username}-{short_id}
        username = lab_session.user.username if hasattr(lab_session, 'user') and lab_session.user else 'unknown'
        short_id = str(lab_session.id).split('-')[0]
        instance_name = f"fixitlab-{username}-{short_id}"

        # ── Idempotency: if an instance was already launched, resume ──
        if lab_session.instance_id:
            existing_id = lab_session.instance_id
            try:
                state = self.get_status(existing_id)
                if state in ("running", "pending"):
                    host = lab_session.ssh_host or self._resolve_host(existing_id)
                    ssh_user = lab_session.ssh_user or "ec2-user"
                    if host:
                        lab_session.ssh_host = host
                        lab_session.ssh_user = ssh_user
                        lab_session.save(update_fields=["ssh_host", "ssh_user"])
                    self._wait_for_ssh_ready(host, ssh_user=ssh_user, timeout=180)
                    logger.info(
                        f"Resumed existing EC2 instance {existing_id} at {host} "
                        f"for session {lab_session.id}"
                    )
                    return existing_id, instance_name
                else:
                    logger.warning(
                        f"Existing instance {existing_id} is {state}, launching new"
                    )
            except Exception as e:
                logger.warning(f"Failed to resume instance {existing_id}: {e}")

        # ── Launch a new EC2 instance ──
        scenario = lab_session.scenario
        ami = self._get_ami(scenario)
        ssh_user = self._get_ssh_user_for_ami(ami)
        instance_type = getattr(settings, "AWS_LAB_INSTANCE_TYPE", "t3.micro")
        key_pair = getattr(settings, "AWS_LAB_KEY_PAIR", "fixitlab-labs")
        subnet_id = getattr(settings, "AWS_LAB_SUBNET_ID", "")
        sg_id = getattr(settings, "AWS_LAB_SECURITY_GROUP_ID", "")
        user_data = self._build_user_data(lab_session)

        instance_id = None
        try:
            run_params = {
                "ImageId": ami,
                "InstanceType": instance_type,
                "KeyName": key_pair,
                "MinCount": 1,
                "MaxCount": 1,
                "UserData": user_data,
                "TagSpecifications": [
                    {
                        "ResourceType": "instance",
                        "Tags": [
                            {"Key": "Name", "Value": instance_name},
                            {"Key": "fixitlab:session_id", "Value": str(lab_session.id)},
                            {"Key": "fixitlab:user_id", "Value": str(lab_session.user_id)},
                            {"Key": "fixitlab:scenario", "Value": scenario.slug},
                            {"Key": "fixitlab:created", "Value": str(int(time.time()))},
                            {"Key": "fixitlab:auto_terminate", "Value": "true"},
                        ],
                    }
                ],
                "InstanceInitiatedShutdownBehavior": "terminate",
            }

            if subnet_id:
                run_params["SubnetId"] = subnet_id
            if sg_id:
                run_params["SecurityGroupIds"] = [sg_id]

            response = self.ec2_client.run_instances(**run_params)
            instance_id = response["Instances"][0]["InstanceId"]

            logger.info(
                f"Launched EC2 instance {instance_id} ({instance_name}) "
                f"for session {lab_session.id}"
            )

            # ── CRITICAL: save instance_id to DB immediately ──
            # This prevents a second instance from being launched on retry.
            lab_session.instance_id = instance_id
            lab_session.save(update_fields=["instance_id"])

            # Wait for instance to be running
            self._wait_for_instance(instance_id, timeout=120)

            # Get public IP
            instance = self.ec2_resource.Instance(instance_id)
            instance.reload()
            public_ip = instance.public_ip_address

            if not public_ip:
                desc = self.ec2_client.describe_instances(InstanceIds=[instance_id])
                public_ip = (
                    desc["Reservations"][0]["Instances"][0]
                    .get("PublicIpAddress", "")
                )

            # Store SSH info on the lab session
            lab_session.ssh_host = public_ip or ""
            lab_session.ssh_user = ssh_user
            lab_session.save(update_fields=["ssh_host", "ssh_user"])

            logger.info(
                f"EC2 instance {instance_id}: AMI={ami}, user={ssh_user}, IP={public_ip}"
            )

            # Wait for SSH to be ready and setup script to complete
            self._wait_for_ssh_ready(public_ip, ssh_user=ssh_user, timeout=180)

            logger.info(
                f"EC2 instance {instance_id} ready at {public_ip} "
                f"for session {lab_session.id}"
            )

            return instance_id, instance_name

        except Exception as e:
            logger.error(f"Failed to launch EC2 instance: {e}")
            # If instance was launched but SSH failed, terminate to avoid orphans
            if instance_id:
                try:
                    self.terminate(instance_id)
                    logger.info(f"Cleaned up failed instance {instance_id}")
                except Exception as te:
                    logger.error(f"Failed to cleanup instance {instance_id}: {te}")
                # Clear the instance_id so next retry starts fresh
                lab_session.instance_id = None
                lab_session.ssh_host = ""
                lab_session.save(update_fields=["instance_id", "ssh_host"])
            raise

    def _wait_for_instance(self, instance_id, timeout=120):
        """Wait for EC2 instance to reach 'running' state."""
        logger.info(f"Waiting for instance {instance_id} to start...")
        waiter = self.ec2_client.get_waiter("instance_running")
        waiter.wait(
            InstanceIds=[instance_id],
            WaiterConfig={"Delay": 5, "MaxAttempts": timeout // 5},
        )

    def _wait_for_ssh_ready(self, host, ssh_user=None, timeout=180, port=22):
        """
        Wait until SSH is available and setup script has completed.
        Does NOT raise on timeout — the terminal consumer has reconnection
        logic and the .ready file check handles late setup completion.
        """
        import socket

        if not host:
            logger.warning("No host provided for SSH readiness check")
            return

        username = ssh_user or "ec2-user"
        start = time.time()
        ssh_connected = False
        while time.time() - start < timeout:
            try:
                sock = socket.create_connection((host, port), timeout=5)
                sock.close()
                ssh_connected = True

                # SSH port is open — now check if setup is complete
                ssh = self._get_ssh_client(host, username=username)
                _, stdout, _ = ssh.exec_command(
                    "test -f /opt/fixitlab/.ready && echo READY || echo WAITING"
                )
                result = stdout.read().decode().strip()
                if result == "READY":
                    logger.info(f"Instance at {host} is fully ready (user={username})")
                    return
            except Exception:
                pass
            time.sleep(5)

        # Don't raise — the instance IS running, just setup may still be in progress
        if ssh_connected:
            logger.warning(
                f"Instance at {host}: SSH port open but setup not complete after {timeout}s. "
                f"Proceeding — user can start working while setup finishes."
            )
        else:
            logger.warning(
                f"Instance at {host}: SSH port not reachable after {timeout}s. "
                f"Instance may still be booting. Terminal will retry connection."
            )

    def _get_ssh_client(self, host_or_instance_id, username=None):
        """
        Get or create an SSH client for the given host.
        Uses the configured private key. Thread-safe via _ssh_lock.
        """
        cache_key = f"{host_or_instance_id}:{username or 'default'}"

        with self._ssh_lock:
            if cache_key in self._ssh_connections:
                client = self._ssh_connections[cache_key]
                # Test if still connected
                try:
                    client.exec_command("echo ok", timeout=5)
                    return client
                except Exception:
                    try:
                        client.close()
                    except Exception:
                        pass
                    del self._ssh_connections[cache_key]

        host = host_or_instance_id
        # If it looks like an instance ID, resolve to IP
        if host.startswith("i-"):
            instance = self.ec2_resource.Instance(host)
            instance.reload()
            host = instance.public_ip_address

        ssh_user = username or "ec2-user"
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Load private key
        pkey = self._load_private_key()

        client.connect(
            hostname=host,
            username=ssh_user,
            pkey=pkey,
            timeout=15,
            banner_timeout=15,
            auth_timeout=15,
            allow_agent=False,
            look_for_keys=False,
        )

        with self._ssh_lock:
            # Evict stale connections if cache grows too large
            if len(self._ssh_connections) > 100:
                for old_key in list(self._ssh_connections.keys())[:20]:
                    try:
                        self._ssh_connections[old_key].close()
                    except Exception:
                        pass
                    del self._ssh_connections[old_key]
            self._ssh_connections[cache_key] = client
        return client

    def _load_private_key(self):
        """Load the SSH private key from settings (auto-detects key type)."""
        key_pem = getattr(settings, "AWS_LAB_KEY_PEM", "")
        key_path = getattr(settings, "AWS_LAB_KEY_PATH", "")

        if key_pem:
            return self._parse_private_key(pem_str=key_pem)
        elif key_path:
            return self._parse_private_key(file_path=key_path)
        else:
            raise ValueError(
                "No SSH key configured. Set AWS_LAB_KEY_PEM or AWS_LAB_KEY_PATH."
            )

    @staticmethod
    def _parse_private_key(pem_str=None, file_path=None):
        """Auto-detect and load RSA, Ed25519, or ECDSA private keys."""
        key_classes = [
            paramiko.Ed25519Key,
            paramiko.RSAKey,
            paramiko.ECDSAKey,
        ]
        for cls in key_classes:
            try:
                if pem_str:
                    return cls.from_private_key(io.StringIO(pem_str))
                else:
                    return cls.from_private_key_file(file_path)
            except (paramiko.SSHException, ValueError):
                continue
        src = "PEM string" if pem_str else file_path
        raise ValueError(f"Unable to parse SSH key ({src}). Supported: Ed25519, RSA, ECDSA.")

    def _resolve_host(self, instance_id):
        """Resolve an instance_id to its public IP address."""
        if not instance_id.startswith("i-"):
            return instance_id  # Already an IP/hostname
        instance = self.ec2_resource.Instance(instance_id)
        instance.reload()
        return instance.public_ip_address

    def execute_command(self, instance_id, command, ssh_user=None):
        """Execute a command on the EC2 instance via SSH."""
        try:
            host = self._resolve_host(instance_id)
            username = ssh_user or "ec2-user"
            ssh = self._get_ssh_client(host, username=username)
            _, stdout, stderr = ssh.exec_command(command, timeout=60)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="replace")
            err_output = stderr.read().decode("utf-8", errors="replace")
            return exit_code, output + err_output
        except Exception as e:
            logger.error(f"SSH command failed on {instance_id}: {e}")
            raise

    def create_exec_stream(self, instance_id, ssh_user=None):
        """
        Create an interactive SSH channel for terminal access.
        Returns (channel_id, paramiko_channel) — the channel is used
        like a socket for read/write by the TerminalConsumer.

        Includes retry logic to handle "Error reading SSH protocol banner"
        which occurs when SSH is still starting up on the EC2 instance.
        """
        host = self._resolve_host(instance_id)
        pkey = self._load_private_key()
        username = ssh_user or "ec2-user"

        max_attempts = 15   # up to ~75 seconds of retries
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                client.connect(
                    hostname=host,
                    username=username,
                    pkey=pkey,
                    timeout=10,
                    banner_timeout=15,
                    auth_timeout=15,
                    allow_agent=False,
                    look_for_keys=False,
                )

                # Open interactive shell channel
                channel = client.invoke_shell(
                    term="xterm-256color",
                    width=120,
                    height=40,
                )
                channel.setblocking(True)

                # Store the client reference so it doesn't get GC'd
                channel._ssh_client = client

                channel_id = f"ssh-{instance_id}-{int(time.time())}"

                if attempt > 1:
                    logger.info(
                        f"SSH stream created for {instance_id} on attempt {attempt}"
                    )

                return channel_id, channel

            except Exception as e:
                last_error = e
                try:
                    client.close()
                except Exception:
                    pass

                if attempt < max_attempts:
                    logger.debug(
                        f"SSH connect attempt {attempt}/{max_attempts} failed "
                        f"for {instance_id} ({host}): {e}"
                    )
                    time.sleep(5)
                else:
                    logger.error(
                        f"Failed to create SSH stream for {instance_id} after "
                        f"{max_attempts} attempts: {e}"
                    )

        raise last_error

    def run_validation(self, instance_id, validation_script):
        """Run validation script on the EC2 instance."""
        try:
            exit_code, output = self.execute_command(
                instance_id, validation_script
            )
            return exit_code == 0, output
        except Exception as e:
            logger.error(f"Validation failed on {instance_id}: {e}")
            return False, str(e)

    def terminate(self, instance_id, session_id=None):
        """Terminate the EC2 instance."""
        try:
            self.ec2_client.terminate_instances(InstanceIds=[instance_id])
            logger.info(f"Terminated EC2 instance {instance_id}")

            # Clean up SSH connections for this instance only
            with self._ssh_lock:
                for key in list(self._ssh_connections.keys()):
                    if instance_id in key:
                        try:
                            self._ssh_connections[key].close()
                        except Exception:
                            pass
                        del self._ssh_connections[key]

        except Exception as e:
            logger.error(f"Failed to terminate EC2 instance {instance_id}: {e}")

    def get_status(self, instance_id):
        """Get the current status of an EC2 instance."""
        try:
            response = self.ec2_client.describe_instances(
                InstanceIds=[instance_id]
            )
            state = response["Reservations"][0]["Instances"][0]["State"]["Name"]
            return state  # pending, running, stopping, stopped, terminated
        except Exception:
            return "terminated"

    def cleanup_expired(self, max_age_seconds=3600):
        """Terminate all FixitLab EC2 instances older than max_age_seconds."""
        if not getattr(settings, "AWS_ACCESS_KEY_ID", "") or not getattr(settings, "AWS_SECRET_ACCESS_KEY", ""):
            return 0
        if not getattr(settings, "AWS_LAB_SUBNET_ID", "") or not getattr(settings, "AWS_LAB_SECURITY_GROUP_ID", ""):
            return 0
        try:
            response = self.ec2_client.describe_instances(
                Filters=[
                    {"Name": "tag:fixitlab:auto_terminate", "Values": ["true"]},
                    {"Name": "instance-state-name", "Values": ["running", "pending"]},
                ]
            )

            terminated = 0
            for reservation in response.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    # Check age from tags
                    tags = {t["Key"]: t["Value"] for t in instance.get("Tags", [])}
                    created = int(tags.get("fixitlab:created", "0"))
                    if created and (time.time() - created) > max_age_seconds:
                        instance_id = instance["InstanceId"]
                        self.ec2_client.terminate_instances(InstanceIds=[instance_id])
                        terminated += 1
                        logger.info(f"Cleaned up expired EC2 instance {instance_id}")

            return terminated
        except Exception as e:
            logger.warning(f"EC2 cleanup skipped: {e}")
            return 0
