"""
Helpers for Docker exec attach sockets (docker-py 6.x / 7.x).

docker-py attaches the HTTP ``response`` object to the socket as ``_response``
so the connection is not garbage-collected. Unwrapping to an inner socket
without preserving that reference causes the exec stream to drop after ~1–2s.
"""


def prepare_exec_socket(sock):
    """
    Return a socket-like object for blocking send/recv, preserving docker-py refs.
    """
    if sock is None:
        raise RuntimeError("Docker exec returned no socket")

    if hasattr(sock, "recv") and hasattr(sock, "send"):
        _set_blocking(sock)
        return sock

    if hasattr(sock, "_sock") and hasattr(sock._sock, "recv"):
        _set_blocking(sock._sock)
        _copy_response_ref(sock, sock._sock)
        return sock._sock

    inner = _unwrap_inner(sock)
    _set_blocking(inner)
    _copy_response_ref(sock, inner)
    return inner


def exec_send(sock, data: bytes) -> None:
    if hasattr(sock, "send"):
        sock.send(data)
        return
    if hasattr(sock, "write"):
        sock.write(data)
        return
    raise RuntimeError("Exec socket has no send/write method")


def exec_recv(sock, size: int) -> bytes:
    if hasattr(sock, "recv"):
        data = sock.recv(size)
        return data if data else b""
    if hasattr(sock, "read"):
        data = sock.read(size)
        return data if data else b""
    raise RuntimeError("Exec socket has no recv/read method")


def exec_set_timeout(sock, seconds: float) -> None:
    if hasattr(sock, "settimeout"):
        sock.settimeout(seconds)


def exec_close(sock) -> None:
    try:
        if hasattr(sock, "close"):
            sock.close()
    except Exception:
        pass


def _set_blocking(sock) -> None:
    if hasattr(sock, "setblocking"):
        sock.setblocking(True)


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
