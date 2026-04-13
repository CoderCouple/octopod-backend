import pytest

from app.service.event_log_service import EventLogService


@pytest.mark.asyncio
async def test_append_and_chain(async_session):
    svc = EventLogService(async_session)
    e1 = await svc.append_event(
        entity_type="org", entity_id="org1", action="create",
        actor_id="actor1", after_state={"name": "Acme"},
    )
    assert e1.sequence_no == 1
    assert e1.prev_hash == "0" * 64

    e2 = await svc.append_event(
        entity_type="org", entity_id="org1", action="update",
        actor_id="actor1", after_state={"name": "Acme Inc"},
    )
    assert e2.sequence_no == 2
    assert e2.prev_hash == e1.event_hash


@pytest.mark.asyncio
async def test_verify_chain_integrity(async_session):
    svc = EventLogService(async_session)
    await svc.append_event(
        entity_type="org", entity_id="org1", action="create",
        actor_id="a", after_state={"x": 1},
    )
    await svc.append_event(
        entity_type="org", entity_id="org1", action="update",
        actor_id="a", after_state={"x": 2},
    )
    valid, error = await svc.verify_chain_integrity()
    assert valid is True
    assert error is None
