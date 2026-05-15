from app.core.app_factory import _should_start_scheduler_for_process


def test_scheduler_skips_uvicorn_reload_parent_process() -> None:
    assert _should_start_scheduler_for_process(
        argv=["uvicorn", "app.main:app", "--reload"],
        process_name="MainProcess",
    ) is False


def test_scheduler_runs_in_uvicorn_reload_worker_process() -> None:
    assert _should_start_scheduler_for_process(
        argv=["uvicorn", "app.main:app", "--reload"],
        process_name="SpawnProcess-1",
    ) is True


def test_scheduler_runs_without_reload() -> None:
    assert _should_start_scheduler_for_process(
        argv=["uvicorn", "app.main:app"],
        process_name="MainProcess",
    ) is True
