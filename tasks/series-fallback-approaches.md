# Fallback approaches — 2026-11-16

1. Relax all anchor comparisons globally: rejected; this could merge unrelated washer, AC and display variants.
2. Add a shared final named-series stage and a narrowly structured capacity-led base-model fallback: selected. Matching remains strict during the normal model stages. Series matching independently proves brand, whole named series and capacity, then reuses physical guards. The existing two-tier result classification supplies yellow notices.
3. Add more model permutations only: insufficient; this does not handle genuinely omitted model codes or base suffixes.

The implementation is generic, with no Samsung/Midea model exceptions or brand/category lists. A shared module owns series eligibility, query building and matching; both network paths reuse it.
