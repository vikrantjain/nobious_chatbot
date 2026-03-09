import logging
from typing import Annotated, Any

import httpx
from langchain_core.tools import InjectedToolArg, tool

from src.chat_service.config import config

logger = logging.getLogger(__name__)


def _headers(access_token: str, tenant_id: int) -> dict[str, str]:
    return {
        "login-type": "NATIVE",
        "tenant_id": str(tenant_id),
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


@tool
async def get_category_list(
    company: str,
    access_token: Annotated[str, InjectedToolArg],
    tenant_id: Annotated[int, InjectedToolArg],
    category_type: str = "forType",
) -> dict[str, Any]:
    """Get the list of categories for a given company.

    Args:
        company: The company code to fetch categories for.
        category_type: Filters the category list by type (default: "forType").

    Returns:
        A dict with a `payload` list of categories, each containing:
        `id`, `category` (core value), `status`, `vistaLocation`, and `isDefault`.
    """
    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            r = await client.put(
                f"{config.ims_base_url}/api/inventory/ticket/getForTypeList",
                headers=_headers(access_token, tenant_id),
                json={"tenantId": tenant_id, "co": company, "category": category_type},
            )
            r.raise_for_status()
            data = r.json()
            data["payload"] = [
                {
                    "id": res["id"],
                    "category": res["coreValue"],
                    "status": res["status"],
                    "vistaLocation": res["vistaLocation"],
                    "isDefault": res["isDefault"]
                }
                for res in data["payload"]]
            return data
    except Exception as e:
        logger.error(f"get_category_list failed: {e}")
        raise

@tool
async def get_all_companies(
    access_token: Annotated[str, InjectedToolArg],
    tenant_id: Annotated[int, InjectedToolArg],
) -> dict[str, Any]:
    """Get the list of all companies available in the system."""
    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            r = await client.get(
                f"{config.ims_base_url}/api/vista/company/allcompanies",
                headers=_headers(access_token, tenant_id),
            )
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.error(f"get_all_companies failed: {e}")
        raise


# @tool
async def get_company_locations(
    company_code: str,
    access_token: Annotated[str, InjectedToolArg],
    tenant_id: Annotated[int, InjectedToolArg],
) -> dict[str, Any]:
    """Get the list of inventory locations for a company in the system.

    Args:
        company_code: The company code whose locations to retrieve.

    Returns:
        A dict with a `locDetails` list, each entry containing:
        `locationCode` and `locationDescription`.
    """
    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            r = await client.get(
                f"{config.ims_base_url}/api/vista/location/getMultipleCompanieslocations/{company_code}",
                headers=_headers(access_token, tenant_id),
            )
            r.raise_for_status()
            data = r.json()
            data["locDetails"] = [
                {
                    "locationCode": loc["loc"],
                    "locationDescription": loc["locDesc"],
                }
                for loc in data["locDetails"]
            ]
            return data
    except Exception as e:
        logger.error(f"get_company_locations failed: {e}")
        raise


@tool
async def get_locations(
    access_token: Annotated[str, InjectedToolArg],
    tenant_id: Annotated[int, InjectedToolArg],
    user_id: Annotated[str, InjectedToolArg],
) -> dict[str, Any]:
    """Get the available inventory locations in the system.

    Returns:
        A dict with a `payload` list of assigned locations, each containing:
        `userLocationId`, `companyId`, `locationCode`,
        `locationDescription`, and `isDefault`.
    """
    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            r = await client.get(
                f"{config.ims_base_url}/api/ims/user/getUserAssingedLocationByUserId/{user_id}",
                headers=_headers(access_token, tenant_id),
            )
            r.raise_for_status()
            data = r.json()
            data["payload"] = [
                {
                    "userLocationId": loc["userLocationId"],
                    "companyId": loc["companyId"],
                    "locationCode": loc["loc"],
                    "locationDescription": loc["locDesc"],
                    "isDefault": loc["isDefault"],
                }
                for loc in data["payload"]
            ]
            return data
    except Exception as e:
        logger.error(f"get_locations failed: {e}")
        raise


@tool
async def get_inventory_at_location(
    company_code: str,
    location_codes: list[str],
    access_token: Annotated[str, InjectedToolArg],
    tenant_id: Annotated[int, InjectedToolArg],
    status: str | None = None,
) -> dict[str, Any]:
    """Get the inventory of materials/items at specific one or more locations of a company.

    Args:
        company_code: The company code to search within.
        location_codes: List of location codes to filter by.
        status: Optional status filter (e.g. "Y" for active).

    Returns:
        A dict with an `itemList` containing matched items, each with:
        `id`, `item` (item code), `description`, `status`, `type`, `stocked`,
        `unitOfMeasure`, `salesUnitOfMeasure`, `category`, `materialGroup`,
        `locationCode`, `locationCount`, `vendorCount`, `standardCost`,
        `standardPrice`, `unitCost`, `averageCost`, `price`, `onHand`, `onOrder`,
        `lowStockThreshold`, `reorderPoint`, `taxCode`, `taxable`,
        `taxDescription`, and `comment`.
    """
    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            r = await client.put(
                f"{config.ims_base_url}/api/vista/material/search",
                headers=_headers(access_token, tenant_id),
                json={"cmp": company_code, "status": status, "inco": company_code, "loc": location_codes},
            )
            r.raise_for_status()
            data = r.json()
            data["itemList"] = [
                {
                    "id": m["id"],
                    "item": m["item"],  # item code / item ID
                    "description": m["description"],
                    "status": m["status"],
                    "type": m["type"],
                    "stocked": m["stocked"],
                    "unitOfMeasure": m["uom"],
                    "salesUnitOfMeasure": m["salesUom"],
                    "category": m["category"],
                    "materialGroup": m["matlGroup"],
                    "locationCode": m["loc"],
                    "locationCount": m["locationCount"],
                    "vendorCount": m["vendorCount"],
                    "standardCost": m["stdCost"],
                    "standardPrice": m["stdPrice"],
                    "unitCost": m["unitCost"],
                    "averageCost": m["avgCost"],
                    "price": m["price"],
                    "onHand": m["onHand"],
                    "onOrder": m["onOrder"],
                    "lowStockThreshold": m["lowStock"],
                    "reorderPoint": m["reOrder"],
                    "taxCode": m["taxCode"],
                    "taxable": m["taxable"],
                    "taxDescription": m["taxDescription"],
                    "comment": m["comment"],
                    # Ignored: "ecm"/"priceECM"/"priceEcm"/"lastEcm" (ECM-related, unclear),
                    # "line" (unclear), "itemKeyId" (unclear vs "id"),
                    # "costGLAcct"/"invGLAcct"/"adjGLAcct"/"jobSalesGLAcct" (GL accounts),
                    # "jobRate"/"costType"/"sold"/"cost"/"total"/"tax" (accounting),
                    # "markUp"/"uomConversion"/"retrievedQuantity"/"stdUom" (secondary),
                    # "company"/"cmp" (redundant, already a parameter)
                }
                for m in data["itemList"]
            ]
            return data
    except Exception as e:
        logger.error(f"get_inventory_at_location failed: {e}")
        raise


@tool
async def get_item_details(
    company_code: str,
    item_code: str,
    location_codes: list[str],
    access_token: Annotated[str, InjectedToolArg],
    tenant_id: Annotated[int, InjectedToolArg],
) -> dict[str, Any]:
    """Get detailed information about a specific inventory item at one more locations.

    Args:
        company_code: The company code the item belongs to.
        item_code: The item code to retrieve details for.
        location_codes: List of Vista location codes to scope the lookup.

    Returns:
        A dict with an `itemDetail` object containing:
        `item` (item code), `description`, `status`, `type`, `stocked`,
        `unitOfMeasure`, `salesUnitOfMeasure`, `category`, `materialGroup`,
        `locationCode`, `locationCount`, `vendorCount`, `standardCost`, `standardPrice`, `unitCost`,
        `averageCost`, `price`, `onHand`, `onOrder`, `lowStockThreshold`,
        `reorderPoint`, `taxCode`, `taxable`, `taxDescription`, and `comment`.
    """
    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            r = await client.put(
                f"{config.ims_base_url}/api/vista/material/getItemDetailsByVistaLoc/{company_code}/{item_code}",
                headers=_headers(access_token, tenant_id),
                json=location_codes,
            )
            r.raise_for_status()
            data = r.json()
            m = data["itemDetail"]
            data["itemDetail"] = {
                "item": m["item"],
                "description": m["description"],
                "status": m["status"],
                "type": m["type"],
                "stocked": m["stocked"],
                "unitOfMeasure": m["uom"],
                "salesUnitOfMeasure": m["salesUom"],
                "category": m["category"],
                "materialGroup": m["matlGroup"],
                "locationCode": m["loc"],
                "locationCount": m["locationCount"],
                "vendorCount": m["vendorCount"],
                "standardCost": m["stdCost"],
                "standardPrice": m["stdPrice"],
                "unitCost": m["unitCost"],
                "averageCost": m["avgCost"],
                "price": m["price"],
                "onHand": m["onHand"],
                "onOrder": m["onOrder"],
                "lowStockThreshold": m["lowStock"],
                "reorderPoint": m["reOrder"],
                "taxCode": m["taxCode"],
                "taxable": m["taxable"],
                "taxDescription": m["taxDescription"],
                "comment": m["comment"],
                # Ignored: "id"/"itemKeyId" (internal IDs, unclear distinction),
                # "ecm"/"priceECM"/"priceEcm"/"lastEcm" (ECM-related, unclear),
                # "line" (unclear), "costGLAcct"/"invGLAcct"/"adjGLAcct"/"jobSalesGLAcct" (GL accounts),
                # "jobRate"/"costType"/"sold"/"cost"/"total"/"tax" (accounting),
                # "markUp"/"uomConversion"/"retrievedQuantity"/"stdUom" (secondary),
                # "company"/"cmp" (redundant, already a parameter)
            }
            return data
    except Exception as e:
        logger.error(f"get_item_details failed: {e}")
        raise


@tool
async def get_allocation_history(
    company_code: str,
    item_code: str,
    access_token: Annotated[str, InjectedToolArg],
    tenant_id: Annotated[int, InjectedToolArg],
    user_id: Annotated[str, InjectedToolArg],
) -> dict[str, Any]:
    """Get the transaction/allocation history for a specific inventory item.

    Args:
        company_code: The company code the item belongs to.
        item_code: The item code to retrieve allocation history for.

    Returns:
        A dict with a `payload` list of allocation events, each containing:
        `transactionId`, `transactionType`, `quantity`, `quantityReceived`,
        `forType`, `forDescription`, `allocationFor`, and `createdDate`.
    """
    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            r = await client.get(
                f"{config.ims_base_url}/api/inventory/allocation/allocationHistoryByItem/{user_id}/{company_code}/{item_code}",
                headers=_headers(access_token, tenant_id),
            )
            r.raise_for_status()
            data = r.json()
            data["payload"] = [
                {
                    "transactionId": a["transactionId"],
                    "transactionType": a["transactionType"],
                    "quantity": a["quantity"],
                    "quantityReceived": a["qtyReceived"],
                    "forType": a["forType"],
                    "forDescription": a["forDescription"],
                    "allocationFor": a["allocationFor"],
                    "createdDate": a["createdDate"],
                    # Ignored: "itemCode"/"co" (redundant, already parameters), "tenantKeyId" (internal key)
                }
                for a in data["payload"]
            ]
            return data
    except Exception as e:
        logger.error(f"get_allocation_history failed: {e}")
        raise


@tool
async def get_material_location_inventory(
    company_code: str,
    item_code: str,
    location_codes: list[str],
    access_token: Annotated[str, InjectedToolArg],
    tenant_id: Annotated[int, InjectedToolArg],
    user_id: Annotated[str, InjectedToolArg],
) -> dict[str, Any]:
    """Get inventory quantities for an item across one or more locations.

    Args:
        company_code: The company code the item belongs to.
        item_code: The item code to look up inventory for.
        location_codes: List of location codes to scope the lookup.

    Returns:
        A dict with a `payload` containing:
        - `byLocation`: list of locations, each with `locationId`, `locationDescription`,
          and `materialByLocation` (list of `itemCode`, `itemDescription`, `quantity`,
          `unitOfMeasure`, `nonPalletedQuantity`, `palletList`, `barcodeId`, `distributorCode`).
        - `byMaterial`: list of items, each with `itemCode`, `itemDescription`, `quantity`,
          `unitOfMeasure`, and `locationByMaterial` (list of `locationCode`,
          `locationDescription`, `quantity`, `unitOfMeasure`, `nonPalletedQuantity`, `palletList`).
    """
    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            r = await client.put(
                f"{config.ims_base_url}/api/inventory/materialLocation/getMaterialLocationListByItemByAssignedLocation/{user_id}",
                headers=_headers(access_token, tenant_id),
                json={"cmp": company_code, "item": item_code, "loc": location_codes},
            )
            r.raise_for_status()
            data = r.json()
            payload = data["payload"]
            data["payload"] = {
                "byLocation": [
                    {
                        "locationId": loc["locationId"],
                        "locationDescription": loc["locationDescription"],
                        "materialByLocation": [
                            {
                                "itemCode": m["material"],
                                "itemDescription": m["matertialDescription"],  # typo in API response
                                "quantity": m["quantity"],
                                "unitOfMeasure": m["uom"],
                                "nonPalletedQuantity": m["nonPalletedQuantity"],
                                "palletList": m["palletList"],
                                "barcodeId": m["barcodeId"],
                                "distributorCode": m["distributorCode"],
                                # Ignored: "keyId"/"locId" (internal IDs), "cmpCode"/"cmpName" (redundant parameters)
                            }
                            for m in loc["materialByLocation"]
                        ],
                    }
                    for loc in payload["byLocation"]
                ],
                "byMaterial": [
                    {
                        "itemCode": m["material"],
                        "itemDescription": m["materialDescription"],
                        "quantity": m["quantity"],
                        "unitOfMeasure": m["uom"],
                        "locationByMaterial": [
                            {
                                "locationCode": loc["location"],
                                "locationDescription": loc["locationDescription"],
                                "quantity": loc["quantity"],
                                "unitOfMeasure": loc["uom"],
                                "nonPalletedQuantity": loc["nonPalletedQuantity"],
                                "palletList": loc["palletList"],
                                # Ignored: "keyId"/"locId" (internal IDs)
                            }
                            for loc in m["locationByMaterial"]
                        ],
                    }
                    for m in payload["byMaterial"]
                ],
                # Ignored: "locationFile"/"materialFile"/"cycleCountFile" (file export references, always null)
            }
            return data
    except Exception as e:
        logger.error(f"get_material_location_inventory failed: {e}")
        raise


ACCOUNT_TOOLS = [
    get_category_list,
    get_all_companies,
    get_locations,
    get_inventory_at_location,
    get_item_details,
    get_allocation_history,
    get_material_location_inventory,
]
