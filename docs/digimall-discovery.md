# DigiMall model-first discovery

DigiMall relevance-ranked search now has its own query and pagination policy.
AlfaMall retains its existing search and early-exit behavior. Financial formulas,
commission rates, shipping and profit floors are unchanged.

## Using it

Existing CLI options work without additional flags:

```console
python index.py -i "path/to/catalog.csv" -p digi
python index.py -i "path/to/catalog.csv" -p digi -r
python index.py -i "path/to/catalog.csv" -p digi -m 5
```

Catalogs must supply a valid Brand and a usable model. Missing model rows receive
a failed discovery result instead of a guessed-brand or brand-only search.

The engine searches the extracted model first. If the query's required pages contain
no exact in-stock external match, it tries a distinct separator representation and
then the first distinct brandless numeric stem from the existing Tier 2 generator.
There are at most three query attempts per explicit model branch. Broader retrieval
never weakens the original product's brand, model, capacity or variant validation.

Every query fetches 100 items/page: one page through count 100, two through 200,
three for larger counts. Compatible/viable sellers and missing target-brand results
do not stop required pagination. Later pages run concurrently under a shared limit
equal to CLI concurrency. Per-run raw-page caching and in-flight sharing eliminate
identical HTTP requests while still validating each product separately.

Compatible offers are deduplicated and sorted locally. The lowest five are retained
as a shortlist; the full pool remains available for above-floor alternatives and
observed maximum/count calculations.

## Reading the results

`Digi Discovery Coverage` and `Digi Discovery Detail` are exported in CSV and Excel
and displayed in the terminal. Existing risk-alert columns remain at the end.

The terminal audit uses a short summary, for example `3 searches | 9/9 pages checked |
0 compatible sellers | Scan limit reached`. Raw per-query/page detail stays in
`Digi Discovery Detail` exports. Successful capped scans with no compatible offers
use existing monopoly pricing with a Not Found / observed SOLO label, never a timeout label. Actual failed requests
show retry progress and a final retrieval-failed notice; default request timeouts
increase from 15 to 20 to 25 seconds across the three attempts.

| Coverage | Meaning |
|---|---|
| COMPLETE | Required pages of the selected query policy were inspected |
| CAPPED | More than 300 advertised results; only pages 1–3 inspected |
| UNKNOWN | Reliable initial result count unavailable |
| INCOMPLETE | Required page failed, or page/count continuity was inconsistent |
| FAILED | No usable response, invalid catalog brand/model, or no usable query |

Successful capped scans can qualify as **WIN — OBSERVED (3-page scan)** when the
price beats the lowest observed compatible offer and meets existing profit goals.
CAPPED stays visible as a coverage note. Unknown/incomplete scans remain provisional
and do not qualify as DigiMall personal-commission winners.
Independently confirmed AlfaMall wins remain eligible in combined exports.
With no eligible observed offers after a successful COMPLETE or CAPPED scan, existing
monopoly pricing applies, labeled Not Found / observed SOLO for capped scans. This is
a bounded-search pricing policy, not proof of absence across the entire marketplace.
UNKNOWN, INCOMPLETE and FAILED searches do not receive monopoly prices. Failed/unknown/incomplete rows retry on resume;
capped searches do not automatically repeat forever.

Range mode also uses DigiMall's adaptive queries and reports observed ranges within
that budget. It does not claim the maximum across every alternate query spelling.
Explicit string/dictionary scraper callers remain supported; dictionaries retain
canonical tier order and their caller-selected exhaustive behavior.

DigiMall's rejection diagnostics distinguish explicit model/facet collisions from
uncertain identity. Clearly different extracted models and incompatible automation,
tub or capacity facets do not falsely block Not Found pricing. Listings missing model identity are rejected, not guessed from brand/capacity,
and do not block monopoly when no valid competitors remain. Policy version v3 invalidates older Digi/all cached
checkpoint rows; Alfa-only fingerprints and matching decisions remain unchanged.

COMPLETE is bounded policy completion, not proof of an exhaustive marketplace scan.
Alternate-query-only listings and results after page 3 can remain undiscovered.

## Validation observations — 2026-11-06

Live read-only checks exercised the implemented path without exporting catalogs:

| Model | Queries | HTTP pages | Coverage | Lowest observed PKR |
|---|---:|---:|---|---:|
| Haier 120-316S6 | 1 | 3 | CAPPED | 82,999 |
| Gree 12AITH21W-T3 | 1 | 3 | CAPPED | 158,499 |
| Dawlance DMB-4467 SD | 1 | 1 | COMPLETE | 43,449 |
| Midea MSAG2B-12HRDN1 | 1 | 1 | COMPLETE | 128,999 |
| TCL extracted 55 55C6K | 1 | 2 | COMPLETE | 203,699 |

These are transient observations, not current price promises. Individual live runs
took about 0.67–5.10 seconds; network/server conditions affect timings.

`python -m scripts.benchmark_digimall_discovery` replays identical compatible responses
with simulated 2ms HTTP delay. Five fixture brands, each with three simultaneous
identical products, used 207 HTTP calls with the legacy path versus 5 with adaptive
discovery/shared caching; observed minima and compatible-offer counts agreed. This
is a controlled successful-primary/cache comparison, not a live speed guarantee or
proof of alternate-query recall. Fallback/page-boundary/failure tests cover additional
requests, including preservation of a sixth viable above-floor offer.

Final verification: **618 tests passed**, with 97% combined statement coverage of
the new discovery/transport modules. Repository Ruff lint, strict mypy on the nine
touched engine modules, and Black checks on the five new Python files passed.
The suite emitted 26 Windows curl event-loop compatibility warnings.

Final Digi policy v4: after a successful COMPLETE/CAPPED scan, zero eligible external
offers means Not Found and existing monopoly pricing, regardless of why listings
were rejected. Rejection counters remain diagnostic, not a second pricing veto.
Failed/unknown/incomplete scans and accepted ambiguous-variant selection remain
separate guards. No matcher acceptance rules or Alfa behavior are changed.
