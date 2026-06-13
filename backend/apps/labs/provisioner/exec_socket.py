"""
Helpers for Docker exec attach sockets (docker-py 6.x / 7.x).

On Linux (Unix socket to Docker), docker-py cannot set sock._response on the raw
socket, so the HTTP response is garbage-collected and the exec stream drops after
~1–2 seconds. DockerExecSocket keeps the response object alive explicitly.
"""


def _coerce_recv_bytes(data) -> bytes:
    """Normalize docker exec socket reads to bytes (some SDK paths return tuples)."""
    if data is None:
        return b""
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    if isinstance(data, str):
        return data.encode("utf-8", errors="replace")
    if isinstance(data, int):
        return b""
    if isinstance(data, (tuple, list)):
        parts = []
        for item in data:
            parts.append(_coerce_recv_bytes(item))
        return b"".join(parts)
    try:
        return bytes(data)
    except TypeError:
        return b""


def stream_chunk_to_text(data) -> str:
    """Decode exec stream chunks without calling .decode() on raw tuples."""
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    return _coerce_recv_bytes(data).decode("utf-8", errors="replace")


class DockerExecSocket:
    """Wraps the raw exec socket and holds the requests Response alive."""

    __slots__ = ("_sock", "_response")

    def __init__(self, sock, response):
        self._sock = sock
        self._response = response

    def send(self, data: bytes) -> None:
        sock = self._sock
        if hasattr(sock, "send"):
            sock.send(data)
            return
        if hasattr(sock, "sendall"):
            sock.sendall(data)
            return
        raise RuntimeError("Exec socket is not writable")

    def recv(self, size: int) -> bytes:
        if hasattr(self._sock, "recv"):
            data = self._sock.recv(size)
            return _coerce_recv_bytes(data)
        if hasattr(self._sock, "read"):
            data = self._sock.read(size)
            return _coerce_recv_bytes(data)
        raise RuntimeError("Exec socket has no recv/read method")

    def settimeout(self, seconds: float) -> None:
        if hasattr(self._sock, "settimeout"):
            self._sock.settimeout(seconds)

    def setblocking(self, flag: bool) -> None:
        if hasattr(self._sock, "setblocking"):
            self._sock.setblocking(flag)

    def fileno(self) -> int:
        return self._sock.fileno()

    def close(self) -> None:
        try:
            self._response.close()
        except Exception:
            pass
        try:
            self._sock.close()
        except Exception:
            pass


def start_exec_stream(api, exec_id: str, *, tty: bool = True) -> DockerExecSocket:
    """Start an exec instance and return a socket that keeps the HTTP response alive."""
    headers = {"Connection": "Upgrade", "Upgrade": "tcp"}
    data = {"Tty": tty, "Detach": False}
    response = api._post_json(
        api._url("/exec/{0}/start", exec_id),
        headers=headers,
        data=data,
        stream=True,
    )
    raw_sock = api._get_raw_response_socket(response)
    wrapped = DockerExecSocket(raw_sock, response)
    wrapped.setblocking(True)
    return wrapped


def exec_send(sock, data: bytes) -> None:
    if isinstance(sock, DockerExecSocket):
        sock.send(data)
        return
    target = _io_target(sock)
    if hasattr(target, "send"):
        target.send(data)
        return
    if hasattr(target, "write"):
        target.write(data)
        return
    raise RuntimeError("Exec socket has no send/write method")


def exec_recv(sock, size: int) -> bytes:
    if isinstance(sock, DockerExecSocket):
        return sock.recv(size)
    target = _io_target(sock)
    if hasattr(target, "recv"):
        return _coerce_recv_bytes(target.recv(size))
    if hasattr(target, "read"):
        return _coerce_recv_bytes(target.read(size))
    raise RuntimeError("Exec socket has no recv/read method")


def exec_set_timeout(sock, seconds: float) -> None:
    if isinstance(sock, DockerExecSocket):
        sock.settimeout(seconds)
        return
    target = _io_target(sock)
    if hasattr(target, "settimeout"):
        target.settimeout(seconds)


def exec_close(sock) -> None:
    try:
        if hasattr(sock, "close"):
            sock.close()
    except Exception:
        pass


def _io_target(sock):
    if isinstance(sock, DockerExecSocket):
        return sock
    if hasattr(sock, "recv") or hasattr(sock, "read"):
        return sock
    if hasattr(sock, "_sock"):
        return sock._sock
    return sock
