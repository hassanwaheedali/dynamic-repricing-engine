# Technical Plan: Server Down Detection Guard vs. Legitimate Monopoly

## 1. Problem Statement & Retail Risk Analysis

### Current Flaw (The Ambiguous Empty List)
Currently, in `pricing_engine/scraper.py`, both `scrape_alfamall_search` and `scrape_digimall_search` return `list[ScrapedOffer]`:
- If the remote server responds with `HTTP 200 OK` and finds 0 products matching the query: it returns `[]`.
- If the remote server crashes with `HTTP 500`, drops sockets (`wsarecv`), or times out after 3 retries: it also returns `[]`.

### Business & Commercial Hazard
In `pricing_engine/evaluator.py`, when `offers` is empty, the engine currently defaults to:
$$\text{Scenario 1: Zero competitors in market} \longrightarrow \text{Monopoly Pricing (+Rs. 4,000 profit)}$$

If the portal was actually offline or broken during the run:
1. **Blind Overpricing:** An item that actually has 10 active competitors selling at Rs. 165,000 gets priced at Monopoly rate (e.g. Rs. 185,000).
2. **Sales Drop:** Customers see an inflated price, sales plummet, and store credibility is damaged.
3. **Audit Failure:** The merchant and management are misled into believing there are 0 market competitors when the remote server was simply down.

---

## 2. Architectural Design & Contract Separation

### Core Invariant
$$\text{Legitimate Monopoly} \ne \text{Remote Server Down}$$

To guarantee zero mispricing, the scraper must return a rich, unambiguous data contract:

```python
from dataclasses import dataclass

@dataclass(slots=True)
class ScrapeResult:
    offers: list[ScrapedOffer]
    is_success: bool           # True if HTTP 200 OK was received and parsed
    status_code: int | None    # 200, 500, 429, or None (if network socket drop)
    error_detail: str | None   # Description of network abort, timeout, or 500
```

### Evaluator Decision Matrix

| HTTP Status | Parsed Offers | Engine Evaluation Status | Final Price | Commission | Strategy / Reason |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **200 OK (Valid JSON)** | $\ge 1$ offers | Competitive / Safe Fallback | Calculated Winning Price | 10% or 8% | Undercut viable competitor OR Safe Fallback if loss-makers. |
| **200 OK (Valid JSON)** | 0 offers | **`Monopoly Win`** | Cost Base + Rs. 4,000 | 10.00% | Verified 0 competitors found on live storefront. |
| **500 / 429 / Timeout / HTML Challenge** | 0 offers | **`Server Down / Unreachable`** | `None` (Skip / NaN) | N/A | Server unreachable. Skipped to prevent blind mispricing. |

---

## 3. Hardening Against Critical Edge Cases (The 4 Gaps)

### Gap 1: The "Soft 200 OK" Trap (WAF / HTML Challenge Guard)
- **Problem:** Cloudflare / WAF gateways occasionally return `status_code == 200` with an HTML challenge page (`<!DOCTYPE html>... Just a moment...`) instead of API JSON. If `resp.json()` throws or if the dictionary schema does not contain `"results"`, a naive scraper might treat this as 0 offers and trigger false Monopoly!
- **Solution:** `is_success = True` is set **ONLY IF**:
  1. `resp.status_code == 200`
  2. `resp.json()` parses without `JSONDecodeError`
  3. Response contains expected schema (`results` is a valid list)
  If parsing fails or schema is invalid, set `is_success = False, error_detail = "Invalid JSON / WAF challenge received"`.

### Gap 2: Cache Contract Drift (`_query_cache` Type Alignment)
- **Problem:** `_query_cache` previously cached `list[ScrapedOffer]`. If caller expects `ScrapeResult`, cache hits will fail with `AttributeError: 'list' object has no attribute 'is_success'`.
- **Solution:** 
  1. Update `_query_cache` type annotation and storage to `dict[tuple[str, str], ScrapeResult]`.
  2. Cache hits return a new `ScrapeResult` object wrapping cached offers.
  3. **Strict Zero-Poison Rule:** NEVER cache when `is_success is False`. Only verified 200 OK successes are eligible for caching.

