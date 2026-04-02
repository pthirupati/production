import logging
from .provisioner import get_provisioner

logger = logging.getLogger(__name__)


def cleanup_lab(session):
    """Terminate a lab session's resource (container or cloud instance) and mark it as terminated."""
    provider = session.provider or "docker"
    resource_id = session.container_id or session.instance_id

    if resource_id:
        try:
            provisioner = get_provisioner(provider)
            provisioner.terminate(resource_id, session_id=str(session.id))
        except Exception as e:
            logger.error(f"Cleanup error for session {session.id}: {e}")

    session.mark_terminated()

