"""
Real WebSocket terminal consumer.
Connects xterm.js in the browser to either:
  - A Docker exec shell (for Docker-based labs)
  - An SSH shell (for cloud-based labs: AWS EC2, DigitalOcean)

Records command history and terminal I/O for replay.
"""
import json
import asyncio
import logging
import os
import re
import time
from collections import deque
from channels.exceptions import StopConsumer
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from channels.utils import await_many_dispatch
from django.contrib.auth.models import AnonymousUser

from apps.labs.models import LabSession, CommandHistory, SessionRecording
from apps.labs.provisioner import get_provisioner
from apps.labs.provisioner.exec_stream import (
    ExecStreamHolder,
    open_docker_exec,
    release_holder,
)
from apps.labs.provisioner.simulation.shell import SimulationStreamHolder
from apps.labs.provisioner.exec_socket import stream_chunk_to_text

logger = logging.getLogger(__name__)

# Per-user WebSocket connection tracking (prevents resource exhaustion)
MAX_WS_PER_USER = int(os.environ.get("TERMINAL_MAX_WS_PER_USER", "20"))
_WS_CONN_KEY = "ws_conn:{user_id}"
_WS_CONN_TTL = 3700  # slightly over 1 hour; auto-expires stale counts if process crashes

# Learner-facing environment labels — never expose "Simulation".
_LAB_SERVER_LABELS = {
    "aws": "AWS EC2 Lab Server",
    "azure": "Azure Virtual Machine",
    "gcp": "Google Compute Engine VM",
    "openstack": "OpenStack Instance",
    "vmware": "VMware Virtual Machine",
    "kubernetes": "Kubernetes Node",
    "gpu": "GPU Server",
    "windows": "Windows Server",
    "windows-server": "Windows Server",
    "baremetal": "Physical Bare Metal Server",
    "commvault": "Commvault Protected Server",
    "netapp": "NetApp Storage Host",
    "dellemc": "Dell EMC Storage Host",
    "datacenter": "Physical Data Center Host",
    "soc": "SOC Workstation",
    "rhel": "Linux Lab Server (RHEL 9)",
    "linux": "Linux Lab Server (RHEL 9)",
    "generic": "Linux Lab Server (RHEL 9)",
    "terraform": "Terraform Workspace Host",
    "ansible": "Ansible Control Host",
    "ansible-awx": "AWX Control Host",
    "docker": "Docker Host",
    "networking": "Network Lab Appliance",
    "grafana": "Observability Host",
    "prometheus": "Observability Host",
    "peoplesoft": "PeopleSoft App Server",
    "maas": "MAAS Deployed Machine",
}


def _resolve_lab_provider_label(provider_type: str, sim_type: str, tech_slug: str, slug: str) -> str:
    """Pure-string label for the welcome banner (safe to call from sync or async)."""
    cloud = {
        "docker": "Docker Container",
        "aws_ec2": "AWS EC2 Instance",
        "digitalocean": "DigitalOcean Droplet",
    }.get(provider_type)
    if cloud:
        return cloud
    if provider_type != "simulation":
        return "Lab Environment"
    key = sim_type if sim_type in _LAB_SERVER_LABELS else tech_slug
    if key not in _LAB_SERVER_LABELS:
        low = (slug or "").lower()
        if low.startswith(("academy-aws", "aws-", "ec2-")):
            key = "aws"
        elif low.startswith(("academy-azure", "azure-")):
            key = "azure"
        elif low.startswith(("academy-gcp", "gcp-")):
            key = "gcp"
        elif low.startswith(("academy-openstack", "openstack-")):
            key = "openstack"
        elif low.startswith(("academy-vmware", "vmware-", "vm-")):
            key = "vmware"
        elif low.startswith(("academy-gpu", "gpu-", "sim-gpu")):
            key = "gpu"
        elif low.startswith(("academy-baremetal", "baremetal-")):
            key = "baremetal"
        elif low.startswith(("academy-datacenter", "datacenter-", "dc-")):
            key = "datacenter"
        elif low.startswith(("academy-soc", "soc-")):
            key = "soc"
        elif low.startswith(("academy-commvault", "commvault-", "cv-")):
            key = "commvault"
        elif low.startswith(("academy-netapp", "netapp-", "ontap-")):
            key = "netapp"
        elif low.startswith(("academy-dellemc", "dellemc-", "powermax-")):
            key = "dellemc"
    return _LAB_SERVER_LABELS.get(key, "Linux Lab Server (RHEL 9)")


