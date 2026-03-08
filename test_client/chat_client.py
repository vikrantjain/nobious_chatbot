#!/usr/bin/env python3
"""Interactive CLI test client for the Nobious IMS Chat Service."""
import sys

import click
import httpx


def login(ims_url: str, email: str, password: str, tenant_id: str) -> str:
    """Authenticate with IMS and return JWT token."""
    with httpx.Client(verify=False, timeout=10.0) as client:
        resp = client.post(
            f"{ims_url}/api/ims/user/login",
            headers={"login-type": "NATIVE", "tenant_id": tenant_id, "Content-Type": "application/json"},
            json={"email": email, "password": password},
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("payload", {}).get("jwt")
        if not token:
            raise ValueError("Login failed: JWT not found in response")
        return token


def send_chat(base_url: str, token: str, tenant_id: str, query: str, session_id: str | None = None) -> dict:
    """Send a chat message and return the response dict."""
    with httpx.Client(verify=False, timeout=30.0) as client:
        payload = {"query": query}
        if session_id:
            payload["session_id"] = session_id
        resp = client.post(
            f"{base_url}/api/chat",
            headers={"Authorization": f"Bearer {token}", "tenant-id": tenant_id, "Content-Type": "application/json"},
            json=payload,
        )
        if resp.status_code == 429:
            return {"error": "Rate limit exceeded. Please wait a moment before trying again."}
        if resp.status_code == 401:
            return {"error": "Authentication failed. Your session may have expired."}
        resp.raise_for_status()
        return resp.json()


@click.command()
@click.option("--base-url", default="http://localhost:5000", show_default=True, help="Chat service URL")
@click.option("--ims-url", default="http://localhost:5443", show_default=True, help="IMS base URL for login")
@click.option("--tenant-id", default=None, help="Tenant ID for IMS authentication")
def main(base_url: str, ims_url: str, tenant_id: str):
    """Interactive CLI client for the Nobious IMS Chat Service.

    Authenticates with IMS and enters a chat loop.
    Press Ctrl+C to exit.

    Example:
        uv run python test_client/chat_client.py --base-url http://localhost:5000 --ims-url https://tenant1.nobious.io:5443 --tenant-id 1
    """
    click.echo("=== Nobious IMS Chat Client ===")
    click.echo(f"Service: {base_url}")
    click.echo(f"IMS: {ims_url}")
    click.echo(f"Tenant: {tenant_id}")
    click.echo("")

    # Authenticate
    if not tenant_id:
        tenant_id = click.prompt("Tenant ID")
    email = click.prompt("Email")
    password = click.prompt("Password", hide_input=True)

    try:
        token = login(ims_url, email, password, tenant_id)
        click.echo("Logged in successfully")
        click.echo("Type your questions below. Press Ctrl+C to exit.")
        click.echo("-" * 40)
    except Exception as e:
        click.echo(f"Login failed: {e}", err=True)
        sys.exit(1)

    session_id = None

    try:
        while True:
            try:
                query = click.prompt("\nYou")
            except click.Abort:
                break

            if not query.strip():
                continue

            try:
                result = send_chat(base_url, token, tenant_id, query, session_id)

                if "error" in result:
                    click.echo(f"Error: {result['error']}", err=True)
                else:
                    session_id = result.get("session_id", session_id)
                    response = result.get("response", "")
                    click.echo(f"\nAssistant: {response}")

            except httpx.HTTPStatusError as e:
                click.echo(f"HTTP error {e.response.status_code}: {e.response.text}", err=True)
            except Exception as e:
                click.echo(f"Error: {e}", err=True)

    except KeyboardInterrupt:
        pass

    click.echo("\nGoodbye!")


if __name__ == "__main__":
    main()
