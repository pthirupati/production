"""
Real Docker-based lab provisioner.
Spins up isolated containers with pre-broken scenarios for users to fix.
Each lab session gets its own Docker network for full network isolation.
"""
import logging
import re
import time as _time
import docker
from docker.errors import DockerException, NotFound, APIError
from django.conf import settings

logger = logging.getLogger(__name__)


def _safe_container_username(username: str) -> str:
    """Docker names allow [a-zA-Z0-9][a-zA-Z0-9_.-] only."""
    safe = re.sub(r"[^a-zA-Z0-9_.-]", "-", (username or "user").strip())[:40]
    return safe.strip("-") or "user"


class DockerProvisioner:
    """Manages Docker containers for lab sessions."""

    def __init__(self):
        self.client = docker.DockerClient(base_url=settings.DOCKER_SOCKET)

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

            # Security: privileged only for LVM/device scenarios (e.g. lvm-extend)
            privileged = getattr(lab_session.scenario, "docker_privileged", False)
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
                    cap_add=["NET_BIND_SERVICE", "SYS_PTRACE", "DAC_OVERRIDE"],
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
            if output and output[0]:
                logger.info(f"Setup script output: {output[0].decode('utf-8', errors='replace')}")
        except Exception as e:
            logger.warning(f"Setup script execution failed (non-fatal): {e}")

    def execute_command(self, container_id, command):
        """
        Execute a command inside the container.
        Returns (exit_code, output).
        """
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

    def create_exec_stream(self, container_id):
        """
        Create an interactive exec instance for WebSocket terminal.
        Returns (exec_id, raw_socket) for streaming I/O.
        Docker SDK >=7 changed socket handling — we extract the raw socket.
        """
        try:
            container = self.client.containers.get(container_id)
            exec_instance = self.client.api.exec_create(
                container.id,
                cmd="/bin/bash",
                stdin=True,
                tty=True,
                stderr=True,
                stdout=True,
                environment={"TERM": "xterm-256color", "COLUMNS": "120", "LINES": "40"},
            )
            # IMPORTANT: Do NOT pass stream=True with socket=True.
            # In Docker SDK >=7, combining them breaks stdin writes.
            sock = self.client.api.exec_start(
                exec_instance["Id"],
                detach=False,
                tty=True,
                socket=True,
            )
            # Extract the underlying raw socket for direct read/write.
            # Docker SDK wraps it in SocketIO — we need the real socket.
            raw_socket = self._unwrap_socket(sock)
            raw_socket.setblocking(True)

            return exec_instance["Id"], raw_socket
        except (NotFound, APIError) as e:
            logger.error(f"Failed to create exec stream: {e}")
            raise

    @staticmethod
    def _unwrap_socket(sock):
        """
        Unwrap Docker SDK socket wrappers to get the raw OS socket.
        Works across Docker SDK 6.x, 7.x+.
        """
        # Try ._sock first (Docker SDK 6.x SocketIO wrapper)
        if hasattr(sock, '_sock'):
            raw = sock._sock
            # ._sock itself might be wrapped (urllib3 response socket)
            if hasattr(raw, '_sock'):
                return raw._sock
            return raw
        # Docker SDK 7.x uses a response-based wrapper
        if hasattr(sock, '_response'):
            try:
                fp = sock._response._fp
                if hasattr(fp, 'fp') and hasattr(fp.fp, 'raw'):
                    return fp.fp.raw._sock
                if hasattr(fp, 'raw'):
                    return fp.raw._sock
            except AttributeError:
                pass
        # Fallback: it might already be a raw socket
        if hasattr(sock, 'fileno'):
            return sock
        raise RuntimeError("Cannot unwrap Docker exec socket — unsupported SDK version")

    def run_validation(self, container_id, validation_script):
        """
        Run validation script inside the container.
        Returns (passed: bool, output: str).
        """
        try:
            exit_code, output = self.execute_command(
                container_id, validation_script
            )
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
