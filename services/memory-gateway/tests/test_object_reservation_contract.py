from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "app" / "entry.py"
API = ROOT / "app" / "object_api.py"
CONFIG = ROOT / "app" / "object_config.py"
RESERVATIONS = ROOT / "app" / "object_reservations.py"


def test_cleanup_task_is_owned_by_gateway_lifespan() -> None:
    entry = ENTRY.read_text(encoding="utf-8")

    assert "ObjectReservationManager(" in entry
    assert "await application.state.object_reservations.initialize()" in entry
    assert "asyncio.create_task(" in entry
    assert 'name="sumeme-object-reservation-cleanup"' in entry
    assert "cleanup_task.cancel()" in entry
    assert "suppress(asyncio.CancelledError)" in entry


def test_completion_and_delete_use_the_same_reservation_manager() -> None:
    api = API.read_text(encoding="utf-8")

    assert "object_reservations.complete(record)" in api
    assert "object_reservations.delete(record)" in api
    assert "object_reservations" in api
    assert "object_store.verify_upload(record)" not in api
    assert "object_store.delete(record)" not in api


def test_cleanup_uses_owned_leases_and_bounded_batches() -> None:
    source = RESERVATIONS.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")

    assert "lease_id TEXT NOT NULL" in source
    assert "WHERE object_id = ? AND lease_id = ?" in source
    assert "BEGIN IMMEDIATE" in source
    assert "LIMIT ?" in source
    assert "object_cleanup_batch_size" in config
    assert "object_reservation_ttl_seconds" in config
    assert "OBJECT_RESERVATION_TTL_SECONDS must be greater" in config
