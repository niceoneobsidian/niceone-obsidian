"""Privacy contracts."""
from dataclasses import dataclass

@dataclass(frozen=True)
class PrivacyDecision:
    subject: str
    purpose: str
    allowed: bool
