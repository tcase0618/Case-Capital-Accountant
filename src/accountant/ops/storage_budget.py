"""Deterministic storage budget checks for constrained deployments."""

from __future__ import annotations

from dataclasses import dataclass

GIB = 1024**3


@dataclass(frozen=True)
class StorageBudget:
    """Limits that keep the live VPS below its operational storage ceiling."""

    max_database_gb: float = 0.0
    min_free_disk_gb: float = 0.0
    max_cycle_growth_gb: float = 0.0

    @property
    def max_database_bytes(self) -> int | None:
        return _positive_gib_bytes(self.max_database_gb)

    @property
    def min_free_disk_bytes(self) -> int | None:
        return _positive_gib_bytes(self.min_free_disk_gb)

    @property
    def max_cycle_growth_bytes(self) -> int | None:
        return _positive_gib_bytes(self.max_cycle_growth_gb)


@dataclass(frozen=True)
class StorageDecision:
    allowed: bool
    reason: str | None


def evaluate_storage_budget(
    budget: StorageBudget,
    *,
    database_bytes: int,
    disk_free_bytes: int,
    cycle_start_database_bytes: int | None = None,
    reserved_bytes: int = 0,
) -> StorageDecision:
    """Return a conservative decision before beginning another refresh job."""

    projected_database_bytes = database_bytes + max(0, reserved_bytes)
    if (
        budget.max_database_bytes is not None
        and projected_database_bytes > budget.max_database_bytes
    ):
        return StorageDecision(False, "database_cap_reached")

    if (
        budget.min_free_disk_bytes is not None
        and disk_free_bytes - max(0, reserved_bytes) < budget.min_free_disk_bytes
    ):
        return StorageDecision(False, "disk_headroom_below_reserve")

    if (
        cycle_start_database_bytes is not None
        and budget.max_cycle_growth_bytes is not None
        and projected_database_bytes - cycle_start_database_bytes > budget.max_cycle_growth_bytes
    ):
        return StorageDecision(False, "cycle_growth_cap_reached")

    return StorageDecision(True, None)


def _positive_gib_bytes(value: float) -> int | None:
    return int(value * GIB) if value > 0 else None
