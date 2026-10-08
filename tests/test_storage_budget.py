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


def test_storage_gate_rechecks_growth_between_parallel_jobs(test_engine, tmp_path, monkeypatch):
    import threading

    from accountant.ops.storage_gate import StorageGate

    size = [0]
    monkeypatch.setattr(StorageGate, "_database_size", lambda self: size[0])
    gate = StorageGate(
        engine=test_engine, data_dir=tmp_path,
        budget=StorageBudget(max_cycle_growth_gb=0.25), reserve_mb=128,
    )
    started = []

    def job():
        if gate.claim():
            try:
                started.append(True)
                size[0] += 200 * 1024**2
            finally:
                gate.release()

    threads = [threading.Thread(target=job) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(started) == 1
    assert gate.stop_reason == "cycle_growth_cap_reached"


def test_storage_gate_refuses_one_byte_headroom(test_engine, tmp_path, monkeypatch):
    from accountant.ops.storage_gate import StorageGate

    monkeypatch.setattr(StorageGate, "_database_size", lambda self: 100)
    gate = StorageGate(engine=test_engine, data_dir=tmp_path,
                       budget=StorageBudget(max_database_gb=101 / 1024**3), reserve_mb=128)
    assert not gate.claim()
    assert gate.stop_reason == "database_cap_reached"


def test_storage_gate_releases_postgres_advisory_lock(tmp_path, monkeypatch):
    from unittest.mock import Mock

    from accountant.ops.storage_gate import StorageGate

    engine = Mock()
    engine.dialect.name = "postgresql"
    engine.url = "postgresql://offline-test"
    connection = engine.connect.return_value.execution_options.return_value
    monkeypatch.setattr(StorageGate, "_database_size", lambda self: 0)
    gate = StorageGate(engine=engine, data_dir=tmp_path,
                       budget=StorageBudget(max_database_gb=1), reserve_mb=128)
    assert gate.claim()
    gate.release()
    queries = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert queries == ["SELECT pg_advisory_lock(:key)", "SELECT pg_advisory_unlock(:key)"]
    connection.close.assert_called_once()
