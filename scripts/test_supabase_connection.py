import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from rich.console import Console
from rich.panel import Panel

from pricing_engine.db import SupabaseClient

console = Console(legacy_windows=False)


async def check_connection() -> None:
    console.print(Panel("[bold cyan]Supabase Cloud Connection Diagnostic[/]", expand=False))

    client = SupabaseClient()

    if not client.is_configured:
        console.print(
            "\n[bold yellow]⚠️  Supabase is NOT configured yet.[/]\n"
            "[dim]The engine is currently running in [bold green]Offline Graceful Fallback Mode[/] using verified in-memory seed defaults.[/]\n\n"
            "[bold white]To connect your live Supabase database:[/]\n"
            "1. Copy [cyan].env.example[/] to [cyan].env[/]\n"
            "2. Paste your [bold]SUPABASE_URL[/] and [bold]SUPABASE_KEY[/]\n"
            "3. Run the schema in [cyan]scripts/setup_supabase.sql[/] in the Supabase SQL Editor\n"
            "4. Re-run this script: [green]python scripts/test_supabase_connection.py[/]\n"
        )
        return

    session = client._ensure_session()
    try:
        resp = await session.get(
            f"{client.url}/rest/v1/capacity_registry?select=*&status=eq.APPROVED",
            headers=client._headers(),
            timeout=client.timeout,
        )
    except Exception as exc:
        console.print(f"\n[bold red]❌ Network Connection Failed:[/] {exc}")
        return

    if resp.status_code == 401:
        console.print(
            "\n[bold red]❌ Authentication Failed (HTTP 401 - Invalid API key)![/]\n"
            "[yellow]Supabase REST API ne is key ko reject kar diya hai.[/]\n\n"
            "[bold white]Asal API Key Kahan se Milegi:[/]\n"
            "1. Supabase Dashboard mein [cyan]Project Settings (⚙️) -> API[/] par jayein.\n"
            "2. [bold]Project API keys[/] section mein jayein.\n"
            "3. [bold green]anon (public)[/] ya [bold yellow]service_role[/] key copy karein (jo [bold]eyJhbGci...[/] se shuru hoti hai).\n"
            "4. Apni [cyan].env[/] file mein [bold]SUPABASE_KEY=eyJ...[/] paste karein.\n"
        )
        return

    if resp.status_code == 404:
        console.print(
            "\n[bold yellow]⚠️  API Key Valid hai, lekin Tables nahi mile (HTTP 404)![/]\n"
            "[dim]Aap ne abhi tak SQL schema run nahi kiya.[/]\n\n"
            "[bold white]Fix:[/]\n"
            "1. Supabase Dashboard mein [cyan]SQL Editor[/] kholen.\n"
            "2. [cyan]scripts/setup_supabase.sql[/] ka code paste kar ke [bold]RUN[/] dabayein.\n"
        )
        return

    capacities = await client.fetch_approved_capacities()
    synonyms = await client.fetch_approved_synonyms()

    console.print(f"  • Approved Capacity Codes fetched: [bold green]{len(capacities)}[/]")
    console.print(f"  • Approved Synonym Pairs fetched:  [bold green]{len(synonyms)}[/]")

    console.print("\n[bold green]✅ Successfully connected to live Supabase Cloud PostgreSQL![/]\n")


if __name__ == "__main__":
    asyncio.run(check_connection())
