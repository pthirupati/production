"""Resolve lab infrastructure / provisioner type from a Scenario row."""


def lab_infra_type(scenario):
    """Resolve provisioner type — handles stale DB rows for simulation-only tech."""
    lab_mode = getattr(scenario, "lab_mode", "docker") or "docker"
    if lab_mode == "simulation":
        return "simulation"
    from apps.labs.provisioner.simulation.sim_types import normalize_sim_type

    sim_type = normalize_sim_type(getattr(scenario, "simulation_type", None))
    if sim_type in ("terraform", "windows"):
        return "simulation"
    if lab_mode in ("aws_ec2", "digitalocean"):
        return lab_mode
    slug = (getattr(scenario, "slug", "") or "").lower()
    if slug.startswith("sim-"):
        return "simulation"
    # Explicit real-cloud infra still provisions for real.
    infra = getattr(scenario, "infrastructure_type", "") or ""
    if infra in ("aws_ec2", "digitalocean"):
        return infra
    # Otherwise fall back to the in-memory simulation engine rather than "docker".
    # Production never bakes per-scenario container images (build_scenarios=false),
    # so a "docker" route dead-ends in DockerProvisioner with "Lab image not built
    # on server" -> PROVISION_FAILED. The simulation engine's "generic" persona is
    # valid for every technology and needs no image, so every scenario stays
    # launchable. (~93 scenarios previously defaulted to docker and always failed.)
    return "simulation"
