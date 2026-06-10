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
import re
import time
import threading
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

from apps.labs.models import LabSession, CommandHistory, SessionRecording
from apps.labs.provisioner import get_provisioner

logger = logging.getLogger(__name__)

# Per-user WebSocket connection tracking (prevents resource exhaustion)
_user_connections = {}  # user_id -> count
_conn_lock = threading.Lock()
MAX_WS_PER_USER = 3  # Max concurrent terminal sessions per user


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lab_session = None
        self.raw_socket = None       # raw OS socket (Docker) or SSH channel (Cloud)
        self.exec_id = None
        self.reader_task = None
        self.provisioner = None
        self.provider_type = "docker"  # docker | aws_ec2 | digitalocean
        # Command history recording
        self._input_buffer = ""
        self._recording_events = []
        self._session_start_time = None
        self._tracked_user_id = None  # For per-user connection counting
        self._blocked_patterns = []
        self._shell_ready = False
        self._resize_pending = None

    async def connect(self):
        user = self.scope.get("user", AnonymousUser())
        session_id = self.scope["url_route"]["kwargs"].get("session_id")

        if not user.is_authenticated:
            await self.close(code=4001)
            return

        # Enforce per-user WebSocket connection limit
        user_id = user.id
        with _conn_lock:
            current = _user_connections.get(user_id, 0)
            if current >= MAX_WS_PER_USER:
                logger.warning(f"User {user_id} exceeded max WS connections ({MAX_WS_PER_USER})")
                await self.close(code=4008)
                return
            _user_connections[user_id] = current + 1
        self._tracked_user_id = user_id

        # Verify session ownership and status
        self.lab_session = await self._get_session(session_id, user)
        if not self.lab_session:
            await self.close(code=4004)
            return

        if self.lab_session.status != "RUNNING":
            await self.close(code=4003)
            return

        # Determine provider and resource ID
        self.provider_type = self.lab_session.provider or "docker"
        resource_id = self._get_resource_id()

        if not resource_id:
            await self.close(code=4005)
            return

        # Load blocked command patterns from scenario
        self._blocked_patterns = await self._load_blocked_patterns()

        await self.accept()

        # Initialize recording
        self._session_start_time = time.time()
        self._recording_events = []

        # For cloud labs, show a connecting message since SSH may take a moment
        is_cloud = self.provider_type != "docker"
        if is_cloud:
            await self.send(text_data=json.dumps({
                "output": (
                    "\r\n\x1b[1;36m  Connecting to cloud server...\x1b[0m\r\n"
                    "\x1b[90m  This may take 15-30 seconds while SSH initializes.\x1b[0m\r\n\r\n"
                )
            }))

        # Create interactive shell (Docker exec or SSH channel) — retry for slow containers
        try:
            self.provisioner = await asyncio.to_thread(
                get_provisioner, self.provider_type
            )

            exec_error = None
            for attempt in range(5):
                try:
                    if is_cloud:
                        ssh_user = self.lab_session.ssh_user or "ec2-user"
                        self.exec_id, self.raw_socket = await asyncio.to_thread(
                            self.provisioner.create_exec_stream,
                            resource_id,
                            ssh_user,
                        )
                    else:
                        self.exec_id, self.raw_socket = await asyncio.to_thread(
                            self.provisioner.create_exec_stream,
                            resource_id,
                        )
                    exec_error = None
                    break
                except Exception as e:
                    exec_error = e
                    if attempt < 4:
                        await asyncio.sleep(1.5 * (attempt + 1))
                    else:
                        raise exec_error

            provider_label = {
                "docker": "Docker Container",
                "aws_ec2": "AWS EC2 Instance",
                "digitalocean": "DigitalOcean Droplet",
            }.get(self.provider_type, "Lab Environment")

            await self.send(text_data=json.dumps({
                "output": (
                    "\r\n\x1b[1;36m╔══════════════════════════════════════╗\x1b[0m\r\n"
                    "\x1b[1;36m║       FixitLab Terminal Ready         ║\x1b[0m\r\n"
                    "\x1b[1;36m╚══════════════════════════════════════╝\x1b[0m\r\n"
                    f"\r\n Scenario: \x1b[1;33m{self.lab_session.scenario.title}\x1b[0m\r\n"
                    f" Environment: \x1b[1;37m{provider_label}\x1b[0m\r\n"
                    f" Time limit: \x1b[1;37m{self.lab_session.duration_limit // 60} minutes\x1b[0m\r\n"
                    " Type your commands below. Good luck!\r\n\r\n"
                )
            }))

            self._shell_ready = True
            if self._resize_pending:
                await self._apply_resize(self._resize_pending)
                self._resize_pending = None

            # Start reading output
            self.reader_task = asyncio.create_task(self._read_output())

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
        """Get the resource ID based on provider type."""
        if self.provider_type == "docker":
            return self.lab_session.container_id
        else:
            # Cloud providers use instance_id
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
            if self.exec_id and self.provisioner:
                try:
                    await asyncio.to_thread(
                        self.provisioner.client.api.exec_resize,
                        self.exec_id,
                        height=rows,
                        width=cols,
                    )
                except Exception:
                    pass
        else:
            try:
                await asyncio.to_thread(
                    self.raw_socket.resize_pty,
                    width=cols,
                    height=rows,
                )
            except Exception:
                pass

    async def _read_output(self):
        """Continuously read output from the exec socket/SSH channel and send to client."""
        empty_reads = 0
        try:
            while True:
                data = await asyncio.to_thread(self.raw_socket.recv, 4096)
                if not data:
                    empty_reads += 1
                    if empty_reads >= 3:
                        break
                    await asyncio.sleep(0.3)
                    continue
                empty_reads = 0
                output = data.decode("utf-8", errors="replace")

                # Record output for replay
                if self._session_start_time:
                    elapsed = time.time() - self._session_start_time
                    self._recording_events.append([elapsed, "o", output])

                await self.send(text_data=json.dumps({"output": output}))
        except asyncio.CancelledError:
            pass
        except (ConnectionResetError, OSError):
            logger.info("Terminal connection reset (container/instance stopped)")
            try:
                await self.send(text_data=json.dumps({
                    "output": "\r\n\x1b[1;33mSession ended\x1b[0m\r\n"
                }))
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Error reading terminal output: {e}")
            try:
                await self.send(text_data=json.dumps({
                    "output": "\r\n\x1b[1;31mConnection lost\x1b[0m\r\n"
                }))
            except Exception:
                pass

    async def disconnect(self, close_code):
        """Cleanup on disconnect and save recording."""
        # Decrement per-user connection count
        user_id = getattr(self, "_tracked_user_id", None)
        if user_id is not None:
            with _conn_lock:
                count = _user_connections.get(user_id, 1)
                if count <= 1:
                    _user_connections.pop(user_id, None)
                else:
                    _user_connections[user_id] = count - 1

        # Save session recording
        if self.lab_session and self._recording_events:
            await self._save_recording()

        if self.reader_task:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass

        if self.raw_socket:
            try:
                # For SSH channels, also close the parent SSH client
                if hasattr(self.raw_socket, '_ssh_client'):
                    self.raw_socket._ssh_client.close()
                self.raw_socket.close()
            except Exception:
                pass

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
            # Limit recording to 5000 events to prevent huge DB entries
            events = self._recording_events[:5000]
            SessionRecording.objects.update_or_create(
                session=self.lab_session,
                defaults={
                    "events": events,
                    "total_duration": duration,
                },
            )
        except Exception as e:
            logger.debug(f"Failed to save recording: {e}")

    @database_sync_to_async
    def _get_session(self, session_id, user):
        try:
            session = LabSession.objects.select_related("scenario").get(
                id=session_id, user=user
            )
            return session
        except LabSession.DoesNotExist:
            return None

