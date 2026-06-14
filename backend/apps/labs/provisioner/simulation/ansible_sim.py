"""Ansible control node + full RHEL OS + ansible ad-hoc/playbook commands."""

from __future__ import annotations

from .base_sim import BaseRHELSimulator
from .rhel_shell import RHELShell


class AnsibleSimulator(BaseRHELSimulator):
    def __init__(self, scenario_slug: str = "ansible-ssh-key-failure"):
        super().__init__(scenario_slug=scenario_slug, hostname="ansible-control")
        self.shell.state.set_prompt_user("ansible")
        self._ssh_key_fixed = False

    def _register_extras(self) -> None:
        sim = self

        def ansible_handler(parts: list[str], line: str) -> str | None:
            low = line.strip().lower()
            if low.startswith("ansible ") or low.startswith("ansible-playbook") or low.startswith("ansible-inventory"):
                return sim._ansible_command(line)
            if low.startswith("ssh-copy-id"):
                sim._ssh_key_fixed = True
                return "Number of key(s) added: 1"
            return None

        self.shell.register_handler(ansible_handler)

    def _register_extras_on(self, shell: RHELShell) -> None:
        self._register_extras()

    def _ansible_command(self, line: str) -> str:
        low = line.strip().lower()
        if low in ("ansible --version", "ansible-playbook --version"):
            return "ansible [core 2.15.3]\n  config file = /etc/ansible/ansible.cfg\n  python version = 3.11.6"
        if "ping" in low:
            if self._ssh_key_fixed:
                return (
                    "web1 | SUCCESS => {\n"
                    '    "changed": false,\n'
                    '    "ping": "pong"\n'
                    "}\n"
                    "web2 | SUCCESS => {\n"
                    '    "changed": false,\n'
                    '    "ping": "pong"\n'
                    "}"
                )
            return (
                "web1 | SUCCESS => {\n"
                '    "changed": false,\n'
                '    "ping": "pong"\n'
                "}\n"
                "web2 | UNREACHABLE! => {\n"
                '    "msg": "Failed to connect to the host via ssh: Permission denied (publickey).",\n'
                '    "unreachable": true\n'
                "}"
            )
        if low.startswith("ansible-inventory"):
            return (
                "{\n"
                '  "webservers": {\n'
                '    "hosts": ["web1", "web2"]\n'
                "  },\n"
                '  "_meta": {"hostvars": {"web1": {"ansible_host": "10.0.0.11"}, "web2": {"ansible_host": "10.0.0.12"}}}\n'
                "}"
            )
        if low.startswith("ansible-playbook"):
            if "check" in low or "--check" in low:
                return "PLAY [Fix nginx] *****\nTASK [Ensure nginx running] *****\nchanged: [web1]\nok: [web2]"
            if self._ssh_key_fixed:
                return "PLAY [Fix nginx] *****\nTASK [Ensure nginx running] *****\nchanged: [web1]\nchanged: [web2]\nPLAY RECAP *****\nweb1 : ok=2 changed=1\nweb2 : ok=2 changed=1"
            return "PLAY [Fix nginx] *****\nTASK [Ensure nginx running] *****\nfatal: [web2]: FAILED! => {\"msg\": \"Unable to start service nginx\"}"
        return f"{line}: OK (ansible simulation)"
