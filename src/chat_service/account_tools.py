from typing import Annotated, Any

import httpx
from langchain_core.tools import InjectedToolArg, tool

from src.chat_service.config import config


def _headers(access_token: str, tenant_id: int) -> dict[str, str]:
    return {
        "login-type": "NATIVE",
        "tenant_id": str(tenant_id),
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


@tool
async def get_ticket_types(
    co: str,
    access_token: Annotated[str, InjectedToolArg],
    tenant_id: Annotated[int, InjectedToolArg],
    category: str = "forType",
) -> dict[str, Any]:
    """Get ticket/group category list for a company from IMS.
    Returns ticket types available for the given company and category."""
    async with httpx.AsyncClient(verify=False) as client:
        r = await client.put(
            f"{config.ims_base_url}/api/inventory/ticket/getForTypeList",
            headers=_headers(access_token, tenant_id),
            json={"tenantId": tenant_id, "co": co, "category": category},
        )
        r.raise_for_status()
        return r.json()


@tool
async def get_all_companies(
    access_token: Annotated[str, InjectedToolArg],
    tenant_id: Annotated[int, InjectedToolArg],
) -> dict[str, Any]:
    """Get the list of all companies accessible to the authenticated user in IMS."""
    async with httpx.AsyncClient(verify=False) as client:
        r = await client.get(
            f"{config.ims_base_url}/api/vista/company/allcompanies",
            headers=_headers(access_token, tenant_id),
        )
        r.raise_for_status()
        return r.json()


@tool
async def get_company_locations(
    company_code: str,
    access_token: Annotated[str, InjectedToolArg],
    tenant_id: Annotated[int, InjectedToolArg],
) -> dict[str, Any]:
    """Get all warehouse/store locations for the given company code."""
    async with httpx.AsyncClient(verify=False) as client:
        r = await client.get(
            f"{config.ims_base_url}/api/vista/location/getMultipleCompanieslocations/{company_code}",
            headers=_headers(access_token, tenant_id),
        )
        r.raise_for_status()
        return r.json()


@tool
async def get_user_assigned_locations(
    user_id: str,
    access_token: Annotated[str, InjectedToolArg],
    tenant_id: Annotated[int, InjectedToolArg],
) -> dict[str, Any]:
    """Get the inventory locations assigned to a specific user by their user ID."""
    async with httpx.AsyncClient(verify=False) as client:
        r = await client.get(
            f"{config.ims_base_url}/api/ims/user/getUserAssingedLocationByUserId/{user_id}",
            headers=_headers(access_token, tenant_id),
        )
        r.raise_for_status()
        return r.json()


@tool
async def search_materials(
    cmp: str,
    loc: list[str],
    access_token: Annotated[str, InjectedToolArg],
    tenant_id: Annotated[int, InjectedToolArg],
    status: str | None = None,
    inco: str = "8",
) -> dict[str, Any]:
    """Search for inventory materials/items at specific locations for a company.
    Returns a list of matching items with their details."""
    async with httpx.AsyncClient(verify=False) as client:
        r = await client.put(
            f"{config.ims_base_url}/api/vista/material/search",
            headers=_headers(access_token, tenant_id),
            json={"cmp": cmp, "status": status, "inco": inco, "loc": loc},
        )
        r.raise_for_status()
        return r.json()


@tool
async def get_item_details(
    cmp: str,
    item: str,
    locations: list[str],
    access_token: Annotated[str, InjectedToolArg],
    tenant_id: Annotated[int, InjectedToolArg],
) -> dict[str, Any]:
    """Get detailed information about a specific inventory item at given Vista locations.
    Returns item specs, pricing, and availability details."""
    async with httpx.AsyncClient(verify=False) as client:
        r = await client.put(
            f"{config.ims_base_url}/api/vista/material/getItemDetailsByVistaLoc/{cmp}/{item}",
            headers=_headers(access_token, tenant_id),
            json=locations,
        )
        r.raise_for_status()
        return r.json()


@tool
async def get_allocation_history(
    user_id: str,
    cmp: str,
    item: str,
    access_token: Annotated[str, InjectedToolArg],
    tenant_id: Annotated[int, InjectedToolArg],
) -> dict[str, Any]:
    """Get the transaction/allocation history for a specific inventory item.
    Returns a chronological list of allocation events."""
    async with httpx.AsyncClient(verify=False) as client:
        r = await client.get(
            f"{config.ims_base_url}/api/inventory/allocation/allocationHistoryByItem/{user_id}/{cmp}/{item}",
            headers=_headers(access_token, tenant_id),
        )
        r.raise_for_status()
        return r.json()


@tool
async def get_material_location_inventory(
    user_id: str,
    cmp: str,
    item: str,
    loc: list[str],
    access_token: Annotated[str, InjectedToolArg],
    tenant_id: Annotated[int, InjectedToolArg],
) -> dict[str, Any]:
    """Get inventory quantities for an item across assigned locations.
    Returns total quantity and pallet quantity per location."""
    async with httpx.AsyncClient(verify=False) as client:
        r = await client.put(
            f"{config.ims_base_url}/api/inventory/materialLocation/getMaterialLocationListByItemByAssignedLocation/{user_id}",
            headers=_headers(access_token, tenant_id),
            json={"cmp": cmp, "item": item, "loc": loc},
        )
        r.raise_for_status()
        return r.json()


ACCOUNT_TOOLS = [
    get_ticket_types,
    get_all_companies,
    get_company_locations,
    get_user_assigned_locations,
    search_materials,
    get_item_details,
    get_allocation_history,
    get_material_location_inventory,
]
