# Implementation Plan: Sweet-Spot Profit Capping with 10% Default Tier Integrity

## Overview
Implement configurable sweet-spot profit capping (default target: ~Rs. 10,000) for DigiMall and AlfaMall so that inflated competitor prices (e.g. Scroll-N-Shop at Rs. 489,999) do not result in excessive, uncompetitive margins (+Rs. 20,416) that deter buyers. The sweet-spot price must remain strictly bounded within Tier 1 (10.00% Default Tier) whenever the competitor is viable under 10%, ensuring Commission status remains "10.00% Default Tier" and psychological endings (.899 / .999) are maintained.

---

## Architectural & Mathematical Decisions

1. **Five-Tier Adaptive Dynamic Gap Strategy (ADGS)**:
   - Gap = Competitor Price - Floor.
   - **Tier 1 (4 Zeros: Gap >= 10,000)**: Option A sweet spot capped around ~Rs. 10,000 profit (e.g. Item #1 selling at Rs. 478,899, profit: +Rs. 10,296, 10.00% Default Tier).
   - **Tier 2 (3 Zeros: 2,000 <= Gap < 10,000)**: 50% split average with min Rs. 1,000 buffer above floor.
   - **Tier 3 (Moderate Gap: 1,500 <= Gap < 2,000)**: Rs. 500 customer discount (competitor - 500), min Rs. 1,000 profit buffer (e.g. 1800 gap -> Rs. 500 discount, Rs. 1,300 profit).
   - **Tier 4 (Small-Medium Gap: 800 <= Gap < 1,500)**: Rs. 200 undercut (e.g. 1200, 1000, 900, 800) for visible discount without dropping below floor.
   - **Tier 5 (Tight Gap: Gap < 800)**: Closest Rs. 100 undercut right below competitor while strictly preserving +Rs. 500 minimum profit floor.

---

## Task List

### Phase 1: Engine Evaluator Sweet-Spot Math
- [ ] **Task 1: Add Dynamic Sweet-Spot Ceiling in `evaluator.py`**
  - Ensure `max_ceiling_10` is calculated as $\max((\text{cost\_base} + \text{target\_cap}) / 0.92, \text{floor\_digi\_10} + 250)$ when target cap is specified.
  - Preserve `effective_comm = "10.00%"` and `status = "Safe Win (10% Tier)"`.
  - Format strategy reason: `"Filtered sub-floor offers. Competitor {vendor} (Rs. {price}) price is inflated. Capped at sweet-spot price Rs. {final_p} (+Rs. {profit} profit) for sales conversion."`

### Phase 2: Unit Testing & Verification
- [ ] **Task 2: Add TDD Test for Item #1 Sweet Spot in `tests/test_evaluator.py`**
  - Verify Item #1 with Scroll-N-Shop (489,999) prices at `478,899`.
  - Assert `result.status == "Safe Win (10% Tier)"`.
  - Assert `result.effective_comm == "10.00%"`.
  - Assert `result.real_profit == 10296` (sweet spot ~10k, not 20k).
- [ ] **Task 3: Update `tests/test_pipeline.py` & Pipeline Integration**
  - Ensure pipeline passes `max_profit_cap=10000.0` or configurable sweet spot.
  - Verify all 37+ tests pass.

### Phase 3: Visual Inspection & Terminal Audit
- [ ] **Task 4: Terminal Audit Verification**
  - Run `render_audit_card` for Item #1 and Item #2.
  - Confirm Item #1 shows `Target Undercut (10% Viable)`, `10.00% Default Tier`, `Final Price: Rs. 478,899`, `Profit: +Rs. 10,296`.
  - Confirm Item #2 shows `Target Undercut (8% Viable)`, `8.00% Emergency Switch`, `Final Price: Rs. 165,899`, `Profit: +Rs. 1,649`.

---

## Risks & Mitigations
| Risk | Impact | Mitigation |
|---|---|---|
| Cap drops below 10% Floor | High (Causes false 8% emergency switch) | Invariant: `max_ceiling_10 >= floor_digi_10 + 250` ensures price is always in Tier 1 |
| Small products (<100k) cap too high | Low | On small items, competitor undercut `price - 100` is naturally below 10k profit |
