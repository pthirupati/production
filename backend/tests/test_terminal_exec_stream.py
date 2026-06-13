"""Tests for Docker exec stream GC fix (Unix socket hosts)."""
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from apps.labs.provisioner.docker_provisioner import _exec_stream_text
from apps.labs.provisioner.exec_socket import (
    DockerExecSocket,
    _coerce_recv_bytes,
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


class DockerExecSocketTests(SimpleTestCase):
    def test_wrapper_keeps_response_reference(self):
        sock = MagicMock()
        response = MagicMock()
        wrapped = DockerExecSocket(sock, response)
        self.assertIs(wrapped._response, response)
        wrapped.send(b"hi")
        sock.send.assert_called_once_with(b"hi")
        sock.recv.return_value = b"ok"
        self.assertEqual(wrapped.recv(4), b"ok")
        wrapped.close()
        response.close.assert_called_once()
        sock.close.assert_called_once()

    def test_start_exec_stream_uses_post_json(self):
        api = MagicMock()
        raw_sock = MagicMock()
        response = MagicMock()
        api._post_json.return_value = response
        api._get_raw_response_socket.return_value = raw_sock

        wrapped = start_exec_stream(api, "exec123")

        api._post_json.assert_called_once()
        api._get_raw_response_socket.assert_called_once_with(response)
        self.assertIsInstance(wrapped, DockerExecSocket)
        self.assertIs(wrapped._response, response)
