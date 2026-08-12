"""In-memory Docker daemon state for terminal `docker` simulation.

Backs the unified shell so `docker ps/images/run/build/stop/rm/logs/exec/inspect/
network/volume/compose` all operate on one mutable object graph instead of canned
strings. State is plain lists/dicts so it round-trips through the session snapshot.

The same object graph also renders the Docker Engine REST API (see
`engine_api_*` below) so labs can teach `curl --unix-socket /var/run/docker.sock`
against the exact schema a real daemon returns.
"""

from __future__ import annotations

import random
import re
from typing import Any

# Engine API version the mock reports; matches the socket paths labs curl.
ENGINE_API_VERSION = "1.43"

# "0.0.0.0:80->80/tcp" / "6379/tcp" — the CLI display form we store internally.
_PORT_MAPPED_RE = re.compile(
    r"^(?:(?P<ip>[\d.:a-fA-F\[\]]+):)?(?P<public>\d+)->(?P<private>\d+)/(?P<proto>\w+)$"
)
_PORT_BARE_RE = re.compile(r"^(?P<private>\d+)/(?P<proto>\w+)$")


def _short_id() -> str:
    return "".join(random.choice("abcdef0123456789") for _ in range(12))


def _uptime_phrase(seconds: int) -> str:
    if seconds < 5:
        return "Less than a second"
    if seconds < 60:
        return f"{seconds} seconds"
    if seconds < 3600:
        n = seconds // 60
        return f"{n} minute{'s' if n != 1 else ''}"
    if seconds < 86400:
        n = seconds // 3600
        return f"{n} hour{'s' if n != 1 else ''}"
    n = seconds // 86400
    return f"{n} day{'s' if n != 1 else ''}"


