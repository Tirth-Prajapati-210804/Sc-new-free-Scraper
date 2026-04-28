from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.models.route_group import RouteGroup
from app.schemas.route_group import RouteGroupUpdate
from app.services import route_group_service


@pytest.mark.asyncio
async def test_update_clears_collection_data_when_route_identity_changes() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    group_id = uuid.uuid4()
    group = RouteGroup(
        id=group_id,
        name="Canada to Vietnam",
        destination_label="Vietnam",
        destinations=["SGN", "HAN"],
        origins=["YVR", "YYZ"],
        nights=10,
        days_ahead=90,
        sheet_name_map={"YVR": "Canada", "YYZ": "Canada"},
        special_sheets=[],
        is_active=True,
        currency="USD",
        max_stops=1,
        start_date=None,
        end_date=None,
        trip_type="one_way",
        user_id=None,
    )

    with patch.object(route_group_service, "get_by_id", AsyncMock(return_value=group)):
        with patch.object(
            route_group_service,
            "_clear_group_collection_data",
            AsyncMock(),
        ) as clear_mock:
            updated = await route_group_service.update(
                session=session,
                group_id=group_id,
                data=RouteGroupUpdate(destinations=["NRT"]),
            )

    assert updated is group
    assert group.destinations == ["NRT"]
    clear_mock.assert_awaited_once_with(session, group_id)
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(group)


@pytest.mark.asyncio
async def test_update_keeps_collection_data_when_identity_is_unchanged() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    group_id = uuid.uuid4()
    group = RouteGroup(
        id=group_id,
        name="Canada to Vietnam",
        destination_label="Vietnam",
        destinations=["SGN", "HAN"],
        origins=["YVR", "YYZ"],
        nights=10,
        days_ahead=90,
        sheet_name_map={"YVR": "Canada", "YYZ": "Canada"},
        special_sheets=[],
        is_active=True,
        currency="USD",
        max_stops=1,
        start_date=None,
        end_date=None,
        trip_type="one_way",
        user_id=None,
    )

    with patch.object(route_group_service, "get_by_id", AsyncMock(return_value=group)):
        with patch.object(
            route_group_service,
            "_clear_group_collection_data",
            AsyncMock(),
        ) as clear_mock:
            updated = await route_group_service.update(
                session=session,
                group_id=group_id,
                data=RouteGroupUpdate(name="Updated Name"),
            )

    assert updated is group
    assert group.name == "Updated Name"
    clear_mock.assert_not_awaited()
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(group)
