"""
API Versioning Demo

Demonstrates how to use the versioning system with example requests.

Run the API server first:
    python api/fastapi_app.py

Then run this demo:
    python api/examples/versioning_demo.py
"""

import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()
BASE_URL = "http://localhost:8766"


def demo_path_based_versioning():
    """Demo: Version specified in URL path."""
    console.print("\n[bold cyan]Demo 1: Path-Based Versioning[/bold cyan]")

    # V1 endpoint
    response = requests.get(f"{BASE_URL}/api/v1/health/")
    console.print(f"✓ GET /api/v1/health/")
    console.print(f"  Status: {response.status_code}")
    console.print(f"  X-API-Version: {response.headers.get('X-API-Version', 'N/A')}")


def demo_header_based_versioning():
    """Demo: Version specified via Accept-Version header."""
    console.print("\n[bold cyan]Demo 2: Header-Based Versioning[/bold cyan]")

    response = requests.get(
        f"{BASE_URL}/api/health/",
        headers={"Accept-Version": "v1"}
    )
    console.print(f"✓ GET /api/health/ with Accept-Version: v1")
    console.print(f"  Status: {response.status_code}")
    console.print(f"  X-API-Version: {response.headers.get('X-API-Version', 'N/A')}")


def demo_version_discovery():
    """Demo: Discover available API versions."""
    console.print("\n[bold cyan]Demo 3: Version Discovery[/bold cyan]")

    # List all versions
    response = requests.get(f"{BASE_URL}/api/versions")
    if response.status_code == 200:
        data = response.json()
        console.print(f"✓ GET /api/versions")
        console.print(f"  Current Version: {data['current_version']}")

        table = Table(title="Available Versions")
        table.add_column("Version", style="cyan")
        table.add_column("Current", style="green")
        table.add_column("Deprecated", style="yellow")
        table.add_column("Sunset Date", style="red")

        for v in data['versions']:
            table.add_row(
                v['version'],
                "✓" if v.get('current') else "",
                "✓" if v.get('deprecated') else "",
                v.get('sunset_date', '-')
            )

        console.print(table)


def demo_version_priority():
    """Demo: Version priority (path > header > default)."""
    console.print("\n[bold cyan]Demo 4: Version Priority[/bold cyan]")

    # Path wins over header
    response = requests.get(
        f"{BASE_URL}/api/v1/health/",
        headers={"Accept-Version": "v2"}  # This gets ignored
    )
    console.print(f"✓ GET /api/v1/health/ with Accept-Version: v2")
    console.print(f"  Expected: v1 (path wins)")
    console.print(f"  Actual: {response.headers.get('X-API-Version', 'N/A')}")


def demo_deprecation_warnings():
    """Demo: Deprecation headers (requires marking v1 as deprecated)."""
    console.print("\n[bold cyan]Demo 5: Deprecation Warnings[/bold cyan]")
    console.print("  Note: This requires setting DEPRECATED_VERSIONS in api/versioning.py")

    response = requests.get(f"{BASE_URL}/api/v1/health/")

    if response.headers.get("Deprecation"):
        console.print(f"  Deprecation: {response.headers.get('Deprecation')}")
        console.print(f"  Sunset: {response.headers.get('Sunset')}")
        console.print(f"  Warning: {response.headers.get('Warning')}")
    else:
        console.print("  No deprecation (v1 is current version)")


def demo_client_example():
    """Demo: Example client code."""
    console.print("\n[bold cyan]Demo 6: Client Code Example[/bold cyan]")

    code = '''
import requests

def api_call_with_version(endpoint, version="v1"):
    """Make API call with specific version."""
    response = requests.get(
        f"http://localhost:8766/api/{version}{endpoint}",
    )

    # Check if deprecated
    if response.headers.get("Deprecation") == "true":
        sunset = response.headers.get("Sunset")
        print(f"Warning: Version {version} deprecated, sunset {sunset}")

    return response.json()

# Usage
data = api_call_with_version("/staking/pool", version="v1")
print(data)
'''

    syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title="Example Client", border_style="green"))


def main():
    """Run all demos."""
    console.print(Panel.fit(
        "[bold yellow]API Versioning Demo[/bold yellow]\n"
        "Demonstrates JARVIS API versioning features",
        border_style="yellow"
    ))

    try:
        # Check if API is running
        response = requests.get(f"{BASE_URL}/api/health/quick", timeout=2)
        if response.status_code != 200:
            console.print("[red]✗ API server not responding correctly[/red]")
            return
    except requests.exceptions.RequestException:
        console.print(
            "[red]✗ API server not running![/red]\n"
            "Start it with: python api/fastapi_app.py"
        )
        return

    console.print("[green]✓ API server is running[/green]")

    # Run demos
    demo_path_based_versioning()
    demo_header_based_versioning()
    demo_version_discovery()
    demo_version_priority()
    demo_deprecation_warnings()
    demo_client_example()

    console.print("\n[bold green]✓ All demos completed![/bold green]")
    console.print("\nSee api/VERSIONING.md for more details.")


if __name__ == "__main__":
    main()
