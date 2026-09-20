from accountant.ops.storage_budget import StorageBudget, evaluate_storage_budget


def test_storage_budget_allows_work_below_all_limits() -> None:
    decision = evaluate_storage_budget(
        StorageBudget(max_database_gb=14, min_free_disk_gb=25, max_cycle_growth_gb=1),
        database_bytes=10 * 1024**3,
        disk_free_bytes=30 * 1024**3,
        cycle_start_database_bytes=int(9.5 * 1024**3),
        reserved_bytes=128 * 1024**2,
    )

    assert decision.allowed is True
    assert decision.reason is None


def test_storage_budget_blocks_database_cap() -> None:
    decision = evaluate_storage_budget(
        StorageBudget(max_database_gb=14),
        database_bytes=13 * 1024**3,
        disk_free_bytes=40 * 1024**3,
        reserved_bytes=2 * 1024**3,
    )

    assert decision.allowed is False
    assert decision.reason == "database_cap_reached"


def test_storage_budget_blocks_growth_cap() -> None:
    decision = evaluate_storage_budget(
        StorageBudget(max_cycle_growth_gb=1),
        database_bytes=11 * 1024**3,
        disk_free_bytes=40 * 1024**3,
        cycle_start_database_bytes=9 * 1024**3,
    )

    assert decision.allowed is False
    assert decision.reason == "cycle_growth_cap_reached"
