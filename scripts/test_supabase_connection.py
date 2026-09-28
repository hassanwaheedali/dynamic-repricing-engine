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

    console.print(f"Connecting to: [bold cyan]{client.url}[/]...")

    capacities = await client.fetch_approved_capacities()
    synonyms = await client.fetch_approved_synonyms()

    console.print(f"  • Approved Capacity Codes fetched: [bold green]{len(capacities)}[/]")
    console.print(f"  • Approved Synonym Pairs fetched:  [bold green]{len(synonyms)}[/]")

    console.print("\n[bold green]✅ Successfully connected to live Supabase Cloud PostgreSQL![/]\n")


if __name__ == "__main__":
    asyncio.run(check_connection())
