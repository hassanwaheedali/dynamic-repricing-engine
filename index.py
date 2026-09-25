"""AlfaMall & DigiMall Dynamic Repricing Automation Engine.

Entrypoint script for high-speed dynamic repricing pipeline.
Executes concurrent price discovery against direct backend search APIs,
applies strict variant matching, and computes winning psychological prices.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from pricing_engine.pipeline import run_pipeline

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

DEFAULT_INPUT_CSV = "Gree_Uploading_on_DigiMall_and_Price.csv"
DEFAULT_OUTPUT_CSV = "final_repriced_uploaded_products.csv"


def parse_args() -> argparse.Namespace:
    """Parse command line options."""
    parser = argparse.ArgumentParser(
        description="Dynamic Repricing Automation Engine for AlfaMall & DigiMall"
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=Path(DEFAULT_INPUT_CSV),
        help=f"Input catalog CSV file (default: {DEFAULT_INPUT_CSV})",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(DEFAULT_OUTPUT_CSV),
        help=f"Output repriced CSV file (default: {DEFAULT_OUTPUT_CSV})",
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
    return parser.parse_args()


async def main() -> int:
    """Main asynchronous pipeline entrypoint."""
    args = parse_args()
    input_path: Path = args.input
    output_path: Path = args.output

    if not input_path.exists():
        print(f"\n❌ Error: Input catalog file not found: '{input_path}'")
        print(
            "Please ensure the input CSV file exists in this directory or specify a valid path with --input."
        )
        return 1

    try:
        await run_pipeline(
            input_path=input_path,
            output_path=output_path,
            concurrency=args.concurrency,
            verbose=not args.quiet,
        )
        return 0
    except Exception as exc:
        print(f"\n❌ Pipeline execution error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
