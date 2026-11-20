# Product identity R0 adjudicated controls

Legacy measurements use raw and slot-prepared targets at `dc2996addcbe86e202d1d8b8e02a47b7f21365b0`. The catalog brand is supplied in both paths. The AYS case separately supplies the captured Motorola metadata. “None” means the legacy referee returned no commercial tier. These labels cover identity at the pair boundary. Actual stock, ownership, selected price and notice rendering require separate host replay.

| Source and contrast | Raw tier | Prepared tier | Required outcome | Authority and limits |
| --- | --- | --- | --- | --- |
| Book1 #85, KiaChahiye full `HPU-24CE03/X-IK` | 1 | 2 | Exact on both paths | Full literal model. Own-store exclusion belongs to the host. |
| Book1 #85, Connect Mall `HPU-24CE03/YB(IK)` | 1 | 1 | Ineligible | Explicit opposing qualifier in the Alfa capture, blueprint §17.2. |
| Book1 #85, replace only `/X-IK` with `/KB` | 1 | 2 | Ineligible | Synthetic substitution holding the rest of the input fixed. |
| Book1 #85, captured EZZI digit-zero core | 1 | 2, notice names only `IK` | Base, notice naming omitted `X-IK` | Owner-approved directional omission. Spelling is unchanged. |
| Book1 #89, Digi Home Cart | 1 | 1 | Exact | Captured full-model control with presentation spacing. |
| Book1 #89, Alfa AYS ID `200426182507320405` | None, MODEL_CONFLICT | None, MODEL_CONFLICT | Withhold exact pending sellable-unit and chassis evidence | Literal IDU, Midea in title, Motorola in API. Current reason does not establish the listing is an independently verified conflict. |
| Unigas `50 Gallons Plus` against itself | 1 | 1 | Exact | Controlled title comparison, blueprint §17.3. |
| Unigas 20 against 50, 50 against 20, 30 against 50, 50 against 30 | 1 on all four | 1 on all four | Ineligible in both directions | Controlled substitutions with the same subject and explicit unit. No gallon-to-litre conversion. |
| FINAC stock #100 red Avante, captured black Chrome Hairline seller at Rs. 80,599 | 1 | 1 | Ineligible | Explicit opposing finish after model. Stock row supplies no purchase price. |

Run `.venv\Scripts\python.exe -m pytest tests/test_identity_cutover.py --tb=line -o addopts= -q`. Initial measurement was 17 failed and 7 passed across 24 checks. No test is skipped. A passing AYS non-exact check proves only that the unsafe exact outcome was withheld.

## Fixed-pair replay

From the repository root, run `.venv\Scripts\python.exe -m scripts.identity_baseline --ledger <new-file.jsonl.gz>`. Standard output is the JSON manifest. The ledger uses one JSON object per UTF-8 line. Each source and one-based data row locator identifies the input within the manifest's source hash. Each comparable pair records literal candidate, supplied candidate brand, raw and prepared tier, reason code, basis, missing modifier, notice and detected variant. The report counts blank-title and undeclared-brand records separately. It labels no catalog self-comparison or synthetic quantity change as marketplace ground truth.

Marketplace records reference the original November projections by platform, query, page, one-based rank and listing ID. Repetitions across query pages remain visible. For expenses, stock, seller and deduplication, resolve these records against the input projections and the separate host replay. A captured page supports only the observed search and timestamp. Manually selected queries do not establish production waterfall recall or a complete market.
