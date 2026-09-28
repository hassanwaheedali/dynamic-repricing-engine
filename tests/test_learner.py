import asyncio
from unittest.mock import AsyncMock

from pricing_engine.learner import (
    AutonomousLearner,
    is_valid_residual_token,
    is_valid_synonym_candidate,
    normalize_merchant_name,
)


def test_is_valid_residual_token_rejects_digits_and_metrics() -> None:
    """Residual tokens can NEVER contain numbers or unit specifications (Reviewer Guard 2)."""
    # Numbers and mixed alphanumeric metric leakage must be rejected
    assert is_valid_residual_token("12KG") is False
    assert is_valid_residual_token("12-KILO") is False
    assert is_valid_residual_token("1.5T") is False
    assert is_valid_residual_token("120-826S6") is False
    assert is_valid_residual_token("30") is False

    # Standard unit tokens must be rejected
    assert is_valid_residual_token("KG") is False
    assert is_valid_residual_token("TON") is False
    assert is_valid_residual_token("INCH") is False

    # Single-letter junk must be rejected
    assert is_valid_residual_token("A") is False
    assert is_valid_residual_token("") is False

    # Legitimate cosmetic/feature tokens must be accepted
    assert is_valid_residual_token("GC") is True
    assert is_valid_residual_token("GLASS DOOR") is True
    assert is_valid_residual_token("PILLOW DRUM") is True


def test_normalize_merchant_name_prevents_sybil_variations() -> None:
    """Merchant normalization prevents slight title variations from acting as distinct sellers (Reviewer Guard 3)."""
    m1 = normalize_merchant_name("Mega Store")
    m2 = normalize_merchant_name("MegaStore")
    m3 = normalize_merchant_name("Mega-Store!")
    assert m1 == m2 == m3 == "megastore"


def test_is_valid_synonym_candidate_enforces_symmetry_and_ratio() -> None:
    """Enforces non-empty symmetry and prevents multi-word fluff asymmetry (Reviewer Guard 6)."""
    # Empty strings cannot be mapped
    assert is_valid_synonym_candidate("", "PILLOW DRUM") is False
    assert is_valid_synonym_candidate("GC", "") is False

    # Asymmetry ratio guard: 1 word vs 4 words is fluff, not a variant synonym
    assert is_valid_synonym_candidate("GC", "GLASS DOOR PILLOW DRUM SUPER SILENT") is False

    # Valid symmetric 1-to-1 or 1-to-2 phrases are accepted
    assert is_valid_synonym_candidate("GC", "GLASS DOOR") is True
    assert is_valid_synonym_candidate("PL", "PILLOW DRUM") is True


def test_autonomous_learner_buffers_valid_observations_in_memory() -> None:
    """Observations are buffered in memory and reject invalid/empty categories (Reviewer Guards 1 & 4)."""
    learner = AutonomousLearner()
    learner.clear_buffer()

    # Missing category is rejected (Reviewer Guard 1)
    rejected = learner.buffer_observation(
        brand="Haier",
        category="",  # Empty category
        anchor_model="120-826S6",
        target_residual="GC",
        candidate_residual="GLASS DOOR",
        vendor_name="Mega Store",
        raw_title="Haier 120-826S6 Glass Door",
    )
    assert rejected is False
    assert learner.buffer_size == 0

    # Valid category and tokens are buffered
    accepted = learner.buffer_observation(
        brand="Haier",
        category="WASHING_MACHINE",
        anchor_model="120-826S6",
        target_residual="GC",
        candidate_residual="GLASS DOOR",
        vendor_name="Mega Store",
        raw_title="Haier 120-826S6 Glass Door",
    )
    assert accepted is True
    assert learner.buffer_size == 1


def test_autonomous_learner_bulk_flushes_to_supabase() -> None:
    """Bulk flush sends single batch POST to Supabase client without N+1 calls (Reviewer Guard 4)."""

    async def _test() -> None:
        learner = AutonomousLearner()
        learner.clear_buffer()

        learner.buffer_observation(
            brand="Haier",
            category="WASHING_MACHINE",
            anchor_model="120-826S6",
            target_residual="GC",
            candidate_residual="GLASS DOOR",
            vendor_name="Seller A",
            raw_title="Haier 120-826S6 Glass Door",
        )
        learner.buffer_observation(
            brand="Haier",
            category="WASHING_MACHINE",
            anchor_model="120-826S6",
            target_residual="GC",
            candidate_residual="GLASS COVER",
            vendor_name="Seller B",
            raw_title="Haier 120-826S6 Glass Cover",
        )

        mock_client = AsyncMock()
        mock_client.record_observations_batch.return_value = 2

        recorded = await learner.flush_observations(mock_client)
        assert recorded == 2
        assert mock_client.record_observations_batch.call_count == 1
        assert learner.buffer_size == 0

    asyncio.run(_test())


def test_autonomous_learner_promotes_candidates_with_three_distinct_vendors() -> None:
    """Candidates are promoted to APPROVED only when >= 3 distinct normalized merchants confirm (Reviewer Guard 3)."""
    learner = AutonomousLearner()

    # Observations from 3 distinct vendors for the same pair
    observations = [
        {"vendor_name": "Mega Store", "normalized_merchant": "megastore"},
        {"vendor_name": "Daraz Mall", "normalized_merchant": "darazmall"},
        {"vendor_name": "Lahore Electronics", "normalized_merchant": "lahoreelectronics"},
    ]

    distinct_merchants = learner.count_distinct_merchants(observations)
    assert distinct_merchants == 3
    assert learner.is_consensus_reached(distinct_merchants, threshold=3) is True

    # 3 listings from the SAME vendor should count as only 1 merchant
    sybil_observations = [
        {"vendor_name": "Mega Store", "normalized_merchant": "megastore"},
        {"vendor_name": "MegaStore", "normalized_merchant": "megastore"},
        {"vendor_name": "Mega-Store Official", "normalized_merchant": "megastoreofficial"},
    ]
    assert learner.count_distinct_merchants(sybil_observations) == 2
    assert (
        learner.is_consensus_reached(
            learner.count_distinct_merchants(sybil_observations), threshold=3
        )
        is False
    )


