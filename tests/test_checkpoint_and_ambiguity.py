"""Unit and integration tests for Multi-Variant Conflict Referee and Checkpoint Engine."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pandas as pd

from pricing_engine.checkpoint import (
    compute_row_fingerprint,
    delete_checkpoint,
    detect_dirty_or_pending_rows,
    get_checkpoint_path,
    load_checkpoint,
    merge_records_in_order,
    save_checkpoint,
)
from pricing_engine.matcher import referee_match
from pricing_engine.models import (
    AmbiguousVariantConflict,
    CheckpointState,
    ScrapedOffer,
    ScrapeResult,
)
from pricing_engine.pipeline import run_pipeline
from pricing_engine.scraper import _parse_offers_from_raw_items


def test_multi_variant_ambiguity_detection_on_base_model() -> None:
    """Verify that an un-suffixed base model target flags distinct variants (C, S, E) in base offers."""
    target_base = "Dawlance DWT 255 Automatic Top Load Washing Machine"

    raw_items = [
        {
            "title": "Dawlance DWT 255 C 8.5 Kg Top Load Washing Machine",
            "variant_detail": {"discounted_price": "58,000"},
            "vendor": {"name": "Vendor C"},
        },
        {
            "title": "Dawlance DWT 255 S 8.5 Kg Top Load Washing Machine",
            "variant_detail": {"discounted_price": "52,000"},
            "vendor": {"name": "Vendor S"},
        },
        {
            "title": "Dawlance DWT 255 E 8.5 Kg Top Load Washing Machine",
            "variant_detail": {"discounted_price": "48,000"},
            "vendor": {"name": "Vendor E"},
        },
    ]

    exact, base, d_mod, own = _parse_offers_from_raw_items(
        raw_items, "DWT 255", brand="Dawlance", target_desc=target_base
    )

    assert len(exact) == 0, "Base target must not exact match variant suffixes directly"
    assert len(base) == 3, f"All 3 variants should be recognized as base fallbacks, got {len(base)}"

    # Check detected variants on each offer
    variants = {off.detected_variant for off in base if off.detected_variant}
    assert variants == {"C", "S", "E"}, f"Expected variants {{'C', 'S', 'E'}}, got {variants}"


def test_target_with_explicit_variant_rejects_conflicting_variants() -> None:
    """Verify that a target specifying 'C' directly matches C and strictly collides with S."""
    target_c = "Dawlance DWT 255 C 8.5 Kg Top Load Washing Machine"

    cand_c = "Dawlance DWT 255 C 8.5 Kg Top Load Washing Machine"
    dec_c = referee_match(target_c, cand_c, brand="Dawlance")
    assert dec_c.is_match is True

    cand_s = "Dawlance DWT 255 S 8.5 Kg Top Load Washing Machine"
    dec_s = referee_match(target_c, cand_s, brand="Dawlance")
    assert dec_s.is_match is False
    assert "collision" in dec_s.reason.lower()


def test_dw10600_twin_tub_variant_detection() -> None:
    """Verify dynamic variant detection on Item #13 model stem (DW-10600 W FL vs C FL)."""
    target_base = "Dawlance DW-10600 FL Twin Tub Washing Machine"

    raw_items = [
        {
            "title": "Dawlance DW-10600 W FL Twin Tub Semi Automatic Washing Machine 10",
            "variant_detail": {"discounted_price": "58,499"},
            "vendor": {"name": "Vendor W"},
        },
        {
            "title": "Dawlance DW-10600 C FL Twin Tub Semi Automatic Washing Machine 10",
            "variant_detail": {"discounted_price": "61,400"},
            "vendor": {"name": "Vendor C"},
        },
    ]

    exact, base, _, _ = _parse_offers_from_raw_items(
        raw_items, "DW-10600 FL", brand="Dawlance", target_desc=target_base
    )
    assert len(base) == 2
    detected = sorted(off.detected_variant for off in base if off.detected_variant)
    assert detected == ["C", "W"]


def test_dwt1016_ddm_inv_does_not_trigger_unlogical_variant_conflict() -> None:
    """Verify that models with hardware capabilities (DDM, INV) do not trigger fake variant conflict."""
    target = "Dawlance DWT 1016 DDM INV Prima Automatic Top Load Washing Machine"

    raw_items = [
        {
            "title": "Dawlance DWT 1016 DDM Top Load Washing Machine",
            "variant_detail": {"discounted_price": "108,700"},
            "vendor": {"name": "Vendor A"},
        },
        {
            "title": "Dawlance DWT 1016 Inverter Automatic Washing Machine",
            "variant_detail": {"discounted_price": "109,699"},
            "vendor": {"name": "Vendor B"},
        },
    ]

    exact, base, _, _ = _parse_offers_from_raw_items(
        raw_items, "DWT-1016", brand="Dawlance", target_desc=target
    )
    # Neither candidate has a variant suffix; both omitted one of target's capabilities.
    # Therefore detected_variant must be None on both, preventing unlogical variant prompt!
    variants = [off.detected_variant for off in base if off.detected_variant]
    assert variants == [], (
        f"Hardware capabilities must never be treated as variant suffixes, got {variants}"
    )


