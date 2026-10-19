"""Deployment defaults. Research features require an explicit local opt-in."""
import os


def public_cloud_mode():
    value = os.environ.get("PUBLIC_CLOUD_MODE", "true").lower()
    if value not in {"true", "false"}:
        raise ValueError("PUBLIC_CLOUD_MODE must be true or false")
    return value == "true"


def available_modes():
    modes = ["Аналіз URL", "Демонстраційний режим"]
    return modes if public_cloud_mode() else modes + ["Результати дослідження", "Дослідницький режим"]
