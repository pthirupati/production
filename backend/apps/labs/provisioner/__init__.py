"""
Provisioner factory — returns the right provisioner for a given provider type.

Supported providers:
  - docker: Local Docker containers (default, free, fast)
  - aws_ec2: AWS EC2 instances (full Linux server)
  - digitalocean: DigitalOcean droplets (full Linux server)
"""
import logging
import threading
from .docker_provisioner import DockerProvisioner

logger = logging.getLogger(__name__)

# Thread-safe lazy-load cloud provisioners
_cloud_provisioners = {}
_provisioner_lock = threading.Lock()


def get_provisioner(provider="docker"):
    """
    Factory function — returns the provisioner for the given provider type.
    Thread-safe: uses a lock to prevent duplicate instantiation under
    concurrent Celery workers.

    Args:
        provider: "docker", "aws_ec2", or "digitalocean"

    Returns:
        A provisioner instance with provision(), terminate(), etc.
    """
    if provider == "docker":
        return DockerProvisioner()

    elif provider == "aws_ec2":
        if "aws_ec2" not in _cloud_provisioners:
            with _provisioner_lock:
                if "aws_ec2" not in _cloud_provisioners:  # double-checked locking
                    from .aws_provisioner import EC2Provisioner
                    _cloud_provisioners["aws_ec2"] = EC2Provisioner()
        return _cloud_provisioners["aws_ec2"]

    elif provider == "digitalocean":
        if "digitalocean" not in _cloud_provisioners:
            with _provisioner_lock:
                if "digitalocean" not in _cloud_provisioners:
                    from .do_provisioner import DOProvisioner
                    _cloud_provisioners["digitalocean"] = DOProvisioner()
        return _cloud_provisioners["digitalocean"]

    elif provider == "simulation":
        if "simulation" not in _cloud_provisioners:
            with _provisioner_lock:
                if "simulation" not in _cloud_provisioners:
                    from .simulation_provisioner import SimulationProvisioner
                    _cloud_provisioners["simulation"] = SimulationProvisioner()
        return _cloud_provisioners["simulation"]

    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'docker', 'aws_ec2', 'digitalocean', or 'simulation'.")


def terminate_lab_session(provisioner, session):
    """Terminate all resources for a lab session (primary + companions)."""
    if hasattr(provisioner, "terminate_lab"):
        provisioner.terminate_lab(session)
        return
    resource_id = session.container_id or session.instance_id
    if resource_id:
        provisioner.terminate(resource_id, session_id=str(session.id))


__all__ = ["DockerProvisioner", "get_provisioner", "terminate_lab_session"]
