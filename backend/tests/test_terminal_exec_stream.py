"""Tests for Docker exec stream GC fix (Unix socket hosts)."""
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from apps.labs.provisioner.docker_provisioner import _exec_stream_text
from apps.labs.provisioner.exec_socket import (
    DockerExecSocket,
    _coerce_recv_bytes,
    _resolve_exec_write_target,
    start_exec_stream,
    stream_chunk_to_text,
)
from apps.terminal.middleware import _scope_query_string


class CoerceRecvTests(SimpleTestCase):
    def test_tuple_stream_chunks(self):
        self.assertEqual(_coerce_recv_bytes((b"hi", b" there")), b"hi there")

    def test_nested_tuple_stream(self):
        self.assertEqual(_coerce_recv_bytes(((b"a", b"b"), b"c")), b"abc")

    def test_bytes_passthrough(self):
        self.assertEqual(_coerce_recv_bytes(b"ok"), b"ok")

    def test_stream_chunk_to_text_tuple(self):
        self.assertEqual(stream_chunk_to_text((b"root@", b":~$ ")), "root@:~$ ")


class ExecStreamTextTests(SimpleTestCase):
    def test_demux_tuple(self):
        out = (b"stdout", b"stderr")
        self.assertEqual(_exec_stream_text(out, 0), "stdout")
        self.assertEqual(_exec_stream_text(out, 1), "stderr")

    def test_raw_bytes(self):
        self.assertEqual(_exec_stream_text(b"only", 0), "only")


class QueryStringTests(SimpleTestCase):
    def test_bytes(self):
        self.assertEqual(_scope_query_string({"query_string": b"a=1&b=2"}), "a=1&b=2")

    def test_tuple(self):
        self.assertEqual(
            _scope_query_string({"query_string": (b"token=abc",)}),
            "token=abc",
        )


class ResolveExecWriteTests(SimpleTestCase):
    def test_prefers_writable_candidate_without_changing_read_socket(self):
        readable = MagicMock(spec=["recv"])
        readable.recv.return_value = b"root@host:~$ "
        writable = MagicMock(spec=["send"])

        class FakeFp:
            def __init__(self, sock):
                self.raw = FakeRaw(sock)

        class FakeRaw:
            def __init__(self, sock):
                self.sock = sock

        class FakeInnerFp:
            def __init__(self, sock):
                self.fp = FakeFp(sock)

        class FakeRawWrapper:
            def __init__(self, sock):
                self._fp = FakeInnerFp(sock)

        class FakeResponse:
            def __init__(self, sock):
                self.raw = FakeRawWrapper(sock)

        response = FakeResponse(writable)
        write_target = _resolve_exec_write_target(readable, response)
        self.assertIs(write_target, writable)

        wrapped = DockerExecSocket(readable, response)
        wrapped.send(b"echo hi\r")
        writable.send.assert_called_once_with(b"echo hi\r")
        self.assertEqual(wrapped.recv(64), b"root@host:~$ ")

    def test_docker_exec_socket_send_uses_write_fallback(self):
        class WriteOnly:
            def read(self, n):
                return b""

            def write(self, data):
                self.wrote = data

        target = WriteOnly()
        wrapped = DockerExecSocket(target, object())
        wrapped.send(b"hi")
        self.assertEqual(target.wrote, b"hi")


class DockerExecSocketTests(SimpleTestCase):
    def test_wrapper_keeps_response_reference(self):
        class FakeSock:
            def __init__(self):
                self.sent = []

            def send(self, data):
                self.sent.append(data)

            def recv(self, size):
                return b"ok"

            def settimeout(self, seconds):
                pass

            def setblocking(self, flag):
                pass

            def fileno(self):
                return 0

            def close(self):
                pass

        sock = FakeSock()
        response = object()
        wrapped = DockerExecSocket(sock, response)
        self.assertIs(wrapped._response, response)
        wrapped.send(b"hi")
        self.assertEqual(sock.sent, [b"hi"])
        self.assertEqual(wrapped.recv(4), b"ok")
        wrapped.close()

    def test_start_exec_stream_uses_post_json(self):
        api = MagicMock()
        raw_sock = MagicMock()
        raw_sock.recv = MagicMock(return_value=b"")
        raw_sock.send = MagicMock()
        response = MagicMock()
        api._post_json.return_value = response
        api._get_raw_response_socket.return_value = raw_sock

        wrapped = start_exec_stream(api, "exec123")

        api._post_json.assert_called_once()
        api._get_raw_response_socket.assert_called_once_with(response)
        self.assertIsInstance(wrapped, DockerExecSocket)
        self.assertIs(wrapped._response, response)
        self.assertIs(wrapped._sock, raw_sock)
