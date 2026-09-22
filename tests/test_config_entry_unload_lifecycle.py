"""Regression tests for Home Assistant config-entry unload lifecycle."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INIT = (ROOT / "custom_components/dummy_os_data/__init__.py").read_text()


def test_unload_callbacks_do_not_return_precreated_tasks() -> None:
    """Home Assistant must receive callbacks/coroutines, never an already-created Task."""
    assert "entry.async_on_unload(lambda: hass.async_create_task(" not in INIT
    assert "entry.async_on_unload(source_setup_task.cancel)" not in INIT


def test_async_unload_entry_owns_runtime_and_source_shutdown() -> None:
    """Explicit async unload remains the single owner of runtime cleanup."""
    assert "await runtime.async_shutdown_shadow()" in INIT
    assert "source_setup_task.cancel()" in INIT
    assert "await source_setup_task" in INIT
    assert "await solar.async_shutdown()" in INIT
    assert "await prices.async_shutdown()" in INIT
    assert "await degree_days.async_shutdown()" in INIT
    assert "await coordinator.async_shutdown()" in INIT