class DockerState:
    """Mutable docker daemon for the terminal simulation."""

    def __init__(self, scenario_slug: str = "") -> None:
        self.scenario_slug = (scenario_slug or "").lower()
        self.containers: list[dict[str, Any]] = []
        self.images: list[dict[str, Any]] = []
        self.networks: list[dict[str, Any]] = []
        self.volumes: list[dict[str, Any]] = []
        self.daemon_running = True
        self._seed()
        self._apply_scenario()

    # ------------------------------------------------------------------
    # Serialization (snapshot round-trip)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_slug": self.scenario_slug,
            "containers": self.containers,
            "images": self.images,
            "networks": self.networks,
            "volumes": self.volumes,
            "daemon_running": self.daemon_running,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DockerState":
        obj = cls.__new__(cls)
        obj.scenario_slug = data.get("scenario_slug", "")
        obj.containers = data.get("containers", [])
        obj.images = data.get("images", [])
        obj.networks = data.get("networks", [])
        obj.volumes = data.get("volumes", [])
        obj.daemon_running = data.get("daemon_running", True)
        return obj

    # ------------------------------------------------------------------
    # Seeding
    # ------------------------------------------------------------------

    def _container(self, name, image, state="running", exit_code=0, ports="",
                   age=86400, restart_count=0) -> dict[str, Any]:
        return {
            "id": _short_id(),
            "name": name,
            "image": image,
            "state": state,            # running | exited | created
            "exitCode": exit_code,
            "ports": ports,
            "ageSeconds": age,
            "restartCount": restart_count,
            "command": "/docker-entrypoint.sh",
            "network": "bridge",
            "ip": f"172.17.0.{random.randint(2, 250)}" if state == "running" else "",
        }

    def _image(self, repo, tag="latest", size_mb=150, age=172800) -> dict[str, Any]:
        return {"id": _short_id(), "repository": repo, "tag": tag,
                "sizeMb": size_mb, "ageSeconds": age}

    def _seed(self) -> None:
        self.images = [
            self._image("nginx", "latest", 142, 1209600),
            self._image("redis", "7.2-alpine", 43, 604800),
            self._image("postgres", "15", 426, 604800),
            self._image("busybox", "latest", 5, 2592000),
            self._image("alpine", "3.19", 7, 2592000),
        ]
        self.containers = [
            self._container("web", "nginx:latest", state="running",
                            ports="0.0.0.0:80->80/tcp", age=7200),
            self._container("cache", "redis:7.2-alpine", state="running",
                            ports="6379/tcp", age=86400),
        ]
        self.networks = [
            {"id": _short_id(), "name": "bridge", "driver": "bridge", "scope": "local"},
            {"id": _short_id(), "name": "host", "driver": "host", "scope": "local"},
            {"id": _short_id(), "name": "none", "driver": "null", "scope": "local"},
        ]
        self.volumes = [
            {"name": "pgdata", "driver": "local"},
        ]

    def _apply_scenario(self) -> None:
        s = self.scenario_slug
        if "daemon-stopped" in s or "daemon-down" in s:
            self.daemon_running = False
        if "exited" in s or "container-exit" in s or "crash" in s or "stopped" in s:
            for c in self.containers:
                if c["name"] == "web":
                    c["state"] = "exited"
                    c["exitCode"] = 1
                    c["ip"] = ""
                    c["restartCount"] = 3
        if "oom" in s or "memory" in s:
            for c in self.containers:
                if c["name"] == "cache":
                    c["state"] = "exited"
                    c["exitCode"] = 137

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def find_container(self, ref: str) -> dict[str, Any] | None:
        ref = ref.strip()
        for c in self.containers:
            if c["name"] == ref or c["id"].startswith(ref):
                return c
        return None

    def find_image(self, ref: str) -> dict[str, Any] | None:
        if ":" in ref:
            repo, tag = ref.rsplit(":", 1)
        else:
            repo, tag = ref, None
        for img in self.images:
            if img["id"].startswith(ref):
                return img
            if img["repository"] == repo and (tag is None or img["tag"] == tag):
                return img
        return None

    def any_running(self) -> bool:
        return any(c["state"] == "running" for c in self.containers)

    # ------------------------------------------------------------------
    # ps / images / ls
    # ------------------------------------------------------------------

    def ps(self, show_all: bool = False) -> str:
        header = "CONTAINER ID   IMAGE              COMMAND                  STATUS                     PORTS                    NAMES"
        lines = [header]
        for c in self.containers:
            if not show_all and c["state"] != "running":
                continue
            if c["state"] == "running":
                status = f"Up {_uptime_phrase(c['ageSeconds'])}"
            elif c["state"] == "created":
                status = "Created"
            else:
                status = f"Exited ({c['exitCode']}) {_uptime_phrase(c['ageSeconds'])} ago"
            cmd = (c.get("command", "") or "")[:22]
            lines.append(
                f"{c['id']}   {c['image']:<18} \"{cmd:<22}\" {status:<26} {c['ports']:<24} {c['name']}"
            )
        return "\n".join(lines)

    def images_list(self) -> str:
        lines = ["REPOSITORY        TAG          IMAGE ID       CREATED         SIZE"]
        for img in self.images:
            created = _uptime_phrase(img["ageSeconds"]) + " ago"
            lines.append(
                f"{img['repository']:<17} {img['tag']:<12} {img['id']:<14} {created:<15} {img['sizeMb']}MB"
            )
        return "\n".join(lines)

    def network_ls(self) -> str:
        lines = ["NETWORK ID     NAME              DRIVER    SCOPE"]
        for n in self.networks:
            lines.append(f"{n['id'][:12]:<14} {n['name']:<17} {n['driver']:<9} {n['scope']}")
        return "\n".join(lines)

    def volume_ls(self) -> str:
        lines = ["DRIVER    VOLUME NAME"]
        for v in self.volumes:
            lines.append(f"{v['driver']:<9} {v['name']}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def run(self, image: str, name: str = "", detach: bool = False,
            ports: str = "", command: str = "") -> str:
        if not self.find_image(image):
            # pull-on-run
            repo, tag = (image.rsplit(":", 1) + ["latest"])[:2] if ":" not in image else image.rsplit(":", 1)
            self.images.append(self._image(repo, tag, random.randint(20, 400), 5))
        if not name:
            name = f"{image.split(':')[0].split('/')[-1]}-{_short_id()[:6]}"
        if self.find_container(name):
            return (f"docker: Error response from daemon: Conflict. The container name "
                    f"\"/{name}\" is already in use.")
        c = self._container(name, image, state="running", ports=ports, age=1)
        if command:
            c["command"] = command
        self.containers.append(c)
        if detach:
            return c["id"]
        # Foreground run with a command: show a representative line then exit 0.
        if command:
            c["state"] = "exited"
            c["exitCode"] = 0
            return self._foreground_output(command, image)
        return c["id"]

    def _foreground_output(self, command: str, image: str) -> str:
        cl = command.strip().lower()
        if cl.startswith("echo "):
            return command.strip()[5:].strip().strip("'\"")
        if "hello" in image:
            return "Hello from Docker!\nThis message shows that your installation appears to be working correctly."
        if cl in ("ls", "ls -la", "ls -l"):
            return "bin  dev  etc  home  proc  root  sys  tmp  usr  var"
        if cl.startswith("cat /etc/os-release") or "os-release" in cl:
            return "PRETTY_NAME=\"Alpine Linux\""
        return ""

    def start(self, ref: str) -> str:
        c = self.find_container(ref)
        if not c:
            return f"Error response from daemon: No such container: {ref}"
        c["state"] = "running"
        c["exitCode"] = 0
        c["ageSeconds"] = 1
        c["ip"] = f"172.17.0.{random.randint(2, 250)}"
        return c["name"]

    def stop(self, ref: str) -> str:
        c = self.find_container(ref)
        if not c:
            return f"Error response from daemon: No such container: {ref}"
        c["state"] = "exited"
        c["exitCode"] = 0
        c["ip"] = ""
        c["ageSeconds"] = 1
        return c["name"]

    def restart(self, ref: str) -> str:
        c = self.find_container(ref)
        if not c:
            return f"Error response from daemon: No such container: {ref}"
        c["state"] = "running"
        c["exitCode"] = 0
        c["ageSeconds"] = 1
        c["ip"] = f"172.17.0.{random.randint(2, 250)}"
        return c["name"]

    def rm(self, ref: str, force: bool = False) -> str:
        c = self.find_container(ref)
        if not c:
            return f"Error response from daemon: No such container: {ref}"
        if c["state"] == "running" and not force:
            return (f"Error response from daemon: You cannot remove a running container {c['id']}. "
                    f"Stop the container before attempting removal or force remove")
        self.containers = [x for x in self.containers if x["id"] != c["id"]]
        return c["name"]

    def rmi(self, ref: str, force: bool = False) -> str:
        img = self.find_image(ref)
        if not img:
            return f"Error response from daemon: No such image: {ref}"
        in_use = [c["name"] for c in self.containers if c["image"].split(":")[0] == img["repository"]]
        if in_use and not force:
            return (f"Error response from daemon: conflict: unable to remove repository reference "
                    f"\"{ref}\" (must force) - container {in_use[0]} is using its referenced image")
        self.images = [i for i in self.images if i["id"] != img["id"]]
        return f"Untagged: {img['repository']}:{img['tag']}\nDeleted: sha256:{img['id']}"

    def pull(self, image: str) -> str:
        if ":" in image:
            repo, tag = image.rsplit(":", 1)
        else:
            repo, tag = image, "latest"
        if self.find_image(f"{repo}:{tag}"):
            return f"Status: Image is up to date for {repo}:{tag}"
        self.images.append(self._image(repo, tag, random.randint(20, 400), 2))
        return (f"{tag}: Pulling from library/{repo}\n"
                f"Digest: sha256:{_short_id()}{_short_id()}\n"
                f"Status: Downloaded newer image for {repo}:{tag}")

    def build(self, tag: str = "", dockerfile_present: bool = True) -> str:
        if not dockerfile_present:
            return ("unable to prepare context: unable to evaluate symlinks in Dockerfile "
                    "path: no such file or directory")
        repo, t = (tag.rsplit(":", 1) + ["latest"])[:2] if tag and ":" not in tag else (
            tag.rsplit(":", 1) if tag else ("app", "latest"))
        existing = self.find_image(f"{repo}:{t}")
        if not existing:
            self.images.append(self._image(repo, t, random.randint(80, 500), 1))
        return (f"Successfully built {_short_id()}\n"
                f"Successfully tagged {repo}:{t}")

    def logs(self, ref: str) -> str:
        c = self.find_container(ref)
        if not c:
            return f"Error response from daemon: No such container: {ref}"
        if c["state"] == "exited" and c["exitCode"] != 0:
            code = c["exitCode"]
            if code == 137:
                return ("[INFO] cache warming...\n"
                        "fatal: Out of memory (OOM) — killed by cgroup limit")
            return ("[INFO] starting application\n"
                    f"[ERROR] fatal: process exited with code {code}\n"
                    "panic: connection refused")
        return ("[INFO] starting service\n"
                "[INFO] listening on configured port\n"
                "[INFO] ready to accept connections")

    def exec(self, ref: str, command: str) -> str:
        c = self.find_container(ref)
        if not c:
            return f"Error response from daemon: No such container: {ref}"
        if c["state"] != "running":
            return ("Error response from daemon: Container "
                    f"{c['id']} is not running")
        cl = command.strip().lower()
        if not cl or cl in ("sh", "bash", "/bin/sh", "/bin/bash"):
            return f"/ # (interactive shell in {c['name']}; type 'exit' to leave)"
        if cl.startswith("ls"):
            return "bin  dev  etc  home  proc  root  sys  tmp  usr  var"
        if cl.startswith("hostname") or cl.startswith("cat /etc/hostname"):
            return c["id"][:12]
        if cl.startswith("env"):
            return "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\nHOSTNAME=" + c["id"][:12]
        if cl.startswith("whoami") or cl == "id":
            return "root"
        if cl.startswith("ps"):
            return "PID   USER     TIME  COMMAND\n    1 root      0:00 " + c.get("command", "/app")
        return f"(exec in {c['name']}) {command}"

    def inspect(self, ref: str) -> str:
        c = self.find_container(ref)
        if c:
            running = c["state"] == "running"
            return (
                "[\n  {\n"
                f"    \"Id\": \"{c['id']}\",\n"
                f"    \"Name\": \"/{c['name']}\",\n"
                "    \"State\": {\n"
                f"      \"Status\": \"{c['state']}\",\n"
                f"      \"Running\": {str(running).lower()},\n"
                f"      \"ExitCode\": {c['exitCode']}\n"
                "    },\n"
                "    \"Config\": {\n"
                f"      \"Image\": \"{c['image']}\"\n"
                "    },\n"
                "    \"NetworkSettings\": {\n"
                f"      \"IPAddress\": \"{c['ip']}\"\n"
                "    }\n  }\n]"
            )
        img = self.find_image(ref)
        if img:
            return (
                "[\n  {\n"
                f"    \"Id\": \"sha256:{img['id']}\",\n"
                f"    \"RepoTags\": [\"{img['repository']}:{img['tag']}\"],\n"
                f"    \"Size\": {img['sizeMb'] * 1024 * 1024},\n"
                "    \"Architecture\": \"amd64\",\n    \"Os\": \"linux\"\n  }\n]"
            )
        return f"Error: No such object: {ref}"

    def stats(self) -> str:
        lines = ["CONTAINER ID   NAME      CPU %     MEM USAGE / LIMIT     MEM %     NET I/O           PIDS"]
        for c in self.containers:
            if c["state"] != "running":
                continue
            cpu = round(random.uniform(0.1, 12.0), 2)
            mem = random.randint(20, 240)
            lines.append(
                f"{c['id']}   {c['name']:<9} {cpu:<8}% {mem}MiB / 512MiB        "
                f"{round(mem / 512 * 100, 1):<8}% 1.2kB / 0.9kB    {random.randint(1, 20)}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Engine REST API (GET /containers/json, /images/json, ...)
    # ------------------------------------------------------------------

    def _created_epoch(self, age_seconds: int) -> int:
        """Unix `Created` stamp implied by an internal relative age.

        The sim has no wall clock it can trust across snapshot restore, so age
        is anchored to daemon "boot" rather than time.time() — that keeps two
        calls in one session self-consistent, which is what learners diff.
        """
        return max(0, self._epoch_base - int(age_seconds))

    @property
    def _epoch_base(self) -> int:
        # Fixed anchor (2024-01-01T00:00:00Z) so Created never drifts between
        # calls or across a to_dict/from_dict round trip.
        return 1704067200

    def _api_ports(self, ports: str) -> list[dict[str, Any]]:
        """Turn the CLI display string into the API's structured Ports array."""
        out: list[dict[str, Any]] = []
        for chunk in (ports or "").split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            m = _PORT_MAPPED_RE.match(chunk)
            if m:
                out.append({
                    "IP": m.group("ip") or "0.0.0.0",
                    "PrivatePort": int(m.group("private")),
                    "PublicPort": int(m.group("public")),
                    "Type": m.group("proto"),
                })
                continue
            m = _PORT_BARE_RE.match(chunk)
            if m:
                # Exposed but unpublished: no IP/PublicPort, exactly like real docker.
                out.append({
                    "PrivatePort": int(m.group("private")),
                    "Type": m.group("proto"),
                })
        return out

    def _api_status(self, c: dict[str, Any]) -> str:
        if c["state"] == "running":
            return f"Up {_uptime_phrase(c['ageSeconds'])}"
        if c["state"] == "created":
            return "Created"
        return f"Exited ({c['exitCode']}) {_uptime_phrase(c['ageSeconds'])} ago"

    def _api_container(self, c: dict[str, Any]) -> dict[str, Any]:
        net = c.get("network") or "bridge"
        ip = c.get("ip") or ""
        return {
            "Id": c["id"],
            # Real docker always leading-slashes names and returns a list.
            "Names": [f"/{c['name']}"],
            "Image": c["image"],
            "ImageId": f"sha256:{c['id']}",
            "Command": c.get("command", ""),
            "Created": self._created_epoch(c["ageSeconds"]),
            "Ports": self._api_ports(c.get("ports", "")),
            "Labels": {},
            "State": c["state"],
            "Status": self._api_status(c),
            "HostConfig": {"NetworkMode": net},
            "NetworkSettings": {
                "Networks": {
                    net: {
                        "NetworkID": next(
                            (n["id"] for n in self.networks if n["name"] == net), ""
                        ),
                        "IPAddress": ip,
                    }
                }
            },
            "Mounts": [],
        }

    def engine_api_containers(self, show_all: bool = False) -> list[dict[str, Any]]:
        """GET /containers/json — `all=1` includes non-running containers."""
        return [
            self._api_container(c)
            for c in self.containers
            if show_all or c["state"] == "running"
        ]

    def _api_image(self, img: dict[str, Any]) -> dict[str, Any]:
        size_bytes = int(img["sizeMb"]) * 1024 * 1024
        repo_tag = f"{img['repository']}:{img['tag']}"
        return {
            "Id": f"sha256:{img['id']}",
            "ParentId": "",
            "RepoTags": [repo_tag],
            "RepoDigests": [f"{img['repository']}@sha256:{img['id']}"],
            "Created": self._created_epoch(img["ageSeconds"]),
            "Size": size_bytes,
            "VirtualSize": size_bytes,
            "SharedSize": -1,
            "Labels": {},
            # Real docker reports -1 when it hasn't counted referencing containers.
            "Containers": -1,
        }

    def engine_api_images(self) -> list[dict[str, Any]]:
        """GET /images/json."""
        return [self._api_image(i) for i in self.images]

    def engine_api(self, path: str) -> tuple[int, Any]:
        """Route an Engine API path to (status_code, json_body).

        Accepts both bare (`/containers/json`) and versioned
        (`/v1.43/containers/json`) paths, plus an optional query string.
        """
        raw = (path or "").strip()
        if not raw.startswith("/"):
            raw = "/" + raw
        route, _, query = raw.partition("?")
        route = re.sub(r"^/v\d+\.\d+", "", route).rstrip("/") or "/"

        if not self.daemon_running:
            # Matches what a client sees when the socket has no daemon behind it.
            return 503, {"message": "dial unix /var/run/docker.sock: connect: connection refused"}

        params = {}
        for part in query.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = v
        show_all = params.get("all", "").lower() in ("1", "true")

        if route == "/containers/json":
            return 200, self.engine_api_containers(show_all=show_all)
        if route == "/images/json":
            return 200, self.engine_api_images()
        if route in ("/_ping", "/ping"):
            return 200, "OK"
        if route == "/version":
            return 200, {
                "Version": "24.0.7",
                "ApiVersion": ENGINE_API_VERSION,
                "MinAPIVersion": "1.24",
                "Os": "linux",
                "Arch": "amd64",
            }
        if route == "/info":
            return 200, {
                "Containers": len(self.containers),
                "ContainersRunning": sum(
                    1 for c in self.containers if c["state"] == "running"
                ),
                "ContainersStopped": sum(
                    1 for c in self.containers if c["state"] != "running"
                ),
                "Images": len(self.images),
                "ServerVersion": "24.0.7",
            }
        return 404, {"message": f"page not found: {route}"}

    # ------------------------------------------------------------------
    # network / volume create-remove
    # ------------------------------------------------------------------

    def network_create(self, name: str) -> str:
        if any(n["name"] == name for n in self.networks):
            return f"Error response from daemon: network with name {name} already exists"
        nid = _short_id() + _short_id()
        self.networks.append({"id": nid, "name": name, "driver": "bridge", "scope": "local"})
        return nid

    def network_rm(self, name: str) -> str:
        if name in ("bridge", "host", "none"):
            return f"Error response from daemon: {name} is a pre-defined network and cannot be removed"
        if not any(n["name"] == name for n in self.networks):
            return f"Error response from daemon: No such network: {name}"
        self.networks = [n for n in self.networks if n["name"] != name]
        return name

    def network_connect(self, name: str, container: str) -> str:
        c = self.find_container(container)
        if c:
            c["network"] = name
        return ""

    def volume_create(self, name: str) -> str:
        if any(v["name"] == name for v in self.volumes):
            return name
        self.volumes.append({"name": name, "driver": "local"})
        return name

    def volume_rm(self, name: str) -> str:
        if not any(v["name"] == name for v in self.volumes):
            return f"Error response from daemon: no such volume: {name}"
        self.volumes = [v for v in self.volumes if v["name"] != name]
        return name

    # ------------------------------------------------------------------
    # compose
    # ------------------------------------------------------------------

    def compose_up(self) -> str:
        for c in self.containers:
            c["state"] = "running"
            c["exitCode"] = 0
            c["ip"] = c["ip"] or f"172.17.0.{random.randint(2, 250)}"
        return "\n".join(f"Container {c['name']}  Started" for c in self.containers)

    def compose_down(self) -> str:
        out = []
        for c in self.containers:
            if c["state"] == "running":
                c["state"] = "exited"
                c["ip"] = ""
                out.append(f"Container {c['name']}  Stopped")
        return "\n".join(out) or "No containers to stop"

    def compose_ps(self) -> str:
        return self.ps(show_all=True)
