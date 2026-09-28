-- Supabase Cloud PostgreSQL Schema: Autonomous Graph Memory & Learning Registry
-- Enterprise Dynamic Repricing Engine (Category-Bounded & Sybil-Guarded)

-- 1. Capacity Registry
-- Maps brand-specific cooling/washing capacity codes to standardized units (e.g. Dawlance 30 -> 1.5T)
CREATE TABLE IF NOT EXISTS capacity_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand VARCHAR(64) NOT NULL,
    code VARCHAR(32) NOT NULL,
    tonnage VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'APPROVED', -- 'APPROVED', 'CANDIDATE', 'QUARANTINED'
    occurrences INT NOT NULL DEFAULT 1,
    confidence NUMERIC(4, 3) NOT NULL DEFAULT 1.000,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_capacity_brand_code UNIQUE (brand, code)
);

CREATE INDEX IF NOT EXISTS idx_capacity_lookup ON capacity_registry (brand, code);
CREATE INDEX IF NOT EXISTS idx_capacity_status ON capacity_registry (status);

-- 2. Synonym Registry (Reviewer Guard 1: Strict Category-Bounded Polysemy Isolation)
-- Discovered equivalence pairs (e.g. 'GC' <=> 'Glass Door') bounded to (brand, category)
CREATE TABLE IF NOT EXISTS synonym_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand VARCHAR(64) NOT NULL,
    category VARCHAR(64) NOT NULL,
    tag VARCHAR(64) NOT NULL,
    alias VARCHAR(128) NOT NULL,
    occurrences INT NOT NULL DEFAULT 1,
    distinct_vendors INT NOT NULL DEFAULT 1,
    status VARCHAR(32) NOT NULL DEFAULT 'CANDIDATE', -- 'APPROVED', 'CANDIDATE', 'CONFLICT'
    confidence NUMERIC(4, 3) NOT NULL DEFAULT 0.500,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_synonym_pair UNIQUE (brand, category, tag, alias)
);

CREATE INDEX IF NOT EXISTS idx_synonym_lookup ON synonym_registry (brand, category, tag);
CREATE INDEX IF NOT EXISTS idx_synonym_status ON synonym_registry (status);

-- 3. Learning Observations (Reviewer Guards 1, 2, 3: Sybil Protection & Normalization)
-- Append-only raw market observation audit log with normalized merchant uniqueness constraint
CREATE TABLE IF NOT EXISTS learning_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand VARCHAR(64) NOT NULL,
    category VARCHAR(64) NOT NULL,
    anchor_model VARCHAR(64) NOT NULL DEFAULT '',
    target_residual VARCHAR(64) NOT NULL,
    candidate_residual VARCHAR(128) NOT NULL,
    vendor_name VARCHAR(128) NOT NULL,
    normalized_merchant VARCHAR(64) NOT NULL,
    raw_title TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_merchant_observation UNIQUE (brand, category, anchor_model, target_residual, candidate_residual, normalized_merchant)
);

CREATE INDEX IF NOT EXISTS idx_obs_distinct_vendors ON learning_observations (brand, category, target_residual, candidate_residual);
CREATE INDEX IF NOT EXISTS idx_obs_anchor ON learning_observations (brand, anchor_model);

-- 4. Seed Canonical Seed Capacities (Idempotent Upsert)
INSERT INTO capacity_registry (brand, code, tonnage, status, occurrences, confidence) VALUES
    ('DAWLANCE', '10', '0.75', 'APPROVED', 10, 1.000),
    ('DAWLANCE', '15', '1', 'APPROVED', 10, 1.000),
    ('DAWLANCE', '20', '1.25', 'APPROVED', 10, 1.000),
    ('DAWLANCE', '30', '1.5', 'APPROVED', 10, 1.000),
    ('DAWLANCE', '45', '2', 'APPROVED', 10, 1.000),
    ('UNIVERSAL', '09', '0.75', 'APPROVED', 10, 1.000),
    ('UNIVERSAL', '9', '0.75', 'APPROVED', 10, 1.000),
    ('UNIVERSAL', '12', '1', 'APPROVED', 10, 1.000),
    ('UNIVERSAL', '18', '1.5', 'APPROVED', 10, 1.000),
    ('UNIVERSAL', '24', '2', 'APPROVED', 10, 1.000),
    ('UNIVERSAL', '28', '2.5', 'APPROVED', 10, 1.000),
    ('UNIVERSAL', '30', '2.5', 'APPROVED', 10, 1.000),
    ('UNIVERSAL', '36', '3', 'APPROVED', 10, 1.000),
    ('UNIVERSAL', '48', '4', 'APPROVED', 10, 1.000)
ON CONFLICT (brand, code) DO NOTHING;

-- 5. Seed Canonical Seed Synonyms (Idempotent Upsert)
INSERT INTO synonym_registry (brand, category, tag, alias, occurrences, distinct_vendors, status, confidence) VALUES
    ('HAIER', 'WASHING_MACHINE', 'GC', 'GLASS DOOR', 5, 5, 'APPROVED', 1.000),
    ('HAIER', 'WASHING_MACHINE', 'GC', 'GLASS COVER', 5, 5, 'APPROVED', 1.000),
    ('HAIER', 'WASHING_MACHINE', 'PL', 'PILLOW DRUM', 5, 5, 'APPROVED', 1.000)
ON CONFLICT (brand, category, tag, alias) DO NOTHING;

-- 6. Enable Row Level Security (RLS)
ALTER TABLE capacity_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE synonym_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_observations ENABLE ROW LEVEL SECURITY;

-- 7. RLS Policies for service_role and anon/authenticated
DO $$
BEGIN
    DROP POLICY IF EXISTS "Allow public read on approved capacity" ON capacity_registry;
    DROP POLICY IF EXISTS "Allow public read on approved synonyms" ON synonym_registry;
    DROP POLICY IF EXISTS "Allow service_role all on capacity" ON capacity_registry;
    DROP POLICY IF EXISTS "Allow service_role all on synonyms" ON synonym_registry;
    DROP POLICY IF EXISTS "Allow service_role all on observations" ON learning_observations;
    DROP POLICY IF EXISTS "Allow public insert on observations" ON learning_observations;
EXCEPTION WHEN OTHERS THEN
    NULL;
END $$;

CREATE POLICY "Allow public read on approved capacity" ON capacity_registry
    FOR SELECT USING (status = 'APPROVED');

CREATE POLICY "Allow public read on approved synonyms" ON synonym_registry
    FOR SELECT USING (status = 'APPROVED');

CREATE POLICY "Allow service_role all on capacity" ON capacity_registry
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Allow service_role all on synonyms" ON synonym_registry
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Allow service_role all on observations" ON learning_observations
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================================================
-- SECURITY NOTICE (Principle of Least Privilege & STRIDE Hardening):
-- 1. `learning_observations` is an internal telemetry and model-learning ledger.
--    No public (anon) access is permitted. Only `service_role` (backend engine)
--    can read, insert, or prune observation records.
-- 2. `capacity_registry` and `synonym_registry` permit public SELECT ONLY for
--    pre-approved entries (`status = 'APPROVED'`). All mutations require `service_role`.
-- ============================================================================

