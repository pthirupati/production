"""
Helpers for Docker exec attach sockets (docker-py 6.x / 7.x).

On Linux (Unix socket to Docker), docker-py cannot set sock._response on the raw
socket, so the HTTP response is garbage-collected and the exec stream drops after
~1–2 seconds. DockerExecSocket keeps the response object alive explicitly.

The read socket from _get_raw_response_socket is correct for output; stdin often
needs a different object in the docker-py/urllib3 chain (_resolve_exec_write_target).
"""
from __future__ import annotations


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


def _exec_write_candidates(sock, response=None) -> list:
    """Collect docker-py objects that may accept exec stdin."""
    candidates: list = []

    def _add(obj) -> None:
        if obj is not None and obj not in candidates:
            candidates.append(obj)

    _add(sock)
    _add(getattr(sock, "_sock", None))

    resp = response or getattr(sock, "_response", None)
    if resp is not None:
        # Same chain docker-py uses in _get_raw_response_socket (Unix / TCP).
        try:
            fp = resp.raw._fp.fp
            _add(fp)
            raw = getattr(fp, "raw", None)
            _add(raw)
            if raw is not None:
                _add(getattr(raw, "sock", None))
                _add(getattr(raw, "_sock", None))
        except AttributeError:
            pass

        raw = getattr(resp, "raw", None)
        _add(raw)
        if raw is not None:
            _add(getattr(raw, "_fp", None))
            inner = getattr(raw, "_fp", None)
            if inner is not None:
                _add(getattr(inner, "fp", None))
                _add(getattr(inner, "raw", None))
                inner_raw = getattr(inner, "raw", None)
                if inner_raw is not None:
                    _add(getattr(inner_raw, "sock", None))
                    _add(getattr(inner_raw, "_sock", None))

    return candidates


def _resolve_exec_write_target(sock, response=None):
    """Return the best object for writing stdin to a docker exec attach stream."""
    if sock is None:
        raise RuntimeError("Docker exec returned no socket")

    candidates = _exec_write_candidates(sock, response)

    # Prefer real sockets over HTTP/file wrappers (deepest first).
    for candidate in reversed(candidates):
        if hasattr(candidate, "send") or hasattr(candidate, "sendall"):
            _set_blocking(candidate)
            return candidate

    for candidate in reversed(candidates):
        if hasattr(candidate, "write"):
            _set_blocking(candidate)
            return candidate

    return sock


def _set_blocking(sock) -> None:
    if hasattr(sock, "setblocking"):
        try:
            sock.setblocking(True)
        except Exception:
            pass


class DockerExecSocket:
    """Wraps the exec read socket and holds the requests Response alive."""

    __slots__ = ("_sock", "_response", "_write_target")

    def __init__(self, sock, response):
        self._sock = sock
        self._response = response
        self._write_target = _resolve_exec_write_target(sock, response)

    def send(self, data: bytes) -> None:
        for target in (
            self._write_target,
            self._sock,
            getattr(self._sock, "_sock", None),
        ):
            if target is None:
                continue
            if hasattr(target, "send"):
                target.send(data)
                return
            if hasattr(target, "sendall"):
                target.sendall(data)
                return
            if hasattr(target, "write"):
                target.write(data)
                if hasattr(target, "flush"):
                    target.flush()
                return
        raise RuntimeError("Exec socket is not writable")

    def recv(self, size: int) -> bytes:
        if hasattr(self._sock, "recv"):
            return _coerce_recv_bytes(self._sock.recv(size))
        if hasattr(self._sock, "read"):
            return _coerce_recv_bytes(self._sock.read(size))
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
