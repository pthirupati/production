import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import LabSession
from .provisioner.docker_provisioner import DockerProvisioner

logger = logging.getLogger(__name__)


@receiver(post_save, sender=LabSession)
def handle_lab_status_change(sender, instance, created, **kwargs):
    """Clean up Docker container when session ends. Uses update() to avoid recursive signal."""
    if created:
        return

    if instance.status in ["FAILED", "TERMINATED", "EXPIRED"]:
        if instance.container_id:
            try:
                provisioner = DockerProvisioner()
                provisioner.terminate(instance.container_id, session_id=str(instance.id))
                logger.info(f"Terminated container for session {instance.id}")
            except Exception as e:
                logger.error(f"Failed to terminate container for session {instance.id}: {e}")

