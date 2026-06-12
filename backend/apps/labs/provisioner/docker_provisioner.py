"""
Real Docker-based lab provisioner.
Spins up isolated containers with pre-broken scenarios for users to fix.
Each lab session gets its own Docker network for full network isolation.
"""
import io
import logging
import os
import re
import tarfile
import time as _time
import docker
import yaml
from docker.errors import DockerException, NotFound, APIError
from django.conf import settings

from apps.labs.provisioner.exec_stream import open_docker_exec

logger = logging.getLogger(__name__)

# Scenarios that need full privileges (LVM, loop devices, mount, setcap, swapon).
_PRIVILEGED_SLUGS = frozenset({
    "lvm-extend",
    "lvm-add-pv-extend",
    "lvm-pvmove-evacuate",
    "mdadm-degraded-array",
    "xfs-repair-damage",
    "fstab-bad-uuid",
    "fs-readonly-remount",
    "chattr-immutable-config",
    "broken-useradd",
    "swap-disabled",
    "capabilities-ping-fails",
    "static-route-broken",
    "account-locked-faillock",
})


def _safe_container_username(username: str) -> str:
    """Docker names allow [a-zA-Z0-9][a-zA-Z0-9_.-] only."""
    safe = re.sub(r"[^a-zA-Z0-9_.-]", "-", (username or "user").strip())[:40]
    return safe.strip("-") or "user"


