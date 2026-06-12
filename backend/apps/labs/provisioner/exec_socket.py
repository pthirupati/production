"""
Helpers for Docker exec attach sockets (docker-py 6.x / 7.x).

docker-py attaches the HTTP ``response`` object to the socket as ``_response``
so the connection is not garbage-collected. Unwrapping to an inner socket
without preserving that reference causes the exec stream to drop after ~1–2s.
"""


def prepare_exec_socket(sock):
    """
    Return a socket-like object for blocking send/recv, preserving docker-py refs.
    Prefer the outer docker-py socket wrapper — do not peel to raw HTTP layers.
    """
    if sock is None:
        raise RuntimeError("Docker exec returned no socket")

    if hasattr(sock, "recv") and hasattr(sock, "send"):
        _set_blocking(sock)
        return sock

    if hasattr(sock, "_sock") and hasattr(sock._sock, "recv"):
        inner = sock._sock
        _set_blocking(inner)
        _copy_response_ref(sock, inner)
        _copy_response_ref(sock, sock)
        return sock

    inner = _unwrap_inner(sock)
    _set_blocking(inner)
    _copy_response_ref(sock, inner)
    return inner


def exec_send(sock, data: bytes) -> None:
    target = _io_target(sock)
    if hasattr(target, "send"):
        target.send(data)
        return
    if hasattr(target, "write"):
        target.write(data)
        return
    raise RuntimeError("Exec socket has no send/write method")


def exec_recv(sock, size: int) -> bytes:
    target = _io_target(sock)
    if hasattr(target, "recv"):
        data = target.recv(size)
        return data if data else b""
    if hasattr(target, "read"):
        data = target.read(size)
        return data if data else b""
    raise RuntimeError("Exec socket has no recv/read method")


def exec_set_timeout(sock, seconds: float) -> None:
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
    if hasattr(sock, "recv") or hasattr(sock, "read"):
        return sock
    if hasattr(sock, "_sock"):
        return sock._sock
    return sock


def _set_blocking(sock) -> None:
    target = _io_target(sock)
    if hasattr(target, "setblocking"):
        target.setblocking(True)


def _copy_response_ref(source, target) -> None:
    response = getattr(source, "_response", None)
    if response is None:
        return
    try:
        target._response = response
    except AttributeError:
        pass


def _unwrap_inner(sock):
    if hasattr(sock, "_sock"):
        raw = sock._sock
        if hasattr(raw, "_sock"):
            return raw._sock
        return raw
    if hasattr(sock, "_response"):
        try:
            fp = sock._response._fp
            if hasattr(fp, "fp") and hasattr(fp.fp, "raw"):
                inner = fp.fp.raw
                return inner._sock if hasattr(inner, "_sock") else inner
            if hasattr(fp, "raw"):
                inner = fp.raw
                return inner._sock if hasattr(inner, "_sock") else inner
        except AttributeError:
            pass
    if hasattr(sock, "fileno"):
        return sock
    raise RuntimeError("Cannot unwrap Docker exec socket — unsupported SDK version")
