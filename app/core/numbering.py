import secrets
from datetime import UTC, datetime


def generate_number(prefix: str) -> str:
    """Human-readable document number, e.g. PO-20260118-A1B2C3."""
    return f"{prefix}-{datetime.now(UTC):%Y%m%d}-{secrets.token_hex(3).upper()}"