def test_learner_multi_catalog_real_world_washing_machines_and_appliances() -> None:
    """Test learning across real items from Stock Holding Report and Haier Washing Machines."""
    learner = AutonomousLearner()
    learner.clear_buffer()

    # 1. Dawlance DWT-1165 PL (Pillow Drum)
    assert (
        learner.buffer_observation(
            brand="Dawlance",
            category="WASHING_MACHINE",
            anchor_model="DWT-1165",
            target_residual="PL",
            candidate_residual="PILLOW DRUM",
            vendor_name="AlfaMall Partner A",
            raw_title="Dawlance DWT-1165 Pillow Drum Automatic Washing Machine",
        )
        is True
    )

    # 2. Dawlance DWT-14470 ES (Energy Saver)
    assert (
        learner.buffer_observation(
            brand="Dawlance",
            category="WASHING_MACHINE",
            anchor_model="DWT-14470",
            target_residual="ES",
            candidate_residual="ENERGY SAVER",
            vendor_name="DigiMall Store B",
            raw_title="Dawlance DWT-14470 Energy Saver Top Load",
        )
        is True
    )

    # 3. Dawlance DWT-11671 FLT (Flush Lid Top)
    assert (
        learner.buffer_observation(
            brand="Dawlance",
            category="WASHING_MACHINE",
            anchor_model="DWT-11671",
            target_residual="FLT",
            candidate_residual="FLUSH LID",
            vendor_name="Lahore Appliances",
            raw_title="Dawlance DWT-11671 Flush Lid Washing Machine",
        )
        is True
    )

    # 4. Haier Front Load HW 105-BD14376PGU1 (Direct Motion / Belt Drive)
    assert (
        learner.buffer_observation(
            brand="Haier",
            category="FRONT_LOAD_WASHING_MACHINE",
            anchor_model="105-BD14376PGU1",
            target_residual="DM",
            candidate_residual="DIRECT MOTION",
            vendor_name="Official Haier Flagship",
            raw_title="Haier 105-BD14376PGU1 Front Load Direct Motion",
        )
        is True
    )

    # 5. Microwave Oven touch panel (from M/O category in Stock Holding Report)
    assert (
        learner.buffer_observation(
            brand="Dawlance",
            category="MICROWAVE_OVEN",
            anchor_model="DW-MD7",
            target_residual="TP",
            candidate_residual="TOUCH PANEL",
            vendor_name="Metro Electronics",
            raw_title="Dawlance DW-MD7 Touch Panel Microwave Oven",
        )
        is True
    )

    assert learner.buffer_size == 5


def test_learner_blocks_anchor_and_metric_leakage_from_stock_sheet_models() -> None:
    """Validate that actual anchors and metrics from the Stock Holding Report can NEVER be learned as residuals."""
    learner = AutonomousLearner()
    learner.clear_buffer()

    real_anchors_and_metrics = [
        ("DWT-1165", "PL"),  # Real anchor DWT-1165 cannot be target_residual
        ("PL", "DWT-1165"),  # Real anchor cannot be candidate_residual
        ("11671", "FLT"),  # Digits from DWT-11671
        ("FTV60AXV1", "NORMAL"),  # Daikin AC model
        ("1088", "INSECT"),  # Anex 1088 model
        ("12KG", "10KG"),  # Capacity leakage
        ("2.0TON", "1.5TON"),  # Tonnage leakage
        ("3FT", "AIR CURTAIN"),  # Air curtain dimension
    ]

    for target_res, cand_res in real_anchors_and_metrics:
        buffered = learner.buffer_observation(
            brand="Dawlance",
            category="APPLIANCE",
            anchor_model="TEST-MODEL",
            target_residual=target_res,
            candidate_residual=cand_res,
            vendor_name="Sample Vendor",
            raw_title="Sample Title",
        )
        assert buffered is False, f"Failed: ({target_res}, {cand_res}) should have been rejected!"

    assert learner.buffer_size == 0


def test_learner_cross_category_polysemy_isolation_across_catalogs() -> None:
    """Ensure distinct categories in the stock sheet cannot contaminate each other's synonyms."""
    learner = AutonomousLearner()
    learner.clear_buffer()

    # 'GC' in WASHING_MACHINE = Glass Cover / Glass Door
    wm_ok = learner.buffer_observation(
        brand="Haier",
        category="WASHING_MACHINE",
        anchor_model="120-826S6",
        target_residual="GC",
        candidate_residual="GLASS DOOR",
        vendor_name="Vendor 1",
        raw_title="Haier 120-826S6 Glass Door Washing Machine",
    )
    assert wm_ok is True

    # 'GC' in REFRIGERATOR = Glass Chrome
    rf_ok = learner.buffer_observation(
        brand="Dawlance",
        category="REFRIGERATOR",
        anchor_model="9170",
        target_residual="GC",
        candidate_residual="GLASS CHROME",
        vendor_name="Vendor 2",
        raw_title="Dawlance 9170 Glass Chrome Refrigerator",
    )
    assert rf_ok is True

    # Check that both are buffered with strict isolated categories
    assert learner.buffer_size == 2
    cats = {obs["category"] for obs in learner._buffer}
    assert cats == {"WASHING_MACHINE", "REFRIGERATOR"}
