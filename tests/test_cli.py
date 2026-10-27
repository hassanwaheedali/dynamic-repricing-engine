"""Unit and integration tests for index.py CLI and catalog picker."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from index import (
    find_input_catalogs,
    interactive_catalog_picker,
    main,
    parse_args,
)


def test_find_input_catalogs(tmp_path: Path) -> None:
    (tmp_path / "Gree_AC.csv").write_text("dummy", encoding="utf-8")
    (tmp_path / "Haier_Washers.csv").write_text("dummy", encoding="utf-8")
    (tmp_path / "template.csv").write_text("dummy", encoding="utf-8")
    (tmp_path / "template_reference.csv").write_text("dummy", encoding="utf-8")
    (tmp_path / ".gitkeep").write_text("", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("dummy", encoding="utf-8")

    catalogs = find_input_catalogs(tmp_path)

    assert len(catalogs) == 2
    names = [c.name for c in catalogs]
    assert "Gree_AC.csv" in names
    assert "Haier_Washers.csv" in names
    assert "template.csv" not in names


def test_interactive_catalog_picker_selection(tmp_path: Path) -> None:
    cat1 = tmp_path / "cat1.csv"
    cat2 = tmp_path / "cat2.csv"
    catalogs = [cat1, cat2]

    # Select single item "1"
    with patch("builtins.input", return_value="1"):
        res = interactive_catalog_picker(catalogs)
        assert res == [cat1]

    # Select all "A"
    with patch("builtins.input", return_value="A"):
        res = interactive_catalog_picker(catalogs)
        assert res == catalogs

    # Quit "Q"
    with patch("builtins.input", return_value="q"):
        res = interactive_catalog_picker(catalogs)
        assert res is None

    # Invalid input
    with patch("builtins.input", return_value="99"):
        res = interactive_catalog_picker(catalogs)
        assert res is None


def test_parse_args_defaults() -> None:
    with patch("sys.argv", ["index.py"]):
        args = parse_args()
        assert args.input is None
        assert args.output is None
        assert args.batch is False
        assert args.concurrency == 3
        assert args.quiet is False


def test_parse_args_explicit() -> None:
    with patch(
        "sys.argv",
        [
            "index.py",
            "-i",
            "custom_input.csv",
            "-o",
            "custom_output.csv",
            "-c",
            "5",
            "-q",
        ],
    ):
        args = parse_args()
        assert str(args.input) == "custom_input.csv"
        assert str(args.output) == "custom_output.csv"
        assert args.concurrency == 5
        assert args.quiet is True


def test_main_with_explicit_missing_file() -> None:
    with patch("sys.argv", ["index.py", "-i", "definitely_non_existent_file.csv"]):
        code = asyncio.run(main())
        assert code == 1


def test_main_with_explicit_valid_file(tmp_path: Path) -> None:
    test_csv = tmp_path / "test.csv"
    test_csv.write_text("Brand,Name,Net Price\n", encoding="utf-8")

    with (
        patch("sys.argv", ["index.py", "-i", str(test_csv)]),
        patch("index.run_pipeline", new_callable=AsyncMock) as mock_pipe,
    ):
        code = asyncio.run(main())
        assert code == 0
        mock_pipe.assert_called_once()


def test_parse_args_range_flag() -> None:
    with patch("sys.argv", ["index.py"]):
        assert parse_args().range_only is False
    for flag in ("-r", "--range-only"):
        with patch("sys.argv", ["index.py", flag]):
            assert parse_args().range_only is True


def test_main_range_only_uses_range_pipeline(tmp_path: Path) -> None:
    test_csv = tmp_path / "models.csv"
    test_csv.write_text("Brand,Name\nGree,GS-12XPH32\n", encoding="utf-8")

    with (
        patch("sys.argv", ["index.py", "-r", "-i", str(test_csv)]),
        patch("index.run_range_pipeline", new_callable=AsyncMock) as mock_range,
        patch("index.run_pipeline", new_callable=AsyncMock) as mock_pipe,
    ):
        code = asyncio.run(main())
    assert code == 0
    mock_range.assert_called_once()
    mock_pipe.assert_not_called()


def test_prompt_run_mode_choices() -> None:
    from index import prompt_run_mode

    for answer, expected in (("1", "reprice"), ("", "reprice"), ("2", "range"), ("r", "range")):
        with patch("builtins.input", return_value=answer):
            assert prompt_run_mode() == expected
    with patch("builtins.input", return_value="q"):
        assert prompt_run_mode() is None


def test_main_interactive_mode_prompt_selects_range(tmp_path: Path) -> None:
    test_csv = tmp_path / "models.csv"
    test_csv.write_text("Brand,Name\nGree,GS-12XPH32\n", encoding="utf-8")

    with (
        patch("sys.argv", ["index.py", "-i", str(test_csv)]),
        patch("sys.stdin.isatty", return_value=True),
        patch("index.prompt_run_mode", return_value="range"),
        patch("index.run_range_pipeline", new_callable=AsyncMock) as mock_range,
    ):
        assert asyncio.run(main()) == 0
    mock_range.assert_called_once()


def test_parse_args_alfa_flag() -> None:
    """Verify --alfa and --alfa-only flags set alfa_only True, and default is False."""
    with patch("sys.argv", ["index.py"]):
        args = parse_args()
        assert args.alfa_only is False
        assert args.platform == "all"

    with patch("sys.argv", ["index.py", "--alfa"]):
        args = parse_args()
        assert args.alfa_only is True

    with patch("sys.argv", ["index.py", "--alfa-only"]):
        args = parse_args()
        assert args.alfa_only is True


def test_main_alfa_flag_passes_platform_alfa(tmp_path: Path) -> None:
    """Verify --alfa flag passes platform='alfa' to run_pipeline."""
    test_csv = tmp_path / "test.csv"
    test_csv.write_text("Brand,Name,Net Price\nGree,GS-18AITH21W,100000\n", encoding="utf-8")

    with (
        patch("sys.argv", ["index.py", "-i", str(test_csv), "--alfa"]),
        patch("index.run_pipeline", new_callable=AsyncMock) as mock_pipe,
    ):
        assert asyncio.run(main()) == 0
        mock_pipe.assert_called_once()
        assert mock_pipe.call_args.kwargs.get("platform") == "alfa"

