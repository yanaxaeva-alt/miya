"""Layer 8 — Constitutional Core."""

import re

from aeon.config import ConstitutionConfig
from aeon.types import AeonRequest, ConstitutionalTier, ConstitutionalVerdict


class ConstitutionalCore:
    """Reason-based constitutional gate with hard Tier 0 rules."""

    _TIER_0_PATTERNS = (
        (re.compile(r"(?i)\b(kill|murder|harm)\b.*\b(people|person|human)\b"), "harm to people"),
        (re.compile(r"(?i)bypass.*(governance|guard|kill\s*switch|constitution)"), "governance bypass"),
        (re.compile(r"(?i)pretend.*(human|real person)"), "deception about system nature"),
    )
    _TIER_1_PATTERNS = (
        (re.compile(r"(?i)ignore (your )?(values|persona|identity)"), "identity override"),
        (re.compile(r"(?i)unsafe but useful"), "utility over safety"),
    )
    _TIER_2_SIDE_EFFECTS = (
        "delete file",
        "publish",
        "send email",
        "transfer money",
        "shell command",
        "rm -rf",
        "curl ",
        "wget ",
    )

    def __init__(self, config: ConstitutionConfig) -> None:
        self.config = config

    def ratify_request(self, request: AeonRequest) -> ConstitutionalVerdict:
        for pattern, label in self._TIER_0_PATTERNS:
            if pattern.search(request.message):
                return ConstitutionalVerdict(
                    allowed=False,
                    tier=ConstitutionalTier.TIER_0,
                    reason=f"Blocked by Tier 0 rule: {label}",
                    requires_human=False,
                )

        for pattern, label in self._TIER_1_PATTERNS:
            if pattern.search(request.message):
                return ConstitutionalVerdict(
                    allowed=False,
                    tier=ConstitutionalTier.TIER_1,
                    reason=f"Blocked by Tier 1 rule: {label}",
                    requires_human=False,
                )

        if self._needs_human_checkpoint(request.message):
            return ConstitutionalVerdict(
                allowed=True,
                tier=ConstitutionalTier.TIER_2,
                reason="Allowed with human checkpoint for sensitive side effects.",
                requires_human=True,
            )

        return ConstitutionalVerdict(
            allowed=True,
            tier=ConstitutionalTier.TIER_1,
            reason="Request passes default constitutional values.",
            requires_human=False,
        )

    def ratify_response(self, response_text: str) -> ConstitutionalVerdict:
        for pattern, label in self._TIER_0_PATTERNS:
            if pattern.search(response_text):
                return ConstitutionalVerdict(
                    allowed=False,
                    tier=ConstitutionalTier.TIER_0,
                    reason=f"Response blocked by Tier 0 rule: {label}",
                )

        if len(response_text) > 4000:
            return ConstitutionalVerdict(
                allowed=False,
                tier=ConstitutionalTier.TIER_3,
                reason="Response exceeds Tier 3 verbosity limit.",
            )

        return ConstitutionalVerdict(
            allowed=True,
            tier=ConstitutionalTier.TIER_3,
            reason="Response passes constitutional review.",
        )

    @staticmethod
    def _needs_human_checkpoint(message: str) -> bool:
        lowered = message.casefold()
        return any(token in lowered for token in ConstitutionalCore._TIER_2_SIDE_EFFECTS)
