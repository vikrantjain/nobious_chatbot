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
async def test_get_category_list_success(mock_httpx_response, mock_client):
    raw_response = {
        "payload": [
            {"id": 1, "coreValue": "Type A", "status": "A", "vistaLocation": "LOC1", "isDefault": True, "extra": "ignored"}
        ]
    }
    mock_client.put = AsyncMock(return_value=mock_httpx_response(raw_response))

    from src.chat_service.account_tools import get_category_list

    result = await get_category_list.ainvoke({"access_token": "test-token", "tenant_id": 1, "company": "001"})
    assert result == {
        "payload": [
            {"id": 1, "category": "Type A", "status": "A", "vistaLocation": "LOC1", "isDefault": True}
        ]
    }


@pytest.mark.asyncio
async def test_get_locations_success(mock_httpx_response, mock_client):
    raw_response = {
        "payload": [
            {"userLocationId": 10, "companyId": 1, "loc": "WH1", "locDesc": "Warehouse 1", "isDefault": True},
        ]
    }
    mock_client.get = AsyncMock(return_value=mock_httpx_response(raw_response))

    from src.chat_service.account_tools import get_locations

    result = await get_locations.ainvoke(
        {"access_token": "test-token", "tenant_id": 1, "user_id": "user123"}
    )
    assert result == {
        "payload": [
            {"userLocationId": 10, "companyId": 1, "locationCode": "WH1", "locationDescription": "Warehouse 1", "isDefault": True},
        ]
    }
    mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_inventory_at_location_success(mock_httpx_response, mock_client):
    raw_response = {
        "itemList": [
            {
                "id": 1, "item": "SKU-001", "description": "Test Item", "status": "A",
                "type": "M", "stocked": "Y", "uom": "EA", "salesUom": "EA",
                "category": "CAT1", "matlGroup": "GRP1", "loc": "WH1",
                "locationCount": 2, "vendorCount": 1,
                "stdCost": 10.0, "stdPrice": 15.0, "unitCost": 9.5, "avgCost": 9.8,
                "price": 15.0, "onHand": 100, "onOrder": 50,
                "lowStock": 10, "reOrder": 20,
                "taxCode": "TX1", "taxable": "Y", "taxDescription": "Sales Tax",
                "comment": "Test comment",
            }
        ]
    }
    mock_client.put = AsyncMock(return_value=mock_httpx_response(raw_response))

    from src.chat_service.account_tools import get_inventory_at_location

    result = await get_inventory_at_location.ainvoke(
        {"access_token": "test-token", "tenant_id": 1, "company_code": "001", "location_codes": ["WH1"]}
    )
    assert result == {
        "itemList": [
            {
                "id": 1, "item": "SKU-001", "description": "Test Item", "status": "A",
                "type": "M", "stocked": "Y", "unitOfMeasure": "EA", "salesUnitOfMeasure": "EA",
                "category": "CAT1", "materialGroup": "GRP1", "locationCode": "WH1",
                "locationCount": 2, "vendorCount": 1,
                "standardCost": 10.0, "standardPrice": 15.0, "unitCost": 9.5, "averageCost": 9.8,
                "price": 15.0, "onHand": 100, "onOrder": 50,
                "lowStockThreshold": 10, "reorderPoint": 20,
                "taxCode": "TX1", "taxable": "Y", "taxDescription": "Sales Tax",
                "comment": "Test comment",
            }
        ]
    }
    mock_client.put.assert_called_once()


@pytest.mark.asyncio
async def test_get_inventory_at_location_error(mock_httpx_response, mock_client):
    mock_client.put = AsyncMock(return_value=mock_httpx_response({}, status_code=500))

    from src.chat_service.account_tools import get_inventory_at_location

    with pytest.raises(httpx.HTTPStatusError):
        await get_inventory_at_location.ainvoke(
            {"access_token": "test-token", "tenant_id": 1, "company_code": "001", "location_codes": ["WH1"]}
        )


@pytest.mark.asyncio
async def test_get_item_details_success(mock_httpx_response, mock_client):
    raw_response = {
        "itemDetail": {
            "item": "SKU-001", "description": "Test Item", "status": "A",
            "type": "M", "stocked": "Y", "uom": "EA", "salesUom": "EA",
            "category": "CAT1", "matlGroup": "GRP1", "loc": "WH1",
            "locationCount": 2, "vendorCount": 1,
            "stdCost": 10.0, "stdPrice": 15.0, "unitCost": 9.5, "avgCost": 9.8,
            "price": 15.0, "onHand": 100, "onOrder": 50,
            "lowStock": 10, "reOrder": 20,
            "taxCode": "TX1", "taxable": "Y", "taxDescription": "Sales Tax",
            "comment": "Test comment",
        }
    }
    mock_client.put = AsyncMock(return_value=mock_httpx_response(raw_response))

    from src.chat_service.account_tools import get_item_details

    result = await get_item_details.ainvoke(
        {"access_token": "test-token", "tenant_id": 1, "company_code": "001", "item_code": "SKU-001", "location_codes": ["WH1"]}
    )
    assert result == {
        "itemDetail": {
            "item": "SKU-001", "description": "Test Item", "status": "A",
            "type": "M", "stocked": "Y", "unitOfMeasure": "EA", "salesUnitOfMeasure": "EA",
            "category": "CAT1", "materialGroup": "GRP1", "locationCode": "WH1",
            "locationCount": 2, "vendorCount": 1,
            "standardCost": 10.0, "standardPrice": 15.0, "unitCost": 9.5, "averageCost": 9.8,
            "price": 15.0, "onHand": 100, "onOrder": 50,
            "lowStockThreshold": 10, "reorderPoint": 20,
            "taxCode": "TX1", "taxable": "Y", "taxDescription": "Sales Tax",
            "comment": "Test comment",
        }
    }
    mock_client.put.assert_called_once()


