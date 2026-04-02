import uuid
# Common utilities for FixitLab


def generate_uuid() -> str:
    return str(uuid.uuid4())


def minutes_to_seconds(minutes: int) -> int:
    return minutes * 60


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

