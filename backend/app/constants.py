"""
Single place for TRIBE (Modal) deployment URL loaded from the environment.

The value is set in `backend/.env` as `TRIBE_MODAL_URL` (see `app.config.Settings`).
"""

from app.config import get_settings


def tribe_modal_deployment_url() -> str:
    """Global accessor for the TRIBE `extract_bsv` Modal / HTTPS base URL (no trailing slash)."""
    return get_settings().tribe_modal_url.strip()