class DockerProvisioner:
    """Manages Docker containers for lab sessions."""

    def __init__(self):
        self.client = docker.DockerClient(base_url=settings.DOCKER_SOCKET)

    @staticmethod
    def _scenario_privileged(scenario) -> bool:
        """Resolve privileged flag from DB, scenario YAML, or known slug list."""
        if getattr(scenario, "docker_privileged", False):
            return True
        if scenario.slug in _PRIVILEGED_SLUGS:
            return True
        tech_slug = ""
        if getattr(scenario, "technology", None):
            tech_slug = getattr(scenario.technology, "slug", "") or ""
        if tech_slug and scenario.slug:
            yaml_path = f"/scenarios/{tech_slug}/{scenario.slug}/scenario.yaml"
            if os.path.isfile(yaml_path):
                try:
                    with open(yaml_path, encoding="utf-8") as fh:
                        data = yaml.safe_load(fh) or {}
                    if data.get("docker_privileged"):
                        return True
                except (OSError, yaml.YAMLError):
                    pass
        return False

    def _get_session_network_name(self, session_id):
        """Per-session network name for full isolation."""
        return f"fixitlab_net_{session_id}"

    def _create_session_network(self, session_id):
        """Create an isolated network for a single lab session."""
        net_name = self._get_session_network_name(session_id)
        try:
            return self.client.networks.get(net_name)
        except NotFound:
            net = self.client.networks.create(
                net_name,
                driver="bridge",
                internal=True,  # No external internet access
                labels={
                    "fixitlab.session_id": str(session_id),
                    "fixitlab.type": "lab-network",
                },
            )
            logger.info(f"Created per-session network: {net_name}")
            return net

    def _remove_session_network(self, session_id):
        """Remove the per-session network."""
        net_name = self._get_session_network_name(session_id)
        try:
            network = self.client.networks.get(net_name)
            network.remove()
            logger.info(f"Removed per-session network: {net_name}")
        except NotFound:
            pass
        except APIError as e:
            logger.warning(f"Failed to remove network {net_name}: {e}")

    def _get_image_name(self, scenario):
        """Get the Docker image name for a scenario."""
        return f"{settings.DOCKER_SCENARIO_IMAGE_PREFIX}{scenario.slug}:latest"

    def provision(self, lab_session):
        """
        Spin up a fresh Docker container for the lab session.
        Each session gets its own isolated network — containers from
        different sessions cannot communicate with each other.
        Returns (container_id, container_name) or raises.
        """
        image_name = self._get_image_name(lab_session.scenario)
        # Human-readable name: fixitlab-{username}-{short_id}
        username = _safe_container_username(
            lab_session.user.username if hasattr(lab_session, "user") and lab_session.user else "unknown"
        )
        short_id = str(lab_session.id).split('-')[0]
        container_name = f"fixitlab-{username}-{short_id}"

        try:
            # Pull image if not available locally
            try:
                self.client.images.get(image_name)
            except NotFound:
                logger.info(f"Pulling image {image_name}...")
                self.client.images.pull(image_name)

            # Clean up any zombie containers for same session
            self._cleanup_stale_container(container_name)

            # Create per-session isolated network
            session_network = self._create_session_network(lab_session.id)

            # Security: privileged for LVM/device/network-cap scenarios
            privileged = self._scenario_privileged(lab_session.scenario)
            run_kwargs = dict(
                image=image_name,
                name=container_name,
                detach=True,
                mem_limit=settings.DOCKER_CONTAINER_MEMORY_LIMIT,
                nano_cpus=int(settings.DOCKER_CONTAINER_CPU_LIMIT * 1e9),
                network=session_network.name,
                labels={
                    "fixitlab.session_id": str(lab_session.id),
                    "fixitlab.user_id": str(lab_session.user_id),
                    "fixitlab.scenario": lab_session.scenario.slug,
                    "fixitlab.created": str(int(_time.time())),
                },
                environment={
                    "FIXITLAB_SESSION_ID": str(lab_session.id),
                    "FIXITLAB_SCENARIO": lab_session.scenario.slug,
                },
                read_only=False,
                auto_remove=False,
                pids_limit=256,
                tty=True,
                stdin_open=True,
                network_mode=None,
            )
            if privileged:
                run_kwargs["privileged"] = True
            else:
                run_kwargs.update(
                    cap_drop=["ALL"],
                    cap_add=[
                        "NET_BIND_SERVICE",
                        "NET_ADMIN",
                        "NET_RAW",
                        "SYS_ADMIN",
                        "SYS_PTRACE",
                        "DAC_OVERRIDE",
                        "CHOWN",
                        "FOWNER",
                        "SETUID",
                        "SETGID",
                        "SETFCAP",
                        "LINUX_IMMUTABLE",
                    ],
                    privileged=False,
                )

            container = self.client.containers.run(**run_kwargs)

            # Wait for container to be ready
            self._wait_for_container(container)

            # Run scenario setup script if available (ensures broken state is applied)
            self._run_setup_script(container, lab_session.scenario)

            logger.info(
                f"Provisioned container {container_name} "
                f"(id={container.short_id}) for session {lab_session.id}"
            )

            return container.id, container_name

        except DockerException as e:
            err = str(e)
            if "pull access denied" in err or "not found" in err.lower():
                raise DockerException(
                    f"Lab image not built on server: {image_name}. "
                    f"Ask admin to run ./scripts/build-scenario-images.sh"
                ) from e
            logger.error(f"Failed to provision container: {e}")
            raise

    def _cleanup_stale_container(self, container_name):
        """Remove any existing container with the same name."""
        try:
            existing = self.client.containers.get(container_name)
            existing.stop(timeout=3)
            existing.remove(force=True)
            logger.info(f"Cleaned up stale container: {container_name}")
        except NotFound:
            pass
        except Exception as e:
            logger.warning(f"Error cleaning stale container {container_name}: {e}")

    def _wait_for_container(self, container, timeout=10):
        """Wait until container is running."""
        for _ in range(timeout):
            container.reload()
            if container.status == "running":
                return
            _time.sleep(1)
        logger.warning(f"Container {container.short_id} not running after {timeout}s (status: {container.status})")

    def _run_setup_script(self, container, scenario):
        """
        Run the setup script inside the container to ensure the broken state is applied.
        Looks for /opt/fixitlab/setup.sh inside the container image.
        """
        try:
            exit_code, output = container.exec_run(
                cmd=["/bin/bash", "-c",
                     "if [ -f /opt/fixitlab/setup.sh ]; then bash /opt/fixitlab/setup.sh; fi"],
                user="root",
                demux=True,
            )
            chunks = []
            if output and output[0]:
                chunks.append(output[0].decode("utf-8", errors="replace"))
            if output and output[1]:
                chunks.append(output[1].decode("utf-8", errors="replace"))
            if exit_code != 0:
                chunks.append(f"(setup exit code {exit_code})")
            if chunks:
                logger.info("Setup script output: %s", "".join(chunks).strip())
        except Exception as e:
            logger.warning(f"Setup script execution failed (non-fatal): {e}")

    def execute_script(self, container_id, script_content):
        """
        Run a multi-line bash script by copying it into the container.
        Avoids bash -c parsing errors with newlines, quotes, and semicolons.
        """
        try:
            container = self.client.containers.get(container_id)
            script_bytes = script_content.encode("utf-8")
            tarstream = io.BytesIO()
            with tarfile.open(fileobj=tarstream, mode="w") as tar:
                info = tarfile.TarInfo(name="fixitlab_exec.sh")
                info.size = len(script_bytes)
                info.mode = 0o755
                tar.addfile(info, io.BytesIO(script_bytes))
            tarstream.seek(0)
            container.put_archive("/tmp", tarstream.getvalue())

            exit_code, output = container.exec_run(
                cmd=["/bin/bash", "/tmp/fixitlab_exec.sh"],
                demux=True,
                user="root",
            )
            stdout = output[0].decode("utf-8", errors="replace") if output[0] else ""
            stderr = output[1].decode("utf-8", errors="replace") if output[1] else ""
            return exit_code, stdout + stderr
        except (NotFound, APIError) as e:
            logger.error(f"Failed to execute script in container {container_id}: {e}")
            raise

    def execute_command(self, container_id, command):
        """
        Execute a command inside the container.
        Returns (exit_code, output).
        """
        if "\n" in command:
            return self.execute_script(container_id, command)

        try:
            container = self.client.containers.get(container_id)
            exit_code, output = container.exec_run(
                cmd=["/bin/bash", "-c", command],
                demux=True,
                user="root",
            )
            stdout = output[0].decode("utf-8", errors="replace") if output[0] else ""
            stderr = output[1].decode("utf-8", errors="replace") if output[1] else ""
            return exit_code, stdout + stderr
        except (NotFound, APIError) as e:
            logger.error(f"Failed to execute command in container {container_id}: {e}")
            raise

    def create_exec_stream(self, container_id, session_key: str = ""):
        """
        Create an interactive exec instance for WebSocket terminal.
        Returns (exec_id, ExecStreamHolder) for streaming I/O.

        Uses a detached tmux session so reconnects attach to the same shell.
        """
        try:
            holder = open_docker_exec(
                self.client,
                container_id,
                session_key=session_key,
                ensure_tmux=True,
            )
            return holder.exec_id, holder
        except (NotFound, APIError) as e:
            logger.error(f"Failed to create exec stream for {container_id}: {e}")
            raise

    def run_validation(self, container_id, validation_script):
        """
        Run validation script inside the container.
        Returns (passed: bool, output: str).
        """
        try:
            if "\n" in validation_script:
                exit_code, output = self.execute_script(container_id, validation_script)
            else:
                exit_code, output = self.execute_command(container_id, validation_script)
            return exit_code == 0, output
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return False, str(e)

    def terminate(self, container_id, session_id=None):
        """Stop and remove a container and its per-session network."""
        try:
            container = self.client.containers.get(container_id)
            # Extract session_id from labels if not provided
            if not session_id:
                session_id = container.labels.get("fixitlab.session_id")
            # Release host-visible loop/LVM resources before teardown (privileged labs).
            try:
                container.exec_run(
                    cmd=[
                        "/bin/bash",
                        "-c",
                        "if [ -f /opt/fixitlab/lab-loop.sh ]; then "
                        ". /opt/fixitlab/lab-loop.sh && fixitlab_loop_cleanup; fi; "
                        "losetup -D 2>/dev/null || true",
                    ],
                    user="root",
                )
            except Exception as e:
                logger.debug("Loop cleanup before terminate (non-fatal): %s", e)
            container.stop(timeout=5)
            container.remove(force=True)
            logger.info(f"Terminated container {container_id[:12]}")
        except NotFound:
            logger.warning(f"Container {container_id[:12]} already removed")
        except APIError as e:
            logger.error(f"Failed to terminate container {container_id[:12]}: {e}")

        # Clean up per-session network
        if session_id:
            self._remove_session_network(session_id)

    def get_container_status(self, container_id):
        """Get the current status of a container."""
        return self.get_status(container_id)

    def get_status(self, container_id):
        """Get the current status of a container."""
        try:
            container = self.client.containers.get(container_id)
            return container.status  # running, exited, paused, etc.
        except NotFound:
            return "removed"
        except APIError:
            return "unknown"

    def cleanup_expired(self, max_age_seconds=3600):
        """Remove all containers and their networks older than max_age_seconds."""
        import time
        from dateutil.parser import parse as parse_date

        containers = self.client.containers.list(
            filters={"label": "fixitlab.session_id"},
            all=True,
        )
        cleaned = 0
        for container in containers:
            try:
                created = parse_date(container.attrs["Created"])
                age = time.time() - created.timestamp()
                if age > max_age_seconds:
                    session_id = container.labels.get("fixitlab.session_id")
                    container.stop(timeout=3)
                    container.remove(force=True)
                    if session_id:
                        self._remove_session_network(session_id)
                    cleaned += 1
            except Exception as e:
                logger.error(f"Cleanup error for {container.short_id}: {e}")

        # Also clean up any orphaned lab networks
        self._cleanup_orphaned_networks()

        logger.info(f"Cleaned up {cleaned} expired containers")
        return cleaned

    def _cleanup_orphaned_networks(self):
        """Remove fixitlab lab networks that have no connected containers."""
        try:
            networks = self.client.networks.list(
                filters={"label": "fixitlab.type=lab-network"}
            )
            for net in networks:
                net.reload()
                if not net.attrs.get("Containers"):
                    try:
                        net.remove()
                        logger.info(f"Removed orphaned network: {net.name}")
                    except APIError:
                        pass
        except Exception as e:
            logger.warning(f"Orphaned network cleanup error: {e}")