### Gap 3: Asymmetric Platform Isolation (One Live, One Down)
- **Problem:** AlfaMall and DigiMall run independently. If AlfaMall is live and DigiMall is 500 / down (or vice versa), one must not block or corrupt the other.
- **Solution:** Complete decoupling in `pricing_engine/pipeline.py`:
  - Alfa evaluates independently with its own `alfa_scrape_result`.
  - Digi evaluates independently with its own `digi_scrape_result`.
  - If Digi is down, Alfa still sets its proper undercut price (e.g. Rs. 169,299), while Digi cleanly marks `Server Down / Unreachable` with `None`.

### Gap 4: Pandas / CSV Integer Formatting (Zero Float Drift)
- **Problem:** In Python Pandas, introducing `None` or `NaN` into an integer column converts the entire Series to `float64`, exporting prices as `165000.0` instead of `165000`, which breaks third-party catalog uploaders.
- **Solution:** Explicit string formatter in CSV export pipeline:
  ```python
  def format_export_price(val: object) -> str:
      if pd.isna(val) or val is None or val == "":
          return ""
      try:
          return f"{int(float(val)):d}"
      except (ValueError, TypeError):
          return str(val)
  ```
  Guarantees integer representation with zero decimal drift.

---

## 4. Component Breakdown

### Component 1: `pricing_engine/models.py`
- Add `ScrapeResult` dataclass with `offers`, `is_success`, `status_code`, and `error_detail`.

### Component 2: `pricing_engine/scraper.py`
- Update `scrape_alfamall_search` and `scrape_digimall_search` to return `ScrapeResult`.
- Guard against soft 200 OK HTML challenges (validate JSON and `"results"` key).
- Store `ScrapeResult` in `_query_cache` strictly on verified success.

### Component 3: `pricing_engine/evaluator.py`
- Update `evaluate_alfa_pricing` and `evaluate_digi_pricing` signatures to accept `scrape_result: ScrapeResult` (or `offers: list[ScrapedOffer], scrape_success: bool = True, error_detail: str | None = None`).
- If `scrape_success is False`:
  - Return `PlatformPricingResult(final_price=None, real_profit=0, status="Server Down / Unreachable", reason=f"Portal search API unreachable ({error_detail}). Skipped to prevent blind mispricing.")`.
- If `scrape_success is True` and `len(offers) == 0`:
  - Retain legitimate `Monopoly Win` (+Rs. 4,000 profit).

### Component 4: `pricing_engine/pipeline.py`
- Handle `ScrapeResult` independently for AlfaMall and DigiMall.
- Render `[bold red][SERVER DOWN - RETRY LATER][/]` badge on terminal card when status is `Server Down / Unreachable`.
- Export cleanly formatted integer prices via `format_export_price` to prevent float drift in CSV.

---

## 5. Test Verification & Safety Plan

1. **Unit Test: True Monopoly (200 OK with 0 results)**
   - Mock scraper returning `is_success=True`, `offers=[]`.
   - Assert `status == "Monopoly Win"`, `final_price` calculated with +4,000 profit.
2. **Unit Test: Server Down (500 Internal Server Error)**
   - Mock scraper returning `is_success=False`, `status_code=500`.
   - Assert `status == "Server Down / Unreachable"`, `final_price is None`, reason cites 500 error.
3. **Unit Test: Soft 200 OK (WAF HTML Challenge)**
   - Mock response returning 200 OK with HTML string (`<!DOCTYPE html>`).
   - Assert `is_success=False`, `status == "Server Down / Unreachable"`.
4. **Unit Test: Asymmetric Failure Isolation**
   - Mock AlfaMall 200 OK and DigiMall 500 Server Error on same product.
   - Assert Alfa gets valid final price, Digi gets `None` and Server Down status.
5. **Unit Test: CSV Integer Formatting (No Float Drift)**
   - Verify CSV export formatting produces `"165000"` (not `"165000.0"`) even when other rows have `None`.
6. **Regression Safety:**
   - All 52 existing unit tests must remain 100% green.
