"""
Shared configuration reader for Alhazen skill infrastructure.

Reads alhazen.yaml from the project root. Environment variables override
the config file:
  ALHAZEN_MONITORING_ENABLED=true/false
  ALHAZEN_TEXTGRAD_ENABLED=true/false
"""

import os
import sys
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Run: uv add pyyaml", file=sys.stderr)
    sys.exit(1)

# Project root is two levels up from this file (local_resources/skilllog/config.py)
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_FILE = PROJECT_ROOT / "alhazen.yaml"


def _load_raw() -> dict:
    """Load alhazen.yaml, returning empty dict if not found."""
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f) or {}


def is_monitoring_enabled() -> bool:
    """
    Return True if skill usage logging is active.

    Checks ALHAZEN_MONITORING_ENABLED env var first, then alhazen.yaml.
    """
    env_val = os.environ.get("ALHAZEN_MONITORING_ENABLED")
    if env_val is not None:
        return env_val.lower() in ("1", "true", "yes")
    cfg = _load_raw()
    return cfg.get("monitoring", {}).get("enabled", False)


def error_on_typedb_unavailable() -> bool:
    """Return True if the hook should exit non-zero when TypeDB is down."""
    cfg = _load_raw()
    return cfg.get("monitoring", {}).get("error_on_typedb_unavailable", True)


def is_textgrad_enabled() -> bool:
    """
    Return True if TextGrad optimization is permitted.

    Checks ALHAZEN_TEXTGRAD_ENABLED env var first, then alhazen.yaml.
    """
    env_val = os.environ.get("ALHAZEN_TEXTGRAD_ENABLED")
    if env_val is not None:
        return env_val.lower() in ("1", "true", "yes")
    cfg = _load_raw()
    return cfg.get("textgrad", {}).get("enabled", False)


def get_textgrad_backend() -> str:
    """Return the LLM backend identifier for TextGrad optimization."""
    cfg = _load_raw()
    return cfg.get("textgrad", {}).get("backend", "claude-sonnet-4-6")


def get_active_skills() -> Optional[set]:
    """
    Return the set of active skill names, or None meaning 'all skills'.

    Logic:
    - If skills.enabled is present in config: return that set minus skills.disabled
    - If skills.enabled is absent: return None (all skills active) minus skills.disabled
    - skills.disabled is always applied

    Callers treat None as "all skills are active". When a set is returned,
    only those skills are active.
    """
    cfg = _load_raw()
    skills_cfg = cfg.get("skills", {})

    disabled = set(skills_cfg.get("disabled", []) or [])
    enabled_list = skills_cfg.get("enabled")

    if enabled_list is not None:
        # Allowlist mode
        return set(enabled_list) - disabled

    # No allowlist — None means "all skills", caller subtracts disabled separately
    # Return a sentinel-style None; callers should also filter by disabled set
    return None


def get_disabled_skills() -> set:
    """Return the set of explicitly disabled skill names."""
    cfg = _load_raw()
    return set(cfg.get("skills", {}).get("disabled", []) or [])


def is_skill_active(skill_name: str) -> bool:
    """Return True if the given skill name is active per configuration."""
    disabled = get_disabled_skills()
    if skill_name in disabled:
        return False
    active = get_active_skills()
    if active is None:
        return True  # All skills active (no allowlist)
    return skill_name in active
