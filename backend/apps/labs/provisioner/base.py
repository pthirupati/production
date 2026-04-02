"""
Base provisioner interface for all lab infrastructure providers.
All provisioners (Docker, AWS EC2, DigitalOcean) implement this interface.
"""
from abc import ABC, abstractmethod


class BaseProvisioner(ABC):
    """
    Abstract base class for lab provisioners.

    Every provisioner must implement:
      - provision(lab_session) → (resource_id, resource_name)
      - execute_command(resource_id, command) → (exit_code, output)
      - create_exec_stream(resource_id) → (stream_id, raw_socket_or_channel)
      - run_validation(resource_id, validation_script) → (passed, output)
      - terminate(resource_id)
      - get_status(resource_id) → str
    """

    @abstractmethod
    def provision(self, lab_session):
        """
        Provision infrastructure for a lab session.
        Returns (resource_id, resource_name).
        For Docker: (container_id, container_name)
        For AWS: (instance_id, instance_name)
        For DO: (droplet_id, droplet_name)
        """
        raise NotImplementedError

    @abstractmethod
    def execute_command(self, resource_id, command):
        """
        Execute a command on the provisioned resource.
        Returns (exit_code, output_string).
        """
        raise NotImplementedError

    @abstractmethod
    def create_exec_stream(self, resource_id):
        """
        Create an interactive terminal stream.
        Returns (stream_id, raw_io_object).
        For Docker: Docker exec socket
        For Cloud: paramiko SSH channel
        """
        raise NotImplementedError

    @abstractmethod
    def run_validation(self, resource_id, validation_script):
        """
        Run validation script on the resource.
        Returns (passed: bool, output: str).
        """
        raise NotImplementedError

    @abstractmethod
    def terminate(self, resource_id):
        """
        Terminate and clean up the provisioned resource.
        Must be idempotent — safe to call multiple times.
        """
        raise NotImplementedError

    @abstractmethod
    def get_status(self, resource_id):
        """
        Get the current status of the resource.
        Returns a string like 'running', 'stopped', 'terminated', etc.
        """
        raise NotImplementedError

