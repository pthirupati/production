import json
from pathlib import Path

BASE_SCENARIO_PATH = Path(__file__).resolve().parent / "data"

def load_scenario_definition(definition_path: str) -> dict:
    """
    Load scenario definition JSON/YAML.
    For now JSON only (safe & simple).
    """
    file_path = BASE_SCENARIO_PATH / definition_path

    if not file_path.exists():
        raise FileNotFoundError(f"Scenario definition not found: {file_path}")

    if file_path.suffix == ".json":
        with open(file_path) as f:
            return json.load(f)

    raise ValueError("Unsupported scenario format")

