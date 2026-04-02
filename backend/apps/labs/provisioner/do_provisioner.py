"""
DigitalOcean Droplet provisioner for FixitLab.
Launches droplets for scenarios that need full Linux servers
(filesystem operations, kernel modules, LVM, real systemd, etc.)
"""
import logging
import time
import io
import requests
import paramiko
from django.conf import settings

logger = logging.getLogger(__name__)

DO_API_BASE = "https://api.digitalocean.com/v2"


class DOProvisioner:
    """
    Manages DigitalOcean Droplets for lab sessions.

    Lifecycle:
      1. provision() — create droplet with user-data setup script
      2. create_exec_stream() — SSH interactive channel for terminal
      3. execute_command() / run_validation() — SSH command execution
      4. terminate() — destroy droplet

    Required settings:
      DO_API_TOKEN — DigitalOcean API token
      DO_SSH_KEY_ID — SSH key ID registered in DO account
      DO_SSH_KEY_PEM or DO_SSH_KEY_PATH — private key for SSH access
      DO_REGION — region (default: nyc1)
      DO_SIZE — droplet size (default: s-1vcpu-1gb)
    """

    def __init__(self):
        self.api_token = getattr(settings, "DO_API_TOKEN", "")
        if not self.api_token:
            raise ValueError("DO_API_TOKEN not configured")
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        self._ssh_connections = {}

    def _api(self, method, path, json=None, timeout=30):
        """Make a DO API request."""
        url = f"{DO_API_BASE}{path}"
        resp = requests.request(
            method, url, headers=self.headers, json=json, timeout=timeout
        )
        if resp.status_code >= 400:
            logger.error(f"DO API error {resp.status_code}: {resp.text}")
            resp.raise_for_status()
        return resp.json() if resp.text else {}

    def _build_user_data(self, lab_session):
        """Build cloud-init user-data for the droplet."""
        scenario = lab_session.scenario
        setup_script = getattr(scenario, "cloud_setup_script", "") or ""
        validation_script = scenario.validation_script or ""

        return f"""#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive

# Tag this as a FixitLab instance
echo "FIXITLAB_SESSION_ID={lab_session.id}" > /opt/fixitlab_env
echo "FIXITLAB_SCENARIO={scenario.slug}" >> /opt/fixitlab_env

# Install base packages
apt-get update -qq
apt-get install -y -qq vim nano less procps net-tools curl wget htop

# Create validation directory
mkdir -p /opt/fixitlab

# Write validation script
cat > /opt/fixitlab/check.sh << 'CHECKEOF'
{validation_script}
CHECKEOF
chmod +x /opt/fixitlab/check.sh

# Run scenario setup (creates the broken state)
{setup_script}

# Signal readiness
touch /opt/fixitlab/.ready
echo "FixitLab setup complete" >> /var/log/fixitlab-setup.log
"""

    def provision(self, lab_session):
        """
        Create a DigitalOcean Droplet for the lab session.
        Returns (droplet_id_str, droplet_name).
        """
        scenario = lab_session.scenario
        droplet_name = f"fixitlab-{lab_session.id}"
        region = getattr(settings, "DO_REGION", "nyc1")
        size = getattr(settings, "DO_SIZE", "s-1vcpu-1gb")
        image = getattr(scenario, "cloud_image", "") or "ubuntu-22-04-x64"
        ssh_key_id = getattr(settings, "DO_SSH_KEY_ID", "")
        user_data = self._build_user_data(lab_session)

        try:
            payload = {
                "name": droplet_name,
                "region": region,
                "size": size,
                "image": image,
                "ssh_keys": [ssh_key_id] if ssh_key_id else [],
                "user_data": user_data,
                "backups": False,
                "ipv6": False,
                "monitoring": False,
                "tags": [
                    "fixitlab",
                    f"session:{lab_session.id}",
                    f"scenario:{scenario.slug}",
                ],
            }

            data = self._api("POST", "/droplets", json=payload)
            droplet_id = str(data["droplet"]["id"])

            logger.info(
                f"Created DO droplet {droplet_id} ({droplet_name}) "
                f"for session {lab_session.id}"
            )

            # Wait for droplet to become active and get IP
            public_ip = self._wait_for_droplet(droplet_id, timeout=120)

            # Store SSH info on the lab session
            lab_session.ssh_host = public_ip
            lab_session.ssh_user = "root"
            lab_session.save(update_fields=["ssh_host", "ssh_user"])

            # Wait for SSH and setup to complete
            self._wait_for_ssh_ready(public_ip, timeout=180)

            logger.info(
                f"DO droplet {droplet_id} ready at {public_ip} "
                f"for session {lab_session.id}"
            )

            return droplet_id, droplet_name

        except Exception as e:
            logger.error(f"Failed to create DO droplet: {e}")
            raise

    def _wait_for_droplet(self, droplet_id, timeout=120):
        """Wait for droplet to reach 'active' status and return its public IP."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                data = self._api("GET", f"/droplets/{droplet_id}")
                droplet = data["droplet"]
                if droplet["status"] == "active":
                    # Get public IPv4
                    for net in droplet.get("networks", {}).get("v4", []):
                        if net["type"] == "public":
                            return net["ip_address"]
            except Exception as e:
                logger.debug(f"Waiting for droplet {droplet_id}: {e}")
            time.sleep(5)

        raise TimeoutError(
            f"Droplet {droplet_id} not active after {timeout}s"
        )

    def _wait_for_ssh_ready(self, host, timeout=180, port=22):
        """Wait until SSH is available and setup script has completed."""
        import socket

        start = time.time()
        while time.time() - start < timeout:
            try:
                sock = socket.create_connection((host, port), timeout=5)
                sock.close()

                # Check if setup is complete
                ssh = self._get_ssh_client(host)
                _, stdout, _ = ssh.exec_command(
                    "test -f /opt/fixitlab/.ready && echo READY || echo WAITING"
                )
                result = stdout.read().decode().strip()
                if result == "READY":
                    logger.info(f"Droplet at {host} is ready")
                    return
            except Exception:
                pass
            time.sleep(5)

        logger.warning(f"Droplet at {host} not fully ready after {timeout}s")

    def _get_ssh_client(self, host):
        """Get or create an SSH client for the given host."""
        if host in self._ssh_connections:
            client = self._ssh_connections[host]
            try:
                client.exec_command("echo ok", timeout=5)
                return client
            except Exception:
                try:
                    client.close()
                except Exception:
                    pass

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        pkey = self._load_private_key()

        client.connect(
            hostname=host,
            username="root",
            pkey=pkey,
            timeout=30,
            allow_agent=False,
            look_for_keys=False,
        )

        self._ssh_connections[host] = client
        return client

    def _load_private_key(self):
        """Load the SSH private key from settings (auto-detects key type)."""
        key_pem = getattr(settings, "DO_SSH_KEY_PEM", "")
        key_path = getattr(settings, "DO_SSH_KEY_PATH", "")

        if key_pem:
            return self._parse_private_key(pem_str=key_pem)
        elif key_path:
            return self._parse_private_key(file_path=key_path)
        else:
            raise ValueError(
                "No SSH key configured. Set DO_SSH_KEY_PEM or DO_SSH_KEY_PATH."
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

    def execute_command(self, droplet_id, command):
        """Execute a command on the droplet via SSH."""
        try:
            host = self._resolve_host(droplet_id)
            ssh = self._get_ssh_client(host)
            _, stdout, stderr = ssh.exec_command(command, timeout=60)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="replace")
            err_output = stderr.read().decode("utf-8", errors="replace")
            return exit_code, output + err_output
        except Exception as e:
            logger.error(f"SSH command failed on droplet {droplet_id}: {e}")
            raise

    def _resolve_host(self, droplet_id):
        """Resolve a droplet ID to its public IP."""
        # If it already looks like an IP, return as-is
        if "." in str(droplet_id):
            return droplet_id
        try:
            data = self._api("GET", f"/droplets/{droplet_id}")
            for net in data["droplet"]["networks"]["v4"]:
                if net["type"] == "public":
                    return net["ip_address"]
        except Exception:
            pass
        raise ValueError(f"Cannot resolve host for droplet {droplet_id}")

    def create_exec_stream(self, droplet_id):
        """
        Create an interactive SSH channel for terminal access.
        Returns (channel_id, paramiko_channel).
        """
        try:
            host = self._resolve_host(droplet_id)

            # Create a fresh SSH client for the interactive session
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            pkey = self._load_private_key()

            client.connect(
                hostname=host,
                username="root",
                pkey=pkey,
                timeout=30,
                allow_agent=False,
                look_for_keys=False,
            )

            channel = client.invoke_shell(
                term="xterm-256color",
                width=120,
                height=40,
            )
            channel.setblocking(True)

            # Keep client alive
            channel._ssh_client = client

            channel_id = f"do-ssh-{droplet_id}-{int(time.time())}"
            return channel_id, channel

        except Exception as e:
            logger.error(f"Failed to create SSH stream for droplet {droplet_id}: {e}")
            raise

    def run_validation(self, droplet_id, validation_script):
        """Run validation script on the droplet."""
        try:
            exit_code, output = self.execute_command(
                droplet_id, validation_script
            )
            return exit_code == 0, output
        except Exception as e:
            logger.error(f"Validation failed on droplet {droplet_id}: {e}")
            return False, str(e)

    def terminate(self, droplet_id):
        """Destroy the DigitalOcean droplet."""
        try:
            self._api("DELETE", f"/droplets/{droplet_id}")
            logger.info(f"Destroyed DO droplet {droplet_id}")

            # Clean up SSH connections
            for key in list(self._ssh_connections.keys()):
                try:
                    self._ssh_connections[key].close()
                except Exception:
                    pass
            self._ssh_connections.clear()

        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 404:
                logger.warning(f"Droplet {droplet_id} already destroyed")
            else:
                logger.error(f"Failed to destroy droplet {droplet_id}: {e}")

    def get_status(self, droplet_id):
        """Get the current status of a droplet."""
        try:
            data = self._api("GET", f"/droplets/{droplet_id}")
            return data["droplet"]["status"]  # new, active, off, archive
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 404:
                return "destroyed"
            return "unknown"
        except Exception:
            return "unknown"

    def cleanup_expired(self, max_age_seconds=3600):
        """Destroy all FixitLab droplets older than max_age_seconds."""
        try:
            data = self._api("GET", "/droplets?tag_name=fixitlab&per_page=200")
            destroyed = 0

            for droplet in data.get("droplets", []):
                created_at = droplet.get("created_at", "")
                if created_at:
                    from dateutil.parser import parse as parse_date
                    created = parse_date(created_at)
                    age = time.time() - created.timestamp()
                    if age > max_age_seconds:
                        droplet_id = str(droplet["id"])
                        self._api("DELETE", f"/droplets/{droplet_id}")
                        destroyed += 1
                        logger.info(f"Cleaned up expired droplet {droplet_id}")

            return destroyed
        except Exception as e:
            logger.error(f"DO cleanup failed: {e}")
            return 0