def _resolve_hosting_context(
    *,
    provider_label: str,
    sim_type: str,
    tech_slug: str,
    slug: str,
    cross_technology: bool = False,
    vmware_link: bool = False,
    datacenter_link: bool = False,
) -> str:
    """Where this Lab Server appears in the platform (for the terminal banner)."""
    try:
        from apps.labs.provisioner.simulation.hosting_persona import (
            hosted_as_line,
            resolve_host_platform,
        )
        from apps.labs.provisioner.simulation.sim_types import infer_sim_type

        st = infer_sim_type(sim_type, slug, tech_slug)
        platform = resolve_host_platform(st, slug, tech_slug=tech_slug)
        # Prefer platform-specific Hosted-as (covers Linux labs hosted on VMware/AWS/…)
        line = hosted_as_line(platform)
        if cross_technology or vmware_link:
            if platform == "vmware" or st == "vmware":
                return "Hosted as: VMware Virtual Machine (session-linked guest — same OS as this terminal)"
        if datacenter_link and platform in ("datacenter", "baremetal"):
            return "Hosted as: Physical rack server (session-linked — same host as Data Center Floor)"
        return line
    except Exception:
        pass

    low = (slug or "").lower()
    st = (sim_type or "").strip().lower()
    tech = (tech_slug or "").strip().lower()

    if st == "aws" or tech == "aws" or low.startswith(("academy-aws", "aws-", "ec2-")):
        return "Hosted as: AWS EC2 Instance (same guest as AWS Console)"
    if st == "azure" or tech == "azure" or low.startswith(("academy-azure", "azure-")):
        return "Hosted as: Azure Virtual Machine (same guest as Azure Portal)"
    if st == "gcp" or tech == "gcp" or low.startswith(("academy-gcp", "gcp-")):
        return "Hosted as: Google Compute Engine VM (same guest as GCP Console)"
    if st == "openstack" or tech == "openstack" or low.startswith(("academy-openstack", "openstack-")):
        return "Hosted as: OpenStack Instance (same guest as Horizon)"
    if st == "vmware" or tech == "vmware" or low.startswith(("academy-vmware", "vmware-")):
        return "Hosted as: VMware Virtual Machine (same guest as vCenter)"
    if st == "datacenter" or tech == "datacenter" or low.startswith(("academy-datacenter", "datacenter-", "dc-")):
        return "Hosted as: Physical rack server (same host as Data Center Floor)"
    if st == "baremetal" or tech == "baremetal":
        return "Hosted as: Physical Bare Metal Server"
    if st == "gpu" or tech == "gpu":
        return "Hosted as: GPU Server"
    if st == "windows" or tech in ("windows", "windows-server"):
        return "Hosted as: Windows Server"
    if st == "kubernetes" or tech == "kubernetes":
        return "Hosted as: Kubernetes Node"
    if st == "commvault" or tech == "commvault":
        return "Hosted as: Commvault Protected Server"
    if st == "netapp" or tech == "netapp":
        return "Hosted as: NetApp Storage Host"
    if st == "dellemc" or tech == "dellemc":
        return "Hosted as: Dell EMC Storage Host"
    if st == "soc" or tech == "soc":
        return "Hosted as: SOC Workstation"
    if cross_technology or vmware_link:
        return "Hosted as: VMware Virtual Machine (session-linked guest — same OS as this terminal)"
    if datacenter_link:
        return "Hosted as: Physical rack server (session-linked — same host as Data Center Floor)"
    if provider_label and provider_label != "Lab Environment":
        return f"Hosted as: {provider_label}"
    return "Hosted as: Linux Lab Server (scenario-scoped)"


