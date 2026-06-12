"""Tests for Docker exec stream GC fix (Unix socket hosts)."""
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from apps.labs.provisioner.exec_socket import DockerExecSocket, start_exec_stream


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
