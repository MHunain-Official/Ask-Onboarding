"""Expand common workplace shorthand so short forms like EMP / ACK retrieve
the right chunks instead of falling through the no-answer gate."""

import re

# Whole-token replacements only (word boundaries), case-insensitive.
_ABBREVIATIONS: dict[str, str] = {
    "emp": "employee",
    "emps": "employees",
    "mgr": "manager",
    "mgrs": "managers",
    "ack": "acknowledge",
    "acked": "acknowledged",
    "pto": "PTO paid time off",
    "vpn": "VPN",
    "hr": "HR human resources",
    "it": "IT information technology",
    "faq": "FAQ frequently asked questions",
    "sla": "SLA service level agreement",
    "okta": "Okta",
    "sso": "SSO single sign-on",
    "mfa": "MFA multi-factor authentication",
    "2fa": "two-factor authentication",
    "wfh": "work from home remote work",
    "ooo": "out of office",
    "pr": "pull request code review",
}


def expand_abbreviations(question: str) -> str:
    """Return the question with known abbreviations expanded in place.

    The original casing of surrounding words is preserved; only the matched
    token is replaced. Unknown tokens are left untouched.
    """

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        expansion = _ABBREVIATIONS.get(token.lower())
        return expansion if expansion is not None else token

    return re.sub(r"[A-Za-z0-9']+", replace, question)
