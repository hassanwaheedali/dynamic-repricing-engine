"""AlfaMall & DigiMall Dynamic Repricing Automation Engine.

Entrypoint script for high-speed dynamic repricing pipeline.
Executes concurrent price discovery against direct backend search APIs,
applies strict variant matching, and computes winning psychological prices.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pricing_engine.pipeline import run_pipeline
from pricing_engine.range_pipeline import run_range_pipeline

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

console = Console()


def parse_args() -> argparse.Namespace:
    """Parse command line options."""
    parser = argparse.ArgumentParser(
        description="Dynamic Repricing Automation Engine for AlfaMall & DigiMall"
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=None,
        help="Input catalog CSV file or directory (default: scan data/inputs/)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output repriced CSV file (default: structured export to data/outputs/<catalog>/option_<N>/)",
    )
    parser.add_argument(
        "-b",
        "-a",
        "--batch",
        action="store_true",
        help="Batch process all catalog CSV files in data/inputs/",
    )
    parser.add_argument(
        "-c",
        "--concurrency",
        type=int,
        default=3,
        help="Maximum concurrent product search requests (default: 3)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress visual 90-char terminal audit cards",
    )
    parser.add_argument(
        "-r",
        "--range-only",
        dest="range_only",
        action="store_true",
        help=(
            "Market Range Mode: input needs only Brand+Name; outputs market Min/Max for "
            "AlfaMall & DigiMall (CSV + XLSX in data/outputs/<catalog>/option_2/), no final prices"
        ),
    )
    parser.add_argument(
        "-p",
        "--platform",
        type=str.lower,
        choices=["all", "alfa", "digi"],
        default="all",
        help="Target platform: 'all' (default), 'alfa' (AlfaMall only), or 'digi' (DigiMall only)",
    )
    parser.add_argument(
        "--alfa-only",
        action="store_true",
        help="Run repricing only for AlfaMall (alias for --platform alfa)",
    )
    parser.add_argument(
        "--digi-only",
        action="store_true",
        help="Run repricing only for DigiMall (alias for --platform digi)",
    )
    parser.add_argument(
        "-m",
        "--personal-comm",
        dest="personal_comm",
        type=float,
        default=0.0,
        help="Personal commission percentage on Net Price (e.g. 5 for 5%% + Rs. 500 Floor + Winners export)",
    )
    parser.add_argument(
        "--5pct",
        "--my-5pct",
        dest="five_pct",
        action="store_true",
        help="Shortcut for --personal-comm 5.0 (5%% Personal Commission + Rs. 500 Floor + Winning Products export)",
    )
    return parser.parse_args()


ARTIFACT_FILENAME_PATTERN = re.compile(
    r"_(?:repriced|range|winning_\w+)_(?:\d{8}_\d{6}|latest)\.csv$",
    re.IGNORECASE,
)


def find_input_catalogs(inputs_dir: Path = Path("data/inputs")) -> list[Path]:
    """Scan directory for catalog CSV files, excluding templates and generated output artifacts."""
    if not inputs_dir.is_dir():
        return []
    return sorted(
        p
        for p in inputs_dir.glob("*.csv")
        if p.is_file()
        and not p.name.lower().startswith("template")
        and not p.name.endswith(".gitkeep")
        and not ARTIFACT_FILENAME_PATTERN.search(p.name)
    )


def interactive_catalog_picker(catalogs: list[Path]) -> list[Path] | None:
    """Display a Rich interactive catalog picker and return user selection."""
    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("Option", style="bold yellow", width=8)
    table.add_column("Catalog File", style="green")

    for idx, cat in enumerate(catalogs, start=1):
        table.add_row(f"[{idx}]", cat.name)
    table.add_row("[A]", "Run All Catalogs (Batch)")
    table.add_row("[Q]", "Quit")

    panel = Panel(
        table,
        title="[bold cyan]📦 Select Catalog to Reprice[/bold cyan]",
        border_style="cyan",
        expand=False,
    )
    console.print(panel)

    try:
        choice = input(f"Select option [1-{len(catalogs)}, A, Q]: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Operation cancelled.[/yellow]")
        return None

    if choice.lower() in ("q", "quit", "exit"):
        return None
    if choice.lower() in ("a", "all"):
        return catalogs
    try:
        num = int(choice)
        if 1 <= num <= len(catalogs):
            return [catalogs[num - 1]]
    except ValueError:
        pass

    console.print(f"[bold red]❌ Invalid selection: '{choice}'. Aborting.[/bold red]")
    return None


def prompt_run_mode() -> str | None:
    """Ask which mode to run. Returns 'reprice', 'range', 'reprice_5pct', or None to quit."""
    table = Table(show_header=False, box=None)
    table.add_column(style="bold yellow", width=6)
    table.add_column(style="green")
    table.add_row("[1]", "Full Repricing (Standard +Rs. 500 Floor)")
    table.add_row("[2]", "Market Range Only (Min/Max per mall, Brand+Name list)")
    table.add_row(
        "[3]",
        "5% Personal Commission + Winning Products Finder (5% Net Price + Rs. 500 Floor)",
    )
    table.add_row("[Q]", "Quit")
    console.print(
        Panel(table, title="[bold cyan]Select Mode[/bold cyan]", border_style="cyan", expand=False)
    )
    try:
        choice = input("Select mode [1/2/3, Q] (default 1): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Operation cancelled.[/yellow]")
        return None
    if choice in ("q", "quit", "exit"):
        return None
    if choice in ("2", "r", "range"):
        return "range"
    if choice in ("3", "5", "5%", "5pct", "comm"):
        return "reprice_5pct"
    return "reprice"


async def main() -> int:
    """Main asynchronous pipeline entrypoint."""
    args = parse_args()
    input_path: Path | None = args.input
    output_path: Path | None = args.output
    target_catalogs: list[Path] = []
    range_mode: bool = args.range_only
    personal_comm_pct: float = 5.0 if args.five_pct else float(args.personal_comm or 0.0)

    if not range_mode and personal_comm_pct <= 0 and sys.stdin.isatty():
        chosen_mode = prompt_run_mode()
        if chosen_mode is None:
            return 0
        if chosen_mode == "range":
            range_mode = True
        elif chosen_mode == "reprice_5pct":
            personal_comm_pct = 5.0
    if range_mode and output_path is not None:
        console.print(
            "[yellow]ℹ️  -o/--output is ignored in range mode; "
            "files go to data/outputs/<catalog>/option_2/.[/yellow]"
        )

    if args.batch:
        target_catalogs = find_input_catalogs()
        if not target_catalogs:
            console.print(
                "[bold red]❌ No catalog CSV files found in 'data/inputs/'.[/bold red]"
            )
            console.print(
                "Please place your catalog CSVs in 'data/inputs/' or use the -i flag."
            )
            return 1
    elif input_path is not None:
        if not input_path.exists():
            console.print(
                f"\n[bold red]❌ Error: Input catalog file not found: '{input_path}'[/bold red]"
            )
            console.print(
                "Please ensure the CSV file exists or drop it into data/inputs/."
            )
            return 1
        target_catalogs = [input_path]
    else:
        # No input provided: scan data/inputs/
        catalogs = find_input_catalogs()
        if not catalogs:
            console.print(
                "[bold red]❌ No catalog CSV files found in 'data/inputs/'.[/bold red]"
            )
            console.print(
                "Please place your catalog CSV in 'data/inputs/' or specify with -i/--input."
            )
            return 1

        if len(catalogs) == 1:
            console.print(
                f"[bold cyan]ℹ️  Found 1 catalog in data/inputs/: [green]{catalogs[0].name}[/green]. Auto-selecting.[/bold cyan]"
            )
            target_catalogs = [catalogs[0]]
        else:
            # 2+ catalogs found: interactive picker if TTY, else fallback
            if sys.stdin.isatty():
                chosen = interactive_catalog_picker(catalogs)
                if chosen is None:
                    return 0
                target_catalogs = chosen
            else:
                console.print(
                    f"[bold yellow]⚠️  Non-interactive terminal detected. Auto-selecting first catalog: {catalogs[0].name}[/bold yellow]"
                )
                target_catalogs = [catalogs[0]]

    had_errors = False
    target_platform = args.platform
    if args.alfa_only:
        target_platform = "alfa"
    elif args.digi_only:
        target_platform = "digi"

    for cat in target_catalogs:
        try:
            if range_mode:
                await run_range_pipeline(
                    input_path=cat,
                    concurrency=args.concurrency,
                    verbose=not args.quiet,
                    platform=target_platform,
                )
                continue
            effective_out = output_path if len(target_catalogs) == 1 else None
            await run_pipeline(
                input_path=cat,
                output_path=effective_out,
                concurrency=args.concurrency,
                verbose=not args.quiet,
                use_structured_export=(effective_out is None),
                platform=target_platform,
                personal_comm_pct=personal_comm_pct,
            )
        except Exception as exc:
            console.print(
                f"\n[bold red]❌ Pipeline execution error for '{cat.name}': {exc}[/bold red]"
            )
            had_errors = True

    return 1 if had_errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