def reset_user_ws_connections(user_id=None):
    """Clear per-user WS counters (test helper)."""
    from django.core.cache import cache
    if user_id is None:
        # Can't efficiently clear all — used only in tests, acceptable
        pass
    else:
        cache.delete(_WS_CONN_KEY.format(user_id=user_id))


class TerminalConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer that bridges xterm.js to a lab shell.

    Supports two backends:
      - Docker: uses docker exec socket (raw OS socket)
      - Cloud (AWS/DO): uses paramiko SSH channel

    Protocol:
      Client -> Server: {"input": "ls -la\r"}  or  {"resize": {"cols": 120, "rows": 40}}
      Server -> Client: {"output": "...terminal output..."}

    Records:
      - Command history: each line of input is saved as a CommandHistory entry
      - Session recording: all I/O events timestamped for replay
    """

    async def __call__(self, scope, receive, send):
        """
        Run without Redis channel_layer — terminal only uses direct WebSocket I/O.
        Also always release per-user WS slot even if disconnect() never runs.
        """
        self.scope = scope
        self.channel_layer = None
        self.base_send = send
        try:
            await await_many_dispatch([receive], self.dispatch)
        except StopConsumer:
            pass
        finally:
            self._release_connection_slot()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lab_session = None
        self.raw_socket = None       # ExecStreamHolder (Docker) or SSH channel (Cloud)
        self.exec_id = None
        self.reader_task = None
        self.provisioner = None
        self.provider_type = "docker"  # docker | aws_ec2 | digitalocean
        # Command history recording
        self._input_buffer = ""
        self._recording_events = deque(maxlen=5000)
        self._session_start_time = None
        self._tracked_user_id = None  # For per-user connection counting
        self._blocked_patterns = []
        self._shell_ready = False
        self._resize_pending = None
        self._ping_task = None
        self._respawn_in_progress = False
        self._ws_connected = False
        self._sim_stream_key = None

    async def _safe_send(self, text_data: str) -> bool:
        """Send on WebSocket; return False if client already disconnected."""
        if not self._ws_connected:
            return False
        try:
            await self.send(text_data=text_data)
            return True
        except Exception as exc:
            if "closed protocol" in str(exc).lower():
                self._ws_connected = False
            return False

    def _release_connection_slot(self) -> None:
        """Decrement per-user WS counter (safe if called more than once)."""
        user_id = getattr(self, "_tracked_user_id", None)
        if user_id is None:
            return
        self._tracked_user_id = None
        try:
            from django.core.cache import cache
            key = _WS_CONN_KEY.format(user_id=user_id)
            new_val = cache.decr(key, delta=1)
            if new_val <= 0:
                cache.delete(key)
        except Exception:
            pass

    async def connect(self):
        user = self.scope.get("user", AnonymousUser())
        session_id = self.scope["url_route"]["kwargs"].get("session_id")

        if not user.is_authenticated:
            await self.close(code=4001)
            return

        # Enforce per-user WebSocket connection limit
        user_id = user.id
        try:
            from django.core.cache import cache
            key = _WS_CONN_KEY.format(user_id=user_id)
            # Atomic increment; if key didn't exist, set to 1
            try:
                current = cache.incr(key, delta=1)
                cache.expire(key, _WS_CONN_TTL)
            except ValueError:
                # Key doesn't exist — create it
                cache.set(key, 1, timeout=_WS_CONN_TTL)
                current = 1
            if current > MAX_WS_PER_USER:
                cache.decr(key, delta=1)
                logger.warning("User %s exceeded max WS connections (%s)", user_id, MAX_WS_PER_USER)
                await self.close(code=4008)
                return
        except Exception:
            pass
        self._tracked_user_id = user_id

        # Verify session ownership and status
        self.lab_session = await self._get_session(session_id, user)
        if not self.lab_session:
            self._release_connection_slot()
            await self.close(code=4004)
            return

        if self.lab_session.status != "RUNNING":
            self._release_connection_slot()
            await self.close(code=4003)
            return

        from urllib.parse import parse_qs
        qs = parse_qs((self.scope.get("query_string") or b"").decode())
        self._terminal_host = qs.get("host", ["primary"])[0]

        # Determine provider and resource ID
        self.provider_type = self.lab_session.provider or "docker"
        resource_id = self._get_resource_id()

        if not resource_id:
            self._release_connection_slot()
            await self.close(code=4005)
            return

        # Load blocked command patterns from scenario
        self._blocked_patterns = await self._load_blocked_patterns()

        await self.accept()
        self._ws_connected = True

        # Initialize recording
        self._session_start_time = time.time()
        self._recording_events = deque(maxlen=5000)

        # For cloud labs, show a connecting message since SSH may take a moment
        is_cloud = self.provider_type not in ("docker", "simulation")
        if is_cloud:
            await self.send(text_data=json.dumps({
                "output": (
                    "\r\n\x1b[1;36m  Connecting to cloud server...\x1b[0m\r\n"
                    "\x1b[90m  This may take 15-30 seconds while SSH initializes.\x1b[0m\r\n\r\n"
                )
            }))

        # Create interactive shell (Docker exec or SSH channel) — retry for slow containers.
        # All ORM / provisioner work MUST run via database_sync_to_async (not
        # asyncio.to_thread alone): create_exec_stream → ensure_sim_session does
        # LabSession.objects / .save(), and any sync ORM from the async event-loop
        # thread raises SynchronousOnlyOperation → WS 4500.
        try:
            exec_error = None
            for attempt in range(5):
                try:
                    self.exec_id, self.raw_socket = await self._create_exec_stream(resource_id)
                    if isinstance(self.raw_socket, (ExecStreamHolder, SimulationStreamHolder)):
                        await database_sync_to_async(self.raw_socket.set_timeout)(60.0)
                    if isinstance(self.raw_socket, SimulationStreamHolder):
                        self._sim_stream_key = getattr(self.raw_socket, "_stream_key", None)
                    exec_error = None
                    break
                except Exception as e:
                    exec_error = e
                    if attempt < 4:
                        await asyncio.sleep(1.5 * (attempt + 1))
                    else:
                        raise exec_error

            # Welcome banner uses ONLY plain strings prepared in _get_session —
            # never touch scenario/technology FKs from this async method.
            scenario_title = getattr(self, "_welcome_scenario_title", "") or "Lab"
            provider_label = getattr(self, "_welcome_provider_label", None) or "Lab Environment"
            hosting_line = getattr(self, "_welcome_hosting_line", None) or f"Hosted as: {provider_label}"
            duration_limit = getattr(self, "_welcome_duration_limit", None)
            if duration_limit is None:
                duration_limit = getattr(self.lab_session, "duration_limit", 0) or 0

            await self.send(text_data=json.dumps({
                "output": (
                    "\r\n\x1b[1;36m╔══════════════════════════════════════╗\x1b[0m\r\n"
                    "\x1b[1;36m║       FixitLab Terminal Ready         ║\x1b[0m\r\n"
                    "\x1b[1;36m╚══════════════════════════════════════╝\x1b[0m\r\n"
                    f"\r\n Scenario: \x1b[1;33m{scenario_title}\x1b[0m\r\n"
                    f" Environment: \x1b[1;37m{provider_label}\x1b[0m\r\n"
                    f" {hosting_line}\r\n"
                    f" Time limit: \x1b[1;37m{duration_limit // 60} minutes\x1b[0m\r\n"
                    " Type your commands below. Good luck!\r\n\r\n"
                )
            }))

            # Mark shell ready after the welcome banner so clients don't reconnect-loop
            # while waiting for the first exec byte (common on cold Docker attach).
            self._shell_ready = True
            await self._safe_send(json.dumps({"type": "shell_ready"}))

            # Start reading output
            self.reader_task = asyncio.create_task(self._read_output_safe())
            self._ping_task = asyncio.create_task(self._ping_loop())

        except Exception as e:
            logger.error(f"Failed to create exec stream: {e}", exc_info=True)
            error_msg = str(e)
            # Show a friendlier message for SSH banner errors
            if "SSH protocol banner" in error_msg or "banner" in error_msg.lower():
                error_msg = (
                    "Server SSH is still starting up. "
                    "Please wait a moment and refresh the page."
                )
            await self.send(text_data=json.dumps({
                "output": f"\r\n\x1b[1;31mError connecting to lab environment: {error_msg}\x1b[0m\r\n"
            }))
            await self.close(code=4500)

    def _get_resource_id(self):
        """Get the resource ID based on provider type and optional ?host= query."""
        host_key = getattr(self, "_terminal_host", "primary")
        if host_key and host_key != "primary":
            for host in self.lab_session.lab_hosts or []:
                if host.get("name") == host_key and host.get("container_id"):
                    return host["container_id"]
        if self.provider_type == "docker":
            return self.lab_session.container_id
        if self.provider_type == "simulation":
            return self.lab_session.container_id
        return self.lab_session.instance_id

    async def receive(self, text_data=None, bytes_data=None):
        """Handle input from xterm.js — write to raw socket or SSH channel."""
        if not self.raw_socket:
            return

        try:
            data = json.loads(text_data)

            if "input" in data:
                input_bytes = data["input"].encode("utf-8")

                # Build command buffer and check on Enter key
                self._input_buffer += data["input"]
                if "\r" in data["input"] or "\n" in data["input"]:
                    cmd = self._input_buffer.strip()
                    self._input_buffer = ""

                    # Check if command matches any blocked pattern
                    if cmd and self._blocked_patterns:
                        blocked = self._is_command_blocked(cmd)
                        if blocked:
                            # Don't send the Enter to the shell — send warning instead
                            logger.warning(
                                f"Blocked command '{cmd}' in session {self.lab_session.id}"
                            )
                            await self.send(text_data=json.dumps({
                                "output": (
                                    "\r\n\x1b[1;31m⛔ Command blocked: "
                                    f"\x1b[0;33m{blocked}\x1b[1;31m "
                                    "is not allowed in this scenario.\x1b[0m\r\n"
                                ),
                                "blocked": True,
                                "blocked_command": blocked,
                            }))
                            # Send a fresh prompt so the shell isn't left hanging
                            # We eat the Enter keystroke — write nothing to the socket
                            # Instead, send Ctrl+C to cancel and get a new prompt
                            await asyncio.to_thread(
                                self.raw_socket.send, b"\x03"
                            )
                            return

                    if cmd and len(cmd) < 2000 and self.lab_session:
                        await self._save_command(cmd)
                        if self.provider_type == "simulation":
                            from apps.labs.provisioner.simulation.sim_persistence import persist_session_snapshot
                            await asyncio.to_thread(
                                persist_session_snapshot, str(self.lab_session.id)
                            )

                await asyncio.to_thread(self.raw_socket.send, input_bytes)

                # Record input for replay
                if self._session_start_time:
                    elapsed = time.time() - self._session_start_time
                    self._recording_events.append([elapsed, "i", data["input"]])

            elif "resize" in data:
                if not self._shell_ready:
                    self._resize_pending = data["resize"]
                else:
                    await self._apply_resize(data["resize"])

        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.error(f"Error handling terminal input: {e}")

    async def _apply_resize(self, resize_data):
        cols = resize_data.get("cols", 120)
        rows = resize_data.get("rows", 40)
        if self.provider_type == "docker":
            # Docker exec_resize frequently kills the PTY socket (reconnect loop).
            # Initial COLUMNS/LINES are set at exec_create; skip runtime resize for Docker.
            return
        else:
            try:
                await asyncio.to_thread(
                    self.raw_socket.resize_pty,
                    width=cols,
                    height=rows,
                )
            except Exception:
                pass

    async def _ping_loop(self):
        """Keep the Channels websocket alive through proxies."""
        try:
            while self._ws_connected:
                await asyncio.sleep(25)
                if not await self._safe_send(json.dumps({"type": "ping"})):
                    break
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def _open_shell(self, resource_id: str) -> bool:
        """Attach to container/VM shell."""
        self.exec_id, self.raw_socket = await self._create_exec_stream(resource_id)
        if isinstance(self.raw_socket, SimulationStreamHolder):
            self._sim_stream_key = getattr(self.raw_socket, "_stream_key", None)
        return True

    @database_sync_to_async
    def _create_exec_stream(self, resource_id: str):
        """Run provisioner.create_exec_stream off the event loop (ORM-safe)."""
        provisioner = get_provisioner(self.provider_type)
        self.provisioner = provisioner
        if self.provider_type == "simulation":
            host_key = getattr(self, "_terminal_host", "primary")
            return provisioner.create_exec_stream(
                resource_id,
                str(self.lab_session.id),
                host_key,
            )
        if self.provider_type in ("docker",):
            return provisioner.create_exec_stream(
                resource_id,
                str(self.lab_session.id),
            )
        ssh_user = self.lab_session.ssh_user or "ec2-user"
        return provisioner.create_exec_stream(resource_id, ssh_user)

    @database_sync_to_async
    def _get_session(self, session_id, user):
        try:
            session = LabSession.objects.select_related(
                "scenario", "scenario__technology",
            ).get(id=session_id, user=user)
            # Pre-resolve welcome banner strings here so connect() never touches FKs.
            scenario = session.scenario
            sim_type = ""
            tech_slug = ""
            slug = ""
            title = "Lab"
            cross_technology = False
            vmware_link = False
            datacenter_link = False
            if scenario is not None:
                title = scenario.title or title
                sim_type = (getattr(scenario, "simulation_type", None) or "").strip().lower()
                slug = (getattr(scenario, "slug", None) or "").strip().lower()
                cross_technology = bool(getattr(scenario, "cross_technology", False))
                vmware_link = bool(getattr(scenario, "vmware_link", False))
                datacenter_link = bool(getattr(scenario, "datacenter_link", False))
                # Access technology only inside this sync method (select_related).
                tech = None
                if getattr(scenario, "technology_id", None):
                    tech = scenario.technology
                if tech is not None:
                    tech_slug = (tech.slug or "").strip().lower()
            provider_label = _resolve_lab_provider_label(
                session.provider or "docker", sim_type, tech_slug, slug,
            )
            self._welcome_scenario_title = title
            self._welcome_provider_label = provider_label
            self._welcome_hosting_line = _resolve_hosting_context(
                provider_label=provider_label,
                sim_type=sim_type,
                tech_slug=tech_slug,
                slug=slug,
                cross_technology=cross_technology,
                vmware_link=vmware_link,
                datacenter_link=datacenter_link,
            )
            self._welcome_duration_limit = session.duration_limit or 0
            return session
        except LabSession.DoesNotExist:
            return None

    async def _respawn_shell(self, reason: str = "") -> bool:
        """Re-attach to shell without closing the WebSocket (avoids client reconnect loops)."""
        if self._respawn_in_progress or not self.lab_session or not self._ws_connected:
            return False
        self._respawn_in_progress = True
        try:
            resource_id = self._get_resource_id()
            if not resource_id:
                return False

            if isinstance(self.raw_socket, ExecStreamHolder):
                release_holder(str(self.lab_session.id), self.raw_socket)
            elif self.raw_socket:
                try:
                    if hasattr(self.raw_socket, "close"):
                        self.raw_socket.close()
                except Exception:
                    pass
            self.raw_socket = None
            self._shell_ready = False

            if self.provider_type == "simulation":
                from apps.labs.provisioner.simulation_provisioner import evict_sim_stream
                host_key = getattr(self, "_terminal_host", "primary")
                await database_sync_to_async(evict_sim_stream)(
                    str(self.lab_session.id),
                    host_key,
                    self._sim_stream_key,
                )
                self._sim_stream_key = None

            if not await self._safe_send(json.dumps({
                "type": "shell_respawn",
                "output": "\r\n\x1b[1;33mRestoring shell connection...\x1b[0m\r\n",
            })):
                return False

            await self._open_shell(resource_id)
            if isinstance(self.raw_socket, SimulationStreamHolder):
                self._sim_stream_key = getattr(self.raw_socket, "_stream_key", None)
            if isinstance(self.raw_socket, (ExecStreamHolder, SimulationStreamHolder)):
                await database_sync_to_async(self.raw_socket.set_timeout)(60.0)
            self._shell_ready = True
            await self._safe_send(json.dumps({"type": "shell_ready"}))
            return True
        except Exception as exc:
            logger.warning(
                "Shell respawn failed for session %s (%s): %s",
                getattr(self.lab_session, "id", "?"),
                reason,
                exc,
            )
            return False
        finally:
            self._respawn_in_progress = False

    async def _read_output_safe(self):
        """Wrapper so reader failures never propagate to daphne/channels dispatch."""
        try:
            await self._read_output()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error(
                "Terminal reader crashed for session %s: %s",
                getattr(self.lab_session, "id", "?"),
                exc,
                exc_info=True,
            )

    async def _read_output(self):
        """Continuously read output from the exec socket/SSH channel and send to client."""
        empty_reads = 0
        try:
            if isinstance(self.raw_socket, (ExecStreamHolder, SimulationStreamHolder)):
                await asyncio.to_thread(self.raw_socket.set_timeout, 60.0)
            while True:
                if not self._ws_connected:
                    break
                try:
                    if isinstance(self.raw_socket, (ExecStreamHolder, SimulationStreamHolder)):
                        data = await asyncio.to_thread(self.raw_socket.recv, 4096)
                    elif hasattr(self.raw_socket, "recv"):
                        data = await asyncio.to_thread(self.raw_socket.recv, 4096)
                    else:
                        data = await asyncio.to_thread(self.raw_socket.recv, 4096)
                except TimeoutError:
                    continue
                if not data:
                    empty_reads += 1
                    if self.provider_type == "simulation":
                        if empty_reads > 80:
                            logger.info(
                                "Lab stream EOF for session %s — respawning shell",
                                self.lab_session.id,
                            )
                            if not await self._respawn_shell("sim_eof"):
                                await self._safe_send(json.dumps({
                                    "output": "\r\n\x1b[1;31mLab shell unavailable.\x1b[0m\r\n",
                                }))
                                if self._ws_connected:
                                    await self.close(code=4500)
                                break
                            empty_reads = 0
                            if isinstance(self.raw_socket, (ExecStreamHolder, SimulationStreamHolder)):
                                await asyncio.to_thread(self.raw_socket.set_timeout, 60.0)
                            continue
                        await asyncio.sleep(0.3)
                        continue
                    if empty_reads > 30:
                        logger.info(
                            "Exec stream EOF for session %s — respawning shell",
                            self.lab_session.id,
                        )
                        if not await self._respawn_shell("eof"):
                            await self._safe_send(json.dumps({
                                "output": "\r\n\x1b[1;31mLab shell unavailable.\x1b[0m\r\n",
                            }))
                            if self._ws_connected:
                                await self.close(code=4500)
                            break
                        empty_reads = 0
                        if isinstance(self.raw_socket, (ExecStreamHolder, SimulationStreamHolder)):
                            await asyncio.to_thread(self.raw_socket.set_timeout, 60.0)
                        continue
                    await asyncio.sleep(0.2)
                    continue

                empty_reads = 0
                if not self._shell_ready:
                    self._shell_ready = True
                    if self._resize_pending:
                        await self._apply_resize(self._resize_pending)
                        self._resize_pending = None
                    try:
                        await self._safe_send(json.dumps({"type": "shell_ready"}))
                    except Exception:
                        pass

                output = stream_chunk_to_text(data)

                # Record output for replay
                if self._session_start_time:
                    elapsed = time.time() - self._session_start_time
                    self._recording_events.append([elapsed, "o", output])

                if not await self._safe_send(json.dumps({"output": output})):
                    break
        except asyncio.CancelledError:
            pass
        except (ConnectionResetError, OSError) as exc:
            logger.info("Terminal stream reset for session %s: %s", self.lab_session.id, exc)
            if self._ws_connected and not await self._respawn_shell("reset"):
                await self._safe_send(json.dumps({
                    "output": "\r\n\x1b[1;33mSession ended\x1b[0m\r\n"
                }))
        except Exception as e:
            if "closed protocol" in str(e).lower():
                logger.debug(
                    "Terminal client disconnected during read for session %s",
                    getattr(self.lab_session, "id", "?"),
                )
                return
            logger.error(
                "Error reading terminal output for session %s: %s",
                getattr(self.lab_session, "id", "?"),
                e,
                exc_info=True,
            )
            if self._ws_connected and not await self._respawn_shell("error"):
                await self._safe_send(json.dumps({
                    "output": "\r\n\x1b[1;31mConnection lost\x1b[0m\r\n"
                }))

    async def disconnect(self, close_code):
        """Cleanup on disconnect and save recording."""
        self._ws_connected = False
        self._release_connection_slot()
        if self.lab_session and self._recording_events:
            await self._save_recording()

        if self.reader_task:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass

        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass

        if self.lab_session and isinstance(self.raw_socket, ExecStreamHolder):
            release_holder(str(self.lab_session.id), self.raw_socket)
            self.raw_socket = None
        elif self.raw_socket and isinstance(self.raw_socket, SimulationStreamHolder):
            try:
                self.raw_socket.close()
            except Exception:
                pass
            if self.provider_type == "simulation":
                from apps.labs.provisioner.simulation_provisioner import evict_sim_stream
                host_key = getattr(self, "_terminal_host", "primary")
                evict_sim_stream(str(self.lab_session.id), host_key, self._sim_stream_key)
                self._sim_stream_key = None
            self.raw_socket = None
        elif self.raw_socket:
            try:
                if hasattr(self.raw_socket, "_ssh_client"):
                    self.raw_socket._ssh_client.close()
                if hasattr(self.raw_socket, "close"):
                    self.raw_socket.close()
            except Exception:
                pass
            self.raw_socket = None

    @database_sync_to_async
    def _load_blocked_patterns(self):
        """
        Load blocked command patterns from the scenario and compile them.

        Each entry in scenario.blocked_commands can be:
          - A plain string: matched as a substring (case-insensitive)
            e.g. "reboot" blocks any command containing "reboot"
          - A string starting with "^": treated as a regex
            e.g. "^rm\\s+-rf\\s+/" blocks "rm -rf /"

        Returns list of (compiled_regex, display_label) tuples.
        """
        patterns = []
        if not self.lab_session or not self.lab_session.scenario:
            return patterns

        blocked = self.lab_session.scenario.blocked_commands or []
        for entry in blocked:
            if not isinstance(entry, str) or not entry.strip():
                continue
            raw = entry.strip()
            try:
                if raw.startswith("^"):
                    # Regex pattern
                    patterns.append((re.compile(raw, re.IGNORECASE), raw))
                else:
                    # Plain string — match as word boundary or substring
                    # Escape for regex safety, then wrap so it matches the command
                    escaped = re.escape(raw)
                    patterns.append((
                        re.compile(r"(?:^|[;&|]\s*)" + escaped, re.IGNORECASE),
                        raw,
                    ))
            except re.error:
                logger.warning(f"Invalid blocked command pattern: {raw}")
        return patterns

    def _is_command_blocked(self, command):
        """
        Check if a command matches any blocked pattern.
        Handles pipes, semicolons, &&, || by splitting and checking each part.
        Returns the matched pattern label, or None if allowed.
        """
        # Strip ANSI escape codes that xterm might inject
        clean = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", command).strip()
        if not clean:
            return None

        # Split on common shell separators to catch chained commands
        # e.g. "echo hi; reboot" or "true && shutdown -h now"
        parts = re.split(r"\s*(?:;|&&|\|\||\|)\s*", clean)

        for part in parts:
            part = part.strip()
            if not part:
                continue
            for pattern, label in self._blocked_patterns:
                if pattern.search(part):
                    return label
        return None

    @database_sync_to_async
    def _save_command(self, command):
        """Save a command to the history."""
        try:
            CommandHistory.objects.create(
                session=self.lab_session,
                command=command,
            )
        except Exception as e:
            logger.debug(f"Failed to save command: {e}")

    @database_sync_to_async
    def _save_recording(self):
        """Save the session recording for replay."""
        try:
            duration = time.time() - self._session_start_time if self._session_start_time else 0
            # deque is already capped at 5000 events; convert to list for serialization
            events = list(self._recording_events)
            SessionRecording.objects.update_or_create(
                session=self.lab_session,
                defaults={
                    "events": events,
                    "total_duration": duration,
                },
            )
        except Exception as e:
            logger.debug(f"Failed to save recording: {e}")