def test_compute_row_fingerprint_detects_changes() -> None:
    """Verify row fingerprint detects edits across Brand, Title, and Net Price."""
    base_row = {
        "Brand": "Dawlance",
        "Name": "DW-10600 CB FL Twin Tub",
        "Net Price": "46,500",
        "Profit": 500,
    }
    fp_orig = compute_row_fingerprint(base_row)

    # 1. Comma in net price should produce identical fingerprint to float
    float_price_row = {**base_row, "Net Price": 46500.0}
    assert compute_row_fingerprint(float_price_row) == fp_orig

    # 2. Modifying Title must change fingerprint
    fixed_title_row = {**base_row, "Name": "DW-10600 C FL Twin Tub"}
    assert compute_row_fingerprint(fixed_title_row) != fp_orig

    # 3. Modifying Net Price must change fingerprint
    price_change_row = {**base_row, "Net Price": 44000}
    assert compute_row_fingerprint(price_change_row) != fp_orig

    # 4. Modifying Brand must change fingerprint
    brand_change_row = {**base_row, "Brand": "Haier"}
    assert compute_row_fingerprint(brand_change_row) != fp_orig


def test_checkpoint_save_load_and_detect_dirty_rows(tmp_path: Path) -> None:
    """Verify atomic checkpoint persistence, dirty row detection, and order merge."""
    catalog_file = tmp_path / "test_catalog.csv"
    catalog_file.write_text("dummy", encoding="utf-8")

    # Initial catalog with 3 items
    initial_data = [
        {"Brand": "Dawlance", "Name": "Product A", "Net Price": 30000},
        {"Brand": "Dawlance", "Name": "DW-10600 CB FL", "Net Price": 46500},
        {"Brand": "Dawlance", "Name": "Product C", "Net Price": 60000},
    ]
    df_initial = pd.DataFrame(initial_data)

    fp0 = compute_row_fingerprint(df_initial.iloc[0])
    fp1 = compute_row_fingerprint(df_initial.iloc[1])
    fp2 = compute_row_fingerprint(df_initial.iloc[2])

    # State: row 0 completed, row 1 had typo (completed with notice), row 2 was skipped/pending
    initial_state = CheckpointState(
        catalog_name=catalog_file.name,
        catalog_path=str(catalog_file),
        catalog_mtime=catalog_file.stat().st_mtime,
        total_items=3,
        completed_records={
            0: {"S.NO": 1, "Name": "Product A", "Final Price Alfa": 34999},
            1: {"S.NO": 2, "Name": "DW-10600 CB FL", "Final Price Alfa": 57899},
        },
        row_fingerprints={0: fp0, 1: fp1, 2: fp2},
        pending_indices=[2],  # row 2 was pending
        pending_reasons={2: "AMBIGUOUS_MULTI_VARIANT"},
    )

    save_checkpoint(catalog_file, initial_state, checkpoint_dir=tmp_path)
    loaded = load_checkpoint(catalog_file, checkpoint_dir=tmp_path)
    assert loaded is not None
    assert loaded.total_items == 3
    assert loaded.pending_indices == [2]

    # Now user edits CSV: row 1 fixed to 'DW-10600 C FL'
    updated_data = [
        {"Brand": "Dawlance", "Name": "Product A", "Net Price": 30000},  # UNCHANGED
        {"Brand": "Dawlance", "Name": "DW-10600 C FL", "Net Price": 46500},  # EDITED!
        {"Brand": "Dawlance", "Name": "Product C", "Net Price": 60000},  # STILL PENDING
    ]
    df_updated = pd.DataFrame(updated_data)

    rows_to_run, cached_records = detect_dirty_or_pending_rows(df_updated, loaded)

    # Row 0 must be cached, rows 1 and 2 must be run!
    assert 0 in cached_records
    assert rows_to_run == [1, 2], f"Expected rows [1, 2] to run, got {rows_to_run}"

    # Simulate newly resolved records for 1 and 2
    newly_resolved = {
        1: {"S.NO": 2, "Name": "DW-10600 C FL", "Final Price Alfa": 58299},
        2: {"S.NO": 3, "Name": "Product C", "Final Price Alfa": 68999},
    }

    merged = merge_records_in_order(cached_records, newly_resolved, total_items=3)
    assert len(merged) == 3
    assert [r["S.NO"] for r in merged] == [1, 2, 3]
    assert merged[1]["Name"] == "DW-10600 C FL"
    assert merged[1]["Final Price Alfa"] == 58299

    # Clean up checkpoint
    assert delete_checkpoint(catalog_file, checkpoint_dir=tmp_path) is True
    assert load_checkpoint(catalog_file, checkpoint_dir=tmp_path) is None


