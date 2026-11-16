# Fallback investigation — 2026-11-16

Baseline: 774 tests passed before this change.

Live evidence: Samsung searches for 55Q7FAA already return Samsung 55Q7F listings on both stores; the referee rejects the omitted AA suffix. Midea model searches return compound-SKU listings rejected for extra T3 or omitted QC2. Named-series searches return additional full matching QC2 offers whose model contains a space after the capacity code. No final named-series search existed. Several AlfaMall titles explicitly beginning with Midea carry Other/Nothing/Motorola brand tags, so tag-only brand rejection is unreliable.

User policy: finish model queries first; only when no compatible active model (including own store) exists, try brand + explicitly named series + exact capacity. Preserve physical guards, warn for approximate matches, and preserve genuine no-match monopoly fallback.
