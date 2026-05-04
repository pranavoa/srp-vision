Release Notes | Hotel Recommended Sort (Star Affinity + Popularity) v1.2.0 @Today
**Ticket:** [ON-6566](https://onarrival.atlassian.net/browse/ON-6566)  •  **Status:** Backend implemented locally, PR pending; coupled FE PR not yet opened  •  **Date:** 2026-05-04  •  **Endpoint:** `POST /api/v1/hotels/listing`

Hotel listing sort gains a new **`RECOMMENDED`** mode that blends **user rating**, **review-count popularity** (logarithmic), and a **star-affinity multiplier** so that hotels matching the user's selected star tier surface first while close-tier hotels (e.g. 5★ when 4★ was selected) still compete on rating, and well-reviewed hotels break ties cleanly inside a bucket. Implemented as a native Elasticsearch `function_score` — no Painless on the query path, no reindex, no new mappings.

> **v1.1.0 update:** added `hotelTotalReviews` (`log1p` modifier) as a popularity factor. Without it, multiple hotels in the same star bucket with equal `userAvgRating` ranked in arbitrary Lucene doc order (real example seen: 4 × 5★ Mumbai hotels all `userAvgRating=4.7` with review counts ranging 7k → 33k surfacing in undefined order). Reviews now break those ties.
> 

This is the first slice of the broader recommended-scoring effort. Adjusted (Bayesian) rating and distance decay are intentionally **out of scope** for this release and will follow.

Branch ships on `ON-6566-search-listing-sort-changes` (`+117 / -1` across 3 files: 1 new, 2 touched).

---

## What's new

- **New sort mode `RECOMMENDED`.** Added to `SortFieldName` and wired through `findSortCriteria` + `buildBaseSearchQuery` in `ElasticSearchQueries`. Existing modes (`HOTEL_RATING`, `USER_RATING`, default geo, anchor-aware) are untouched.
- **Star-affinity multiplier.** A 3×3 asymmetric matrix encodes "users searching 4★ tolerate 5★ better than 3★; 3★ searchers don't want luxury bleeding into results". Applied as one `filter`+`weight` per hotel-star bucket — only the matching bucket fires per doc.
- **In-bucket order by user rating.** A `field_value_factor` on `userAvgRating` is multiplied into the bucket weight so two 4★ hotels still order by rating, not arbitrarily. Missing ratings fall back to a neutral `1.0`.
- **Popularity tiebreaker via reviews (`v1.1.0`).** A second `field_value_factor` on `hotelTotalReviews` with `log1p` modifier is multiplied in. Logarithmic so a 33k-review hotel beats a 7k-review hotel by ~1.16×, not 4×. Missing review counts fall back to `1.0` (`log1p(1) = ln 2 ≈ 0.69`) so unreviewed hotels aren't zeroed out.
- **Multi-select star filter handling.** When the user picks multiple star ratings (`{3, 4}`), `selectedStar = max(selected)` — matches "I want at least N★, but higher is fine".
- **Default fallback.** When no `HOTEL_RATING` filter is set, `selectedStar = 4` (per spec Gotcha #1). Avoids edge-case empty-row scoring.
- **Single global tuning knob.** A `λ` exponent (default `1.0`) controls how aggressively the star multiplier dominates rating quality. `λ=0` disables the multiplier; `λ=2` makes it strict — tunable via A/B without changing the matrix.
- **Native ES, no Painless.** The whole formula is expressed via `function_score` `filter`+`weight` pairs and `field_value_factor`. No script cache pressure, no Painless compilation cost, easier to debug via `?explain=true`.
- **Surgical wrap.** Recommended sort wraps only the existing `bool.filter` — no change to `post_filter`, aggregations, search-after, or any other sort path. Aggregations still see the unfiltered set; pagination semantics unchanged for non-recommended sorts.

---

## Technical details

### Backend — `ods-flight-service`

#### Sort decomposition (new files)

| Class / File | LOC | Responsibility |
| --- | --- | --- |
| `app/hotel/service/elastic/StarAffinityScoring.kt` | 101 | **New.** Pure Kotlin `object` (no Spring DI). Owns the affinity matrix, `λ`, default selected-star, fallback for missing user rating. Exposes `selectedStarFromFilters(filters)` and `wrapWithStarAffinity(baseQuery, selectedStar)`. |

`ElasticSearchQueries` shrinks its scope by leaning on the new file — only adds two thin touch points (sort-criteria branch + query wrap). No new service, no new bean, no constructor changes.

#### Scoring formula

```
final_score = userAvgRating × log1p(hotelTotalReviews) × affinity[selectedStar][hotelStar] ^ λ
```

Implemented as a single `function_score`:

| Function | Role |
| --- | --- |
| `field_value_factor` on `userAvgRating` (`missing = 1.0`, `modifier = none`) | Quality — orders hotels within the same star bucket by their user rating. |
| `field_value_factor` on `hotelTotalReviews` (`missing = 1.0`, `modifier = log1p`) | Popularity — breaks rating ties; logarithmic so reviews matter but don't dominate. |
| One `{filter: term hotelRating=h, weight: affinity[s][h]^λ}` per hotel-star bucket | Star-tier multiplier. Each doc matches exactly one bucket; non-matching buckets contribute `1.0` under `score_mode: multiply`. |

Combined with `score_mode: multiply` and `boost_mode: replace` so `_score` cleanly equals `userAvgRating × log1p(hotelTotalReviews) × bucketWeight` — the base `bool.filter` query carries no relevance score, so `replace` is safe and avoids BM25 noise contaminating the rank.

#### Affinity matrix

| Selected ↓ / Hotel Weights → | 5★ | 4★ | 3★ |
| --- | --- | --- | --- |
| **5★** | 1.00 | 0.85 | 0.55 |
| **4★** | 0.90 | 1.00 | 0.75 |
| **3★** | 0.55 | 0.85 | 1.00 |

Asymmetry is intentional: 4★ searchers tolerate 5★ better than 3★; 3★ searchers don't want luxury bleeding into results.

> The base query already filters `hotelRating >= 3` (`DEFAULT_HOTEL_MIN_RATING`), so 1★ / 2★ buckets are unreachable and not weighted. If `DEFAULT_HOTEL_MIN_RATING` is ever lowered, extend the matrix to cover the new buckets.
> 

#### Mode decision

| Sort field | Star filter | Resulting query | Sort key |
| --- | --- | --- | --- |
| `RECOMMENDED` | Set (e.g. 4★) | `function_score` wrap with `selectedStar = 4` | `_score` desc |
| `RECOMMENDED` | Multi-select (e.g. `{3, 4}`) | Same, `selectedStar = max = 4` | `_score` desc |
| `RECOMMENDED` | Unset | Same, `selectedStar = 4` (default) | `_score` desc |
| `HOTEL_RATING` / `USER_RATING` / default geo / anchor-aware | any | Unchanged from previous release | Unchanged |

#### Worked example — `selectedStar = 4`, `λ = 1.0`

| Rank | Hotel | Hotel★ | userAvgRating | reviews | `log1p(reviews)` | bucket weight | `_score` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Skyline Boutique | 4 | 4.42 | 12,000 | 9.39 | 1.00 | **41.51** |
| 2 | Citywalk Inn | 4 | 4.18 | 9,500 | 9.16 | 1.00 | 38.31 |
| 3 | The Ritz | 5 | 4.45 | 8,000 | 8.99 | 0.90 | 36.00 |
| 4 | Comfort Stay | 3 | 4.35 | 6,000 | 8.70 | 0.75 | 28.39 |

The 4★ Skyline ranks above the 5★ Ritz despite a lower raw rating — the user signaled tier intent. Within the 4★ bucket, Skyline beats Citywalk on combined rating × reviews.

#### Worked example — popularity tiebreaker (the real Mumbai case from QA)

All four hotels: 5★, `userAvgRating = 4.7`, `selectedStar = 4` → bucket weight = `0.90`.

| Hotel | reviews | `log1p(reviews)` | `_score` | Rank |
| --- | --- | --- | --- | --- |
| The Taj Mahal Palace | 33,438 | 10.42 | **44.07** | 1 |
| ITC Grand Central | 23,552 | 10.07 | 42.60 | 2 |
| The Oberoi | 10,748 | 9.28 | 39.26 | 3 |
| Taj Mahal Tower | 7,486 | 8.92 | 37.74 | 4 |

Pre-`v1.1.0` all four had identical `_score = 4.23` and ordered by Lucene doc id (essentially random). Now they separate cleanly by review-count popularity.

#### Elasticsearch query rewrite (`ElasticSearchQueries.kt`)

The existing `bool.filter` query (geo, radius, hotelRating ≥ 3, destination scope, etc.) is preserved verbatim and conditionally wrapped:

```kotlin
val baseQuery: Map<String, Any> = mapOf("bool" to mapOf("filter" to baseFilterList))
resultMap["query"] =
    if (searchSort?.field == SortFieldName.RECOMMENDED) {
        StarAffinityScoring.wrapWithStarAffinity(
            baseQuery = baseQuery,
            selectedStar = StarAffinityScoring.selectedStarFromFilters(searchFilters),
        )
    } else {
        baseQuery
    }
```

Sort-criteria branch in `findSortCriteria`:

```kotlin
SortFieldName.RECOMMENDED ->
    listOf(
        mapOf("_score" to mapOf("order" to "desc")),
    )
```

**Filters** (existing, unchanged): geo radius, viewport bounding box, `hotelRating ≥ 3`, destination scope.

**`post_filter`** (existing, unchanged): user-applied filters still apply to hits but not aggregations. Star-rating filter selections feed BOTH the post-filter AND the affinity selector — correctly: docs that don't match the selected star still appear (with reduced score), exactly the spec intent.

**Aggregations** (existing, unchanged): dynamic facet exclusion pattern still operates on the unwrapped base filter set.

#### DTO contract changes (`HotelSort.kt`)

**Added:**

- `SortFieldName.RECOMMENDED`

**No removals.** `sortType` is read but ignored for `RECOMMENDED` (always sorted by `_score` descending).

#### Config / tuning knobs

All knobs live in `service/elastic/StarAffinityScoring.kt` as `private const`s — easy to find, easy to unit-test.

| Constant | Default | Purpose |
| --- | --- | --- |
| `LAMBDA` | `1.0` | How aggressively the star multiplier dominates rating quality. `0` = ignore stars; `2` = strict tier. A/B lever. |
| `DEFAULT_SELECTED_STAR` | `4` | Used when no `HOTEL_RATING` filter is present. |
| `MISSING_USER_RATING` | `1.0` | `field_value_factor` fallback for hotels without a `userAvgRating` (so they aren't zeroed out). |
| `MISSING_HOTEL_TOTAL_REVIEWS` | `1.0` | `field_value_factor` fallback for hotels without `hotelTotalReviews`. `log1p(1) ≈ 0.69` — small but non-zero, so unreviewed hotels don't crush to score 0. |
| `AFFINITY` | 3×3 matrix above | Per-tier weights. |

No Spring `@ConfigurationProperties` and no `application.properties` keys yet — promote when product wants per-org overrides or live tuning.

#### Test coverage

- **No new tests** in this release. The change is small (101 LOC of new code, two-line wiring in the existing class) and covered behaviourally via the existing search integration tests once they run against `RECOMMENDED`.
- **Recommended follow-up tests** (next PR): `StarAffinityScoringTest` for matrix lookups + multi-select resolution + default fallback; `ElasticSearchQueriesTest` assertion that `RECOMMENDED` produces a `function_score` wrap and `_score` desc sort.

### Frontend — `hotel-pwa-mobile`

**Pending — not yet started.** Required FE changes for full rollout:

- Add `RECOMMENDED` to the sort enum / dropdown options.
- Make `RECOMMENDED` the default selected sort.
- Send `sort: { field: "RECOMMENDED" }` in the `POST /api/v1/hotels/listing` payload.
- Ensure star-rating filter values keep being sent even when sorted by `RECOMMENDED` (server reads `selectedStar` from filters).
- No DTO changes on the response side — backward-compatible.

### Constraints & non-goals

- **No adjusted (Bayesian) rating.** `userAvgRating` is the raw base — but the `log1p(reviews)` factor (`v1.1.0`) partially mitigates this by down-weighting hotels with thin review history relative to well-established peers. Full Bayesian dampening still deferred.
- **No distance decay.** Recommended sort does not penalize far-from-anchor hotels. Use `NEARBY` (existing default geo sort) when proximity is critical. Deferred.
- **No daily cron / global stats job.** Without adjusted rating, no global average / prior count needs to be computed. Deferred.
- **No new ES mappings, no reindex.** Relies entirely on existing `hotelRating` and `userAvgRating` fields.
- **No Painless scripting.** Pure native function functions for portability and observability (`?explain=true`).
- **No `application.properties` knobs.** `λ`, default star, and the matrix are compiled in. Promote to config when product needs live tuning.
- **No anchor-aware variant.** Anchor sort path (`anchorAwareGeoSort`) is unchanged. `RECOMMENDED` does not stack with anchor pinning yet.

---

## User impact

**Who:** All hotel listing search users; especially users who apply a star-rating filter and expect their selected tier to dominate the page.

**How it benefits them:**

- Selecting "4★" no longer means a 5★ hotel with a marginally higher `userAvgRating` lands at the top — the star intent is honored, and 5★ hotels appear lower with their score multiplied by `0.90`.
- Selecting "3★" no longer surfaces 5★ luxury properties just because they have higher review averages — luxury-bleed is suppressed via the `0.55` weight.
- Within the same star bucket, hotels still order by `userAvgRating`, so the best 4★ in the city is still on top.
- Hotels with no user rating don't disappear from the page (neutral `1.0` fallback) — they sit at the bottom of their bucket instead of being zeroed out.
- When no star filter is set, the page leans toward 4★ as the "default reasonable tier" — matches the most common shopper intent without being abrasive.

---

## Metrics & success criteria

No dashboard data yet (pre-rollout). Watch after deploy:

- **CTR on top-N results when `sort = RECOMMENDED`** vs the previous default (geo / userAvgRating). Target: lift on filtered-by-star searches.
- **Star-filter respect rate** — sample queries where user picked 4★ and check the share of top-10 results that are 4★. Should rise materially.
- **Search-to-listing-to-detail conversion** for star-filtered sessions. Target: lift; no regression for unfiltered sessions.
- **`λ` A/B** — toggle `LAMBDA` between `0.5`, `1.0`, `1.5` to find the right balance between tier respect and rating quality.
- **Tie / pagination jitter rate** — manual QA on pages 2+ to confirm result stability with `_score`-only sort. Add a tiebreaker if jitter is observed (see Known issues).
- **Latency** (p50 / p95) on `/listing` — must hold flat. `function_score` with native filter+weight functions is cheap; expect <1ms per query overhead.

---

## Rollout status & strategy

- **Status:** Backend changes implemented locally on `ON-6566-search-listing-sort-changes`. Compile clean (`./gradlew compileKotlin` passes). PR not yet open. Frontend PR not yet started.
- **Branch commits:** *Pending — to be added after staging the commit.*
- **Coupled deploy not strictly required.** Backend is fully backward-compatible: clients that don't send `sort.field = "RECOMMENDED"` see no change. Backend can ship first; frontend can adopt the new mode at any time after.
- **Kill switch:** None — recommended sort is opt-in via the `sort.field` request param. To disable, the FE simply stops sending `RECOMMENDED`.
- **Rollback:** Revert the three files (`HotelSort.kt`, `ElasticSearchQueries.kt`, `service/elastic/StarAffinityScoring.kt`). No DB migration, no reindex, no data cleanup.
- **Reviewers:** *TBD.*

---

## Known issues / edge cases

- **Pagination jitter on ties.** `_score` is the sole sort key; identical scores can shuffle across pages. With reviews now in the score (`v1.1.0`), exact ties are far rarer — they only happen when star, rating, and review count all match. Mitigation if it still bites: add `hotelCode.keyword asc` as a stable secondary sort.
- **Hotels with no `userAvgRating` or no `hotelTotalReviews`** rank at `bucketWeight × 1.0 × 0.69` (roughly), which can place them above well-rated hotels in lower-affinity buckets. Acceptable for a first release; revisit if user complaints surface.
- **Review count is logarithmic by design.** A hotel with 1,000 reviews and one with 100,000 differ by ~`log(100001)/log(1001) ≈ 1.67×`, not 100×. Intentional — review count is a confidence signal, not a popularity contest winner. If product wants linear weighting, swap `log1p` for `none`.
- **Static matrix.** Weights are compiled in. Per-org or per-experiment overrides require a code change and redeploy. Promote to config if needed.
- **Multi-select max-as-selected**: a user picking `{3, 5}` (skipping 4) gets `selectedStar = 5`, which down-weights 3★ hotels at `0.55`. This is arguably wrong — they explicitly selected 3★. Acceptable trade-off for v1; revisit if telemetry shows the pattern.
- **No distance / anchor coupling.** Recommended sort doesn't combine with the anchor-aware geo sort path. If both are wanted (RECOMMENDED inside an anchor flow), needs design.
- **First-page only behaviour change.** The wrap fires for every page; aggregations are unaffected. No subtle facet-count drift expected, but worth a smoke test.
- **`λ`, default star, and matrix are static constants.** A/B testing requires a code change + redeploy. Externalize before running a serious A/B.

---

## Links

**Pull requests**

- Backend — *PR pending — branch `ON-6566-search-listing-sort-changes`.*
- Frontend — *PR pending — branch `hotel-search-nearby-changes`.*

**Tickets**

- [ON-6566 — Search listing sort changes](https://onarrival.atlassian.net/browse/ON-6566)

**Docs**

- *Hotels — Search — Recommended Sort — Scoring Formula (product source of truth)* — *to be linked once the Notion page is moved into the Hotels space.*
- Predecessor: [Release Notes — Hotel Autocomplete Search Improvement v1.0.0](https://www.notion.so/Release-Notes-Hotel-Autocomplete-Search-Improvement-v1-0-0-342ee3bd5dec8127bb02d73b29bac3e6?pvs=21) (anchor-search refactor that introduced `function_score` wrapping in `ElasticSearchQueries.kt`, reused here).