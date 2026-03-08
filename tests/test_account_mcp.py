import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_httpx_response():
    def _make(json_data, status_code=200):
        response = MagicMock()
        response.json.return_value = json_data
        response.status_code = status_code
        response.raise_for_status = MagicMock()
        if status_code >= 400:
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "error", request=MagicMock(), response=response
            )
        return response

    return _make


@pytest.fixture
def mock_client():
    with patch("src.chat_service.account_tools.httpx.AsyncClient") as mock_client_class:
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = client
        yield client


@pytest.mark.asyncio
async def test_get_all_companies_success(mock_httpx_response, mock_client):
    expected = {"cmpDetails": [{"cmpCode": "001", "name": "Test Co"}]}
    mock_client.get = AsyncMock(return_value=mock_httpx_response(expected))

    from src.chat_service.account_tools import get_all_companies

    result = await get_all_companies.ainvoke({"access_token": "test-token", "tenant_id": 1})
    assert result == expected
    mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_all_companies_error(mock_httpx_response, mock_client):
    mock_client.get = AsyncMock(return_value=mock_httpx_response({}, status_code=401))

    from src.chat_service.account_tools import get_all_companies

    with pytest.raises(httpx.HTTPStatusError):
        await get_all_companies.ainvoke({"access_token": "bad-token", "tenant_id": 1})


@pytest.mark.asyncio
async def test_search_materials_success(mock_httpx_response, mock_client):
    expected = {"itemList": [{"cmp": "001", "item": "SKU-001"}]}
    mock_client.put = AsyncMock(return_value=mock_httpx_response(expected))

    from src.chat_service.account_tools import search_materials

    result = await search_materials.ainvoke({"access_token": "test-token", "tenant_id": 1, "cmp": "001", "loc": ["LOC1"]})
    assert result == expected
    mock_client.put.assert_called_once()


@pytest.mark.asyncio
async def test_search_materials_error(mock_httpx_response, mock_client):
    mock_client.put = AsyncMock(return_value=mock_httpx_response({}, status_code=500))

    from src.chat_service.account_tools import search_materials

    with pytest.raises(httpx.HTTPStatusError):
        await search_materials.ainvoke({"access_token": "test-token", "tenant_id": 1, "cmp": "001", "loc": ["LOC1"]})


@pytest.mark.asyncio
async def test_get_item_details_success(mock_httpx_response, mock_client):
    expected = {"itemDetails": {"item": "SKU-001", "description": "Test Item"}}
    mock_client.put = AsyncMock(return_value=mock_httpx_response(expected))

    from src.chat_service.account_tools import get_item_details

    result = await get_item_details.ainvoke({"access_token": "test-token", "tenant_id": 1, "cmp": "001", "item": "SKU-001", "locations": ["LOC1"]})
    assert result == expected


@pytest.mark.asyncio
async def test_get_item_details_error(mock_httpx_response, mock_client):
    mock_client.put = AsyncMock(return_value=mock_httpx_response({}, status_code=404))

    from src.chat_service.account_tools import get_item_details

    with pytest.raises(httpx.HTTPStatusError):
        await get_item_details.ainvoke({"access_token": "test-token", "tenant_id": 1, "cmp": "001", "item": "SKU-001", "locations": ["LOC1"]})


@pytest.mark.asyncio
async def test_get_allocation_history_success(mock_httpx_response, mock_client):
    expected = {"history": [{"date": "01/15/2024", "qty": 10}]}
    mock_client.get = AsyncMock(return_value=mock_httpx_response(expected))

    from src.chat_service.account_tools import get_allocation_history

    result = await get_allocation_history.ainvoke({"access_token": "test-token", "tenant_id": 1, "user_id": "user123", "cmp": "001", "item": "SKU-001"})
    assert result == expected


@pytest.mark.asyncio
async def test_get_ticket_types_success(mock_httpx_response, mock_client):
    expected = {"types": [{"id": 1, "name": "Type A"}]}
    mock_client.put = AsyncMock(return_value=mock_httpx_response(expected))

    from src.chat_service.account_tools import get_ticket_types

    result = await get_ticket_types.ainvoke({"access_token": "test-token", "tenant_id": 1, "co": "001"})
    assert result == expected


@pytest.mark.asyncio
async def test_get_company_locations_success(mock_httpx_response, mock_client):
    expected = {"locations": [{"code": "WH1", "name": "Warehouse 1"}]}
    mock_client.get = AsyncMock(return_value=mock_httpx_response(expected))

    from src.chat_service.account_tools import get_company_locations

    result = await get_company_locations.ainvoke({"access_token": "test-token", "tenant_id": 1, "company_code": "001"})
    assert result == expected


@pytest.mark.asyncio
async def test_get_material_location_inventory_success(
    mock_httpx_response, mock_client
):
    expected = {"inventory": [{"loc": "WH1", "qty": 50}]}
    mock_client.put = AsyncMock(return_value=mock_httpx_response(expected))

    from src.chat_service.account_tools import get_material_location_inventory

    result = await get_material_location_inventory.ainvoke(
        {"access_token": "test-token", "tenant_id": 1, "user_id": "user123", "cmp": "001", "item": "SKU-001", "loc": ["WH1"]}
    )
    assert result == expected