@pytest.mark.asyncio
async def test_get_item_details_error(mock_httpx_response, mock_client):
    mock_client.put = AsyncMock(return_value=mock_httpx_response({}, status_code=404))

    from src.chat_service.account_tools import get_item_details

    with pytest.raises(httpx.HTTPStatusError):
        await get_item_details.ainvoke(
            {"access_token": "test-token", "tenant_id": 1, "company_code": "001", "item_code": "SKU-001", "location_codes": ["WH1"]}
        )


@pytest.mark.asyncio
async def test_get_allocation_history_success(mock_httpx_response, mock_client):
    raw_response = {
        "payload": [
            {
                "transactionId": 101, "transactionType": "OUT", "quantity": 5,
                "qtyReceived": 0, "forType": "JOB", "forDescription": "Job 100",
                "allocationFor": "WO-001", "createdDate": "01/15/2024",
                "itemCode": "SKU-001", "co": "001", "tenantKeyId": 999,
            }
        ]
    }
    mock_client.get = AsyncMock(return_value=mock_httpx_response(raw_response))

    from src.chat_service.account_tools import get_allocation_history

    result = await get_allocation_history.ainvoke(
        {"access_token": "test-token", "tenant_id": 1, "user_id": "user123", "company_code": "001", "item_code": "SKU-001"}
    )
    assert result == {
        "payload": [
            {
                "transactionId": 101, "transactionType": "OUT", "quantity": 5,
                "quantityReceived": 0, "forType": "JOB", "forDescription": "Job 100",
                "allocationFor": "WO-001", "createdDate": "01/15/2024",
            }
        ]
    }
    mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_material_location_inventory_success(mock_httpx_response, mock_client):
    raw_response = {
        "payload": {
            "byLocation": [
                {
                    "locationId": 10,
                    "locationDescription": "Warehouse 1",
                    "materialByLocation": [
                        {
                            "material": "SKU-001", "matertialDescription": "Test Item",
                            "quantity": 50, "uom": "EA",
                            "nonPalletedQuantity": 50, "palletList": [],
                            "barcodeId": "BC001", "distributorCode": "DIST1",
                            "keyId": 99, "locId": 10, "cmpCode": "001", "cmpName": "Test Co",
                        }
                    ],
                }
            ],
            "byMaterial": [
                {
                    "material": "SKU-001", "materialDescription": "Test Item",
                    "quantity": 50, "uom": "EA",
                    "locationByMaterial": [
                        {
                            "location": "WH1", "locationDescription": "Warehouse 1",
                            "quantity": 50, "uom": "EA",
                            "nonPalletedQuantity": 50, "palletList": [],
                            "keyId": 99, "locId": 10,
                        }
                    ],
                }
            ],
            "locationFile": None,
            "materialFile": None,
            "cycleCountFile": None,
        }
    }
    mock_client.put = AsyncMock(return_value=mock_httpx_response(raw_response))

    from src.chat_service.account_tools import get_material_location_inventory

    result = await get_material_location_inventory.ainvoke(
        {"access_token": "test-token", "tenant_id": 1, "user_id": "user123",
         "company_code": "001", "item_code": "SKU-001", "location_codes": ["WH1"]}
    )
    assert result == {
        "payload": {
            "byLocation": [
                {
                    "locationId": 10,
                    "locationDescription": "Warehouse 1",
                    "materialByLocation": [
                        {
                            "itemCode": "SKU-001", "itemDescription": "Test Item",
                            "quantity": 50, "unitOfMeasure": "EA",
                            "nonPalletedQuantity": 50, "palletList": [],
                            "barcodeId": "BC001", "distributorCode": "DIST1",
                        }
                    ],
                }
            ],
            "byMaterial": [
                {
                    "itemCode": "SKU-001", "itemDescription": "Test Item",
                    "quantity": 50, "unitOfMeasure": "EA",
                    "locationByMaterial": [
                        {
                            "locationCode": "WH1", "locationDescription": "Warehouse 1",
                            "quantity": 50, "unitOfMeasure": "EA",
                            "nonPalletedQuantity": 50, "palletList": [],
                        }
                    ],
                }
            ],
        }
    }
    mock_client.put.assert_called_once()
