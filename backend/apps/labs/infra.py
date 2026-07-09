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
    return getattr(scenario, "infrastructure_type", "docker") or "docker"