def test_pipeline_end_to_end_checkpoint_and_resume(tmp_path: Path) -> None:
    """Verify full end-to-end flow: ambiguity skip -> checkpoint -> CSV edit -> resume -> Option A export."""
    import asyncio

    catalog_file = tmp_path / "dawlance_test.csv"
    catalog_file.write_text(
        "Brand,Name,Net Price\n"
        "Dawlance,Dawlance DWT 255 Automatic Washing Machine,50000\n"
        "Gree,GREE SPLIT AC 12AITH21W-T3,147000\n",
        encoding="utf-8",
    )
    export_dir = tmp_path / "outputs"

    offer_c = ScrapedOffer(
        "Vendor C", 58000.0, False, "Dawlance DWT 255 C 8.5 Kg", detected_variant="C"
    )
    offer_s = ScrapedOffer(
        "Vendor S", 52000.0, False, "Dawlance DWT 255 S 8.5 Kg", detected_variant="S"
    )
    offer_g = ScrapedOffer("Vendor G", 155000.0, False, "Gree Split AC 12AITH21W-T3")

    res_ambig = ScrapeResult(
        offers=[offer_c, offer_s],
        base_offers=[offer_c, offer_s],
        ambiguity_conflict=AmbiguousVariantConflict(
            stem_model="DWT 255",
            detected_variants=["C", "S"],
            variant_offers={"C": [offer_c], "S": [offer_s]},
        ),
    )
    res_gree = ScrapeResult(offers=[offer_g])
    res_empty = ScrapeResult(offers=[])

    async def mock_scrape_alfa(
        session: Any, patterns: Any, target_model: str, **kwargs: Any
    ) -> ScrapeResult:
        if "DWT" in target_model.upper():
            return res_ambig
        return res_gree

    async def mock_scrape_digi(
        session: Any, patterns: Any, target_model: str, **kwargs: Any
    ) -> ScrapeResult:
        return res_empty

    async def _test_flow() -> None:
        # --- Run 1: Headless / Non-interactive (Row 0 must be skipped, Checkpoint must be created) ---
        with (
            patch("pricing_engine.pipeline.scrape_alfamall", side_effect=mock_scrape_alfa),
            patch("pricing_engine.pipeline.scrape_digimall", side_effect=mock_scrape_digi),
        ):
            out_df1 = await run_pipeline(
                input_path=catalog_file,
                output_path=None,
                concurrency=1,
                verbose=False,
                use_structured_export=True,
                export_dir=export_dir,
                resume=True,
            )

        assert len(out_df1) == 2
        # Row 0 was ambiguous -> skipped
        assert out_df1.iloc[0]["Alfa Risk Alert"] == "AMBIGUOUS_VARIANT"
        # Row 1 was clean -> winning or solo
        assert out_df1.iloc[1]["Final Price Alfa"] is not None

        # Verify checkpoint exists
        c_path = get_checkpoint_path(catalog_file)
        assert c_path.is_file(), "Checkpoint file must be generated for pending ambiguous rows"

        # --- User Action: Edit CSV to fix model to 'Dawlance DWT 255 C Automatic Washing Machine' ---
        catalog_file.write_text(
            "Brand,Name,Net Price\n"
            "Dawlance,Dawlance DWT 255 C Automatic Washing Machine,50000\n"
            "Gree,GREE SPLIT AC 12AITH21W-T3,147000\n",
            encoding="utf-8",
        )

        gree_call_count = 0

        async def mock_scrape_alfa_resume(
            session: Any, patterns: Any, target_model: str, **kwargs: Any
        ) -> ScrapeResult:
            nonlocal gree_call_count
            if "12AITH21W" in target_model.upper():
                gree_call_count += 1
                return res_gree
            # Now target has C, exact match!
            return ScrapeResult(offers=[offer_c], base_offers=[offer_c], ambiguity_conflict=None)

        # --- Run 2: Resume! Row 1 (Gree) is cached (0 calls), Row 0 is re-run and resolved! ---
        with (
            patch("pricing_engine.pipeline.scrape_alfamall", side_effect=mock_scrape_alfa_resume),
            patch("pricing_engine.pipeline.scrape_digimall", side_effect=mock_scrape_digi),
        ):
            out_df2 = await run_pipeline(
                input_path=catalog_file,
                output_path=None,
                concurrency=1,
                verbose=False,
                use_structured_export=True,
                export_dir=export_dir,
                resume=True,
            )

        assert len(out_df2) == 2
        # Zero API calls for the cached Gree row!
        assert gree_call_count == 0, "Cached row must not make network calls"

        # Row 0 resolved under Option A!
        assert out_df2.iloc[0]["Final Price Alfa"] is not None
        assert "DWT 255 C" in out_df2.iloc[0]["Name"]
        assert out_df2.iloc[0]["Alfa Risk Alert"] != "AMBIGUOUS_VARIANT"

        # S.NO 1 and 2 in exact order
        assert list(out_df2["S.NO"]) == [1, 2]

        # Checkpoint cleanly deleted
        assert not c_path.is_file(), "Checkpoint must be removed when all rows complete"

    asyncio.run(_test_flow())
