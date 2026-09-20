"""Deployment authority policy for the research-only Accountant."""

from __future__ import annotations

from dataclasses import dataclass

from accountant.config import Settings

_VALID_MODES = {
    "standalone_research",
    "connected_research",
    "advisory_only",
    "terminal_handoff",
}


@dataclass(frozen=True)
class OperatingModePolicy:
    mode: str
    authority: str
    research_only: bool
    terminal_handoff_allowed: bool
    execution_allowed: bool
    next_mode: str | None
    required_gates: tuple[str, ...]


def build_operating_mode(settings: Settings) -> OperatingModePolicy:
    requested = str(settings.operating_mode or "standalone_research").strip().lower()
    mode = requested if requested in _VALID_MODES else "standalone_research"
    policies = {
        "standalone_research": OperatingModePolicy(
            mode=mode,
            authority="local research and report generation only",
            research_only=True,
            terminal_handoff_allowed=False,
            execution_allowed=False,
            next_mode="connected_research",
            required_gates=(
                "seven consecutive days of unattended operation",
                "zero unexplained pipeline failures",
                "source integrity grade STRONG or WATCH",
            ),
        ),
        "connected_research": OperatingModePolicy(
            mode=mode,
            authority="research packets may be read by the Trading Terminal",
            research_only=True,
            terminal_handoff_allowed=True,
            execution_allowed=False,
            next_mode="advisory_only",
            required_gates=(
                "one week of stable standalone operation",
                "packet schema and ticker identity reconciliation",
                "research and trading-terminal data-source audit",
            ),
        ),
        "advisory_only": OperatingModePolicy(
            mode=mode,
            authority="research packets may advise; no order authority",
            research_only=True,
            terminal_handoff_allowed=True,
            execution_allowed=False,
            next_mode="terminal_handoff",
            required_gates=(
                "one week of connected research with no stale-packet incidents",
                "paper-book attribution reviewed",
                "human approval of risk and veto behavior",
            ),
        ),
        "terminal_handoff": OperatingModePolicy(
            mode=mode,
            authority="research packets participate in terminal workflow",
            research_only=True,
            terminal_handoff_allowed=True,
            execution_allowed=False,
            next_mode=None,
            required_gates=(
                "advisory period completed",
                "source, valuation, and score lineage gates pass",
                "Trading Terminal independently enforces execution risk controls",
            ),
        ),
    }
    return policies[mode]


def operating_mode_payload(settings: Settings) -> dict[str, object]:
    policy = build_operating_mode(settings)
    return {
        "mode": policy.mode,
        "authority": policy.authority,
        "research_only": policy.research_only,
        "terminal_handoff_allowed": policy.terminal_handoff_allowed,
        "execution_allowed": policy.execution_allowed,
        "next_mode": policy.next_mode,
        "required_gates": list(policy.required_gates),
        "policy_version": "ACCOUNTANT_OPERATING_MODE_V1",
    }
