import logging
from .models import LabSession
from .provisioner import get_provisioner

logger = logging.getLogger(__name__)


def start_lab_session(user, scenario):
    """
    Create a lab session and provision infrastructure.
    Handles Docker, AWS EC2, and DigitalOcean.
    Note: The main StartLabView in public_api handles this directly.
    This is a utility function for programmatic use.
    """
    infra_type = getattr(scenario, "infrastructure_type", "docker") or "docker"

    session = LabSession.objects.create(
        user=user,
        scenario=scenario,
        status="PROVISIONING",
        provider=infra_type,
    )

    try:
        provisioner = get_provisioner(infra_type)
        resource_id, resource_name = provisioner.provision(session)

        if infra_type == "docker":
            session.container_id = resource_id
            session.container_name = resource_name
        else:
            session.instance_id = resource_id

        session.status = "RUNNING"
        session.save()
        logger.info(f"Lab session {session.id} provisioned: {resource_name} ({infra_type})")
    except Exception as e:
        session.status = "FAILED"
        session.save()
        logger.error(f"Failed to provision lab session {session.id}: {e}")
        raise

    return session

