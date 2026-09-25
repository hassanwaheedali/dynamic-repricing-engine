# Production Performance & Anti-Blocking Optimization: Complete Architectural Blueprint

## 1. Asal Bottlenecks & Problem Diagnosis (Root Causes)

Hamare profiling audit ke mutabiq pricing engine script mein darj zail 5 bari rukawaten theen:

| Bottleneck | Root Cause | Asal Nuqsaan (Production Impact) |
| --- | --- | --- |
| **1. Fake Concurrency** | `run_pipeline` ke andar `for idx, row in df.iterrows()` loop laga tha jismein har item par `await process_item_async(...)` hota tha. | Script nominal tor par `concurrency=3` declare karti thi, magar amli tor par strictly **1 item at a time (sequential)** execute ho rahi thi. 25 products 1.5 se 3.5 minute lete thay. |
| **2. 25-Second Timeout Freeze** | Har request ka default timeout `25.0s` hardcoded tha. | Agar network packet drop ho ya bank ka server stall kare, toh script har failed item par **25 se 75 seconds** tak freeze ho jati thi. |
| **3. WAF Burst Detection (`wsarecv`)** | Zero jitter aur bina delay ke back-to-back requests Comverse Global storefront par ja rahi theen. | Cloudflare WAF ne automated burst detect karke HTTP 429 aur socket connection abort (`wsarecv: An established connection was aborted by host`) phenk diya. |
| **4. Redundant Network Traffic** | Ek hi model/query ke liye zero in-memory caching thi. | Agar catalog mein 5 Gree AC thay, toh script ne 5 dafa remote API ko hit karke apna hi rate-limit waste kiya. |
| **5. Terminal Scramble Risk** | Concurrency mein mukhtalif coroutines ek sath terminal par likhti theen. | Rich cards aur panels ke ANSI escape sequences aapas mein overlap (corrupt) hone ka khatra tha. |

---

## 2. Core Architectural Decisions (The 6 Production Pillars)

### Pillar 1: The "T=0 Burst Wave" Prevention via Micro-Staggering
- **Mechanism:** Har product task dispatch ke darmiyan **200ms (0.2s)** ka micro-delay diya jayega:
  ```python
  tasks = []
  for idx, row in df.iterrows():
      tasks.append(process_item_worker(idx, row, semaphore, session_manager, render_lock))
      await asyncio.sleep(0.2)  # Micro-stagger: T=0 burst wave prevention
  results = await asyncio.gather(*tasks)
  ```
- **Math & Performance Proof:** 25 items ke liye total stagger delay sirf $25 \times 0.2\text{s} = \mathbf{5.0\text{ seconds}}$ hoga. 3 parallel workers background mein run karenge aur total run **15-22 seconds** mein finish ho jayega bina kisi WAF block ke.

### Pillar 2: Guaranteed CSV Index Preservation (`_original_idx`)
- **Mechanism:** Parallel execution mein completion order non-deterministic hota hai (Item #3 pehle mukammal ho sakta hai, Item #1 baad mein).
- **Fix:** Har item ke result dictionary mein `_original_idx = idx` retain kiya jayega.
- **Export Sort:** Output CSV banane se pehle records ko `results.sort(key=lambda x: x["_original_idx"])` karke 100% deterministic original sequence par restore kiya jayega, phir `_original_idx` drop karke clean CSV export hogi.

### Pillar 3: Socket Disconnect Detection & Session Recycling (`curl_cffi`)
- **Mechanism:** Jab server se `wsarecv`, `ConnectionResetError`, ya socket abort error aaye, toh client socket pool poison ho jata hai.
- **Fix:** Error interceptor check karega:
  ```python
  err_str = str(e).lower()
  if any(k in err_str for k in ("wsarecv", "connection was aborted", "reset", "closed")):
      # Close broken session and allocate fresh instance
      await session.close()
      await asyncio.sleep(0.5 + random.uniform(0.1, 0.3))
      session = AsyncSession(impersonate="chrome120")
  ```
- Exponential backoff + randomized jitter applied to prevent cascading failures.

### Pillar 4: Strict Cache Poisoning Guard & On-Demand (Lazy) Caching
- **Mechanism:** In-memory query cache `_query_cache: dict[tuple[str, str], list[ScrapedOffer]]` on-demand populate hoga.
- **Strict Guard:** Cache mein data **SIRF TAB** save hoga jab:
  1. HTTP `status_code == 200` ho, aur
  2. Parsed results non-empty valid offers hon.
- **Zero Poisoning:** Timeouts, 429 rate limits, network aborts, ya empty failure states ko **kabhi cache nahi kiya jayega**, taake agla product dobara fresh live fetch kare aur false monopoly (+Rs. 4,000 margin) trigger na ho.

### Pillar 5: Atomic Rich Render Lock & Lean 10.0s Timeout
- Terminal cards ki visual integrity ke liye `asyncio.Lock()` ensure karega ke ek card poora draw ho, phir agla start ho.
- Default request timeout `25.0s` se reduce karke `10.0s` kar diya jayega.

### Pillar 6: Live Telemetry & Active Terminal Retry Badges (No Silent Freezes)
- **Problem:** Jab 10s ka timeout ya backoff delay hota hai, toh khamoshi ki wajah se user ko lagta hai script freeze ho gayi hai.
- **Fix:** Har socket drop, timeout, ya 429 par silent retry ke bajaye foran ek single-line Rich telemetry badge print hoga:
  - `⚠️  [AlfaMall] Connection stall on '{query}' (Attempt {attempt+1}/{max_retries}) — Auto-recovering in {backoff:.1f}s...`
  - `⛔ [DigiMall] Rate-limit (429) on '{query}' — Cooling down {backoff:.1f}s...`
- User ko live confirmation milti rahegi ke engine active hai aur recover kar raha hai.

---

## 3. Phased Implementation Plan

### Phase 1: Scraper Resilience, Stealth & Safe Caching (`pricing_engine/scraper.py`)
- Full modern Chrome 120 browser headers (`sec-ch-ua`, `user-agent`, `accept-encoding`).
- Safe on-demand cache with strict 200 OK + non-empty guard.
- Socket abort detection (`wsarecv`) with session recycling and jittered exponential backoff.
- Rich terminal telemetry badges for live recovery feedback.
- Lean 10.0s timeout.

### Phase 2: Pipeline Micro-Staggering, Index Sorting & Render Lock (`pricing_engine/pipeline.py`)
- Refactor `run_pipeline` to use bounded `asyncio.Semaphore(3)` with 200ms launch stagger.
- Attach `_original_idx` to each worker output and sort prior to CSV write.
- Wrap `render_audit_card` inside `async with render_lock:` for atomic ANSI rendering.

### Phase 3: Unit Testing & Verification
- Unit tests for cache guard (ensuring error responses are not cached).
- Unit tests for CSV index preservation.
- Full test suite run (`pytest -v`) and linter (`ruff check .`).
- Live production benchmark run against input catalog.
