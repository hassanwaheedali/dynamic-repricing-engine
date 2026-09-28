# ADR-003: Autonomous Co-Occurrence Learning, Confidence Gates, and Cloud Sync

## Status
Accepted

## Date
2026-09-28

## Context
When marketplace sellers use informal or natural language synonyms (e.g. using `Glass Door` instead of `GC`), the system must recognize this equivalence dynamically. Hardcoding synonyms in Python code requires developer intervention for every new market phrasing. However, blindly auto-approving any co-occurring phrase risks poisoning the matching engine with seller typos or erroneous listings.

## Decision
Implement a **Statistical Co-Occurrence Miner** with a strict **Multi-Seller Confirmation Gate** and cloud persistence via Supabase:

### 1. Passive Title Observation
During standard pricing sweeps, every accepted candidate's residual tokens are paired with the target's residual tokens:
$$\text{Observation} = (\text{Brand}, \text{AnchorModel}, \text{TargetResidual}, \text{CandidateResidual})$$

### 2. Multi-Seller Confirmation Gate ($\ge 3$ Distinct Vendors)
- **Candidate State**: An observed synonym or mapping is held as `CANDIDATE` if observed $<3$ times.
- **Approved State**: An equivalence is automatically promoted to `APPROVED` only when $\ge 3$ distinct, verified seller listings confirm the exact same mapping with zero contradictory signals.
- **Conflict Quarantine**: If two listings provide contradictory mappings for the same anchor (e.g. one seller associates `GC` with `Glass Cover` and another with `Grey Color`), the token is immediately quarantined with `status = 'CONFLICT'` and flagged for audit.

### 3. Cloud Synchronization & Zero-Latency Caching
- **Supabase Cloud PostgreSQL**: Serves as the durable, append-only source of truth (`capacity_registry` and `learning_observations`).
- **In-Memory Local Mirror**: The approved registry is pre-loaded at startup into an in-memory dictionary, ensuring zero-latency ($<0.01$ms) lookups during high-speed repricing loops.
- **Graceful Offline Fallback**: If Supabase credentials are missing or the network drops, the engine falls back to local memory without halting or crashing the pricing sweep.

## Alternatives Considered

### 1. Instant Auto-Approval on First Sight
- Pros: Immediate learning.
- Cons: A single seller typo or fraudulent listing permanently pollutes the database.
- Rejected: Unsafe for production financial calculations.

### 2. Manual Human Review for All Discovered Terms
- Pros: 100% human-verified.
- Cons: High operational burden, defeats the purpose of autonomous repricing.
- Rejected: Doesn't scale.

## Consequences
- The repricing engine gets smarter with every catalog run without code changes.
- Multi-seller confirmation prevents hallucinations and seller typos from corrupting matches.
- Full auditability via append-only observation logs in Supabase.
