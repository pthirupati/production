"""Audit L1531 — the SSH jump box was the one container path with no fork-bomb cap.

`_provision_ssh_client` builds a third container that the other two provisioning
paths' hardening never covered: it set `mem_limit` and `nano_cpus` but no
`pids_limit` and no capability restrictions. Memory and CPU caps do not stop a
fork bomb — `:(){ :|:& };:` exhausts the *host* pid table long before it touches
the container's memory limit, and every other lab on the box goes with it.

The capability half is the part with a real failure mode, so it is asserted
precisely rather than just "cap_drop is set". The setup script that runs right
after this container starts does `apk add`, `adduser`, and chown/chmod under
/home/labuser. A blanket `cap_drop=["ALL"]` makes those silently half-fail and
the lab hands the user a jump box whose labuser cannot log in anywhere. So the
test pins the specific caps that script depends on.
"""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.labs.provisioner.docker_provisioner import DockerProvisioner


def _run_ssh_client_provision():
    """Drive _provision_ssh_client against a mock daemon, return the run() kwargs.

    __init__ opens a real Docker socket, so the instance is built without it.
    """
    provisioner = object.__new__(DockerProvisioner)
    provisioner.client = mock.MagicMock()

    container = provisioner.client.containers.run.return_value
    container.id = "c" * 64
    # setup_script's last line is the generated public key; a non-zero exit
    # would skip key install, which is not what this test is about.
    container.exec_run.return_value = mock.Mock(
        exit_code=0, output=b"ssh-ed25519 AAAAfake labuser@ssh-client\n"
    )
    container.attrs = {
        "NetworkSettings": {"Networks": {"fixitlab-net": {"IPAddress": "172.30.0.5"}}}
    }

    session_network = mock.Mock()
    session_network.name = "fixitlab-net"

    lab_session = mock.Mock()
    lab_session.id = 4242
    lab_session.user_id = 7
    lab_session.user.username = "learner"
    lab_session.scenario.slug = "ssh-multi-host"

    with mock.patch.object(provisioner, "_cleanup_stale_container"), \
            mock.patch.object(provisioner, "_wait_for_container"):
        result = provisioner._provision_ssh_client(
            lab_session,
            session_network,
            "learner",
            "abc123",
            remote_hosts=[{"name": "web01", "ip": "172.30.0.9", "container_id": "d" * 64}],
        )

    assert result is not None, "provisioning returned None; remote_hosts was non-empty"
    return provisioner.client.containers.run.call_args.kwargs


@override_settings(
    DOCKER_CONTAINER_MEMORY_LIMIT="512m",
    DOCKER_CONTAINER_CPU_LIMIT=1.0,
    SSH_CLIENT_IMAGE="alpine:3.19",
)
class SSHClientContainerLimitsTests(SimpleTestCase):
    def test_pids_limit_is_set(self):
        """Without this the jump box can fork-bomb the host pid table."""
        kwargs = _run_ssh_client_provision()
        self.assertEqual(
            kwargs.get("pids_limit"),
            256,
            "SSH client container must carry the same pids_limit as the other "
            "two provisioning paths",
        )

    def test_capabilities_are_dropped_and_never_privileged(self):
        kwargs = _run_ssh_client_provision()
        self.assertEqual(kwargs.get("cap_drop"), ["ALL"])
        self.assertFalse(kwargs.get("privileged", False))

    def test_setup_script_capabilities_are_retained(self):
        """The caps the post-start setup script actually needs, or labuser breaks."""
        kwargs = _run_ssh_client_provision()
        cap_add = set(kwargs.get("cap_add") or [])
        # apk add -> SETFCAP; adduser -> SETUID/SETGID; chown/chmod -> CHOWN,
        # FOWNER, DAC_OVERRIDE.
        for cap in ("SETFCAP", "SETUID", "SETGID", "CHOWN", "FOWNER", "DAC_OVERRIDE"):
            self.assertIn(cap, cap_add, f"setup script needs {cap}")

    def test_host_control_capabilities_are_not_granted(self):
        """A jump box only runs ssh; it has no reason to hold the big caps."""
        kwargs = _run_ssh_client_provision()
        cap_add = set(kwargs.get("cap_add") or [])
        for cap in ("SYS_ADMIN", "SYS_PTRACE", "NET_ADMIN", "LINUX_IMMUTABLE"):
            self.assertNotIn(cap, cap_add, f"jump box should not hold {cap}")
