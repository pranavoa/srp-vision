# Release Notes: Hotel Autocomplete Search Improvement v1.1.0

**Ticket:** [ON-6207](https://onarrival.atlassian.net/browse/ON-6207) - **Status:** Backend PR open, awaiting review - **Date:** 2026-04-23 - **Endpoint:** `GET /api/v1/hotels/destination/anchor-search`

Hotel destination autocomplete now has a stronger recall-recovery layer for real hotel-search typing patterns: compact-vs-spaced hotel names, hotel + city queries, accented names, small hotel/brand typos, and visit-worthy place searches. This is a backend-only v1.1.0 follow-up to the v1.0.0 intent-first autocomplete release. It keeps the public `mode + items[] + debug` response contract unchanged while improving the Elasticsearch and Google Places candidate pipelines underneath it.

Backend branch ships in PR [OnArrival/ods-flight-service#4692](https://github.com/OnArrival/ods-flight-service/pull/4692), with `+4534 / -226` across 19 files.

---

## What’s New

- **Staged hotel fallback is now identity-led.** Stage A remains strict. Stage B only runs when Stage A is empty or weak, and now decomposes hotel + location queries into hotel identity and location evidence instead of forcing the full query into hotel-name fields.
- **Compact-vs-spaced hotel + city recovery.** Queries like `welcom hotel bangalore` can recover `Welcomhotel Bengaluru` because Stage B preserves raw identity (`welcom hotel`) for compact hotel-name variants while using stripped identity (`welcom`) for exact blended identity lanes.
- **Reliable `matched_queries` attribution.** Stage B lane names are now unique and typed, avoiding duplicate `_name` collisions inside Elasticsearch requests and making post-query retention deterministic.
- **City corroboration is strength-aware.** Exact and prefix city matches are strong evidence; typo city matches via `cityName.typo` are weak support evidence. Strong city hits win, but hotel-name-led rescue can still survive when city matching is imperfect.
- **Small hotel and brand typos count as hotel intent.** Local scoring now treats near-token matches such as `radisson blue` -> `Radisson Blu` and `jw mariott` -> `JW Marriott` as strong approximate identity matches.
- **Accent-insensitive hotel search.** Query normalization now NFKD-decomposes text, strips diacritics, and searches folded Elasticsearch subfields, so `Le Meridien` can match `Le Méridien`.
- **Compound hotel-name matching.** `hotelName.boundary` is now used as an additive search lane for glued/spaced variants such as `Taj WestEnd`, `Taj West End`, and similar compound names.
- **Query-aware Google Places Call B.** The second Google Places call no longer spends fixed slots on generic `point_of_interest`; it selects visit-worthy primary types based on query triggers such as temple, stadium, mall, hospital, port, transit, or default sightseeing.
- **Non-visit-worthy Google noise is filtered earlier.** Restaurant, cafe, bar, bakery, bare `point_of_interest`, and bare `establishment` suggestions are rejected before ranking unless they also carry a visit-worthy type.
- **Hotel-dominant mixed results suppress generic places.** When top hotel candidates show brand/location cluster consensus and beat place candidates, mixed results keep hotel rows first and drop generic place rows.
- **Google candidate dedupe is more robust.** Merging now prefers `placeId`, then normalized text + coarse subtitle + type bucket, and keeps the more specific destination type, better provider rank, and richer subtitle.

---

## Why this release matters

The v1.0.0 release fixed the overall shape of destination autocomplete. v1.1.0 closes the seam where hotel intent could still be lost after Stage A:

- hotel-name queries that include a city fragment were still vulnerable when the hotel identity was split too aggressively
- compact vs spaced hotel names needed a stronger rescue path that preserved the raw identity tokens
- a single fuzzy hotel clause could not reliably tell the difference between a good hotel rescue and weak global brand leakage
- Google Places still needed stricter visit-worthy filtering so the backend spends limited Google capacity on actual travel destinations, not generic business noise

This update keeps Stage A narrow and high-precision, while Stage B becomes the controlled recovery layer for hotel identity, city corroboration, and typo tolerance.

---

## Elasticsearch index prerequisites

This PR does **not** add new Elasticsearch fields. It depends on the hotel index shape that was prepared by the accent-folding migration work and is already reflected in `es_index_mappings.json`.

The fields and analyzers this release relies on are:

- `hotelName.folded` for accent-insensitive hotel-name matching
- `hotelName.boundary` for compact-vs-spaced hotel names using the `hotel_compound_index` / `hotel_compound_search` analyzers
- `brandName.folded` and `chainName.folded` for brand/chain identity rescue
- `cityName.folded` for folded city corroboration
- `cityName.typo` for typo-tolerant city fragments using `location_typo_index` / `location_typo_search`
- `address.folded` for blended hotel/city/address matching in strict search

The mapping file also shows the underlying index components that make these lanes work:

- `folded_text` for lowercased, accent-folded matching
- `hotel_compound_delimiter` and `hotel_compound_index` for glued/spaced compound hotel names
- `location_typo_ngrams` and `location_typo_index` for city typo recovery

Operationally, the release assumes those sub-fields already exist in the search index or alias behind the hotel search API. If the cluster is still on the older pre-migration index shape, Stage A and Stage B will lose the exact, folded, compound, and typo lanes this PR depends on.

---

## Technical Details

### Backend - `ods-flight-service` ([PR #4692](https://github.com/OnArrival/ods-flight-service/pull/4692))

#### Changed files

| Area | Files | Purpose |
| --- | --- | --- |
| Hotel ES query generation | `ElasticSearchQueries.kt` | Adds folded strict lanes, compact blended hotel+city lane, boundary matching, Stage B split lanes, unique named queries, city corroboration lanes, and India boost weight update. |
| Candidate fetching | `AnchorCandidateFetcher.kt` | Adds Stage A weak-hit gating, Stage B filtering by lane category, query-aware Google type selection, visit-worthy filtering, and stronger candidate dedupe. |
| Intent and scoring | `AnchorIntentResolver.kt` | Adds approximate token matching, brand/chain/location context scoring, hotel-cluster intent evidence, and generic-place suppression for hotel-dominant mixed results. |
| Shared support | `AnchorSearchSupport.kt` | Adds accent normalization, fallback split planning, fallback shape classification, Google type trigger buckets, destination specificity, and noise allowlists. |
| Composition | `AnchorSearchService.kt`, `AnchorSectionComposer.kt` | Wires filtered mixed geo candidates and suppresses generic places when hotel-cluster intent dominates. |
| DTO plumbing | `DestinationSearchV2.kt`, `ElasticSearchResponse.kt` | Adds internal `brandName` / `chainName` ranking signals and deserializes Elasticsearch `matched_queries`. |
| Type and geo utilities | `GooglePlaceTypeMapper.kt`, `HotelUtils.kt` | Maps additional visit-worthy types and exposes Haversine distance for cluster proximity checks. |
| Docs and tests | Source-of-truth doc + 8 test files | Documents Stage B behavior and adds regression coverage for fallback, Google filtering, matching, and response shaping. |

#### Stage A strict query changes

Stage A is the primary query. It is still strict and relevance-first, but now includes more exact-ish recovery lanes so the common cases can succeed without dropping into fallback too early.

Why Stage A exists:

- PM goal: make hotel search feel like hotel search, not a generic text search
- user goal: recover exact and near-exact hotel names even when spacing or accents are inconsistent
- engineering goal: keep the main query narrow enough that Stage B remains a true fallback, not a hidden second ranking system

The strict query now includes:

- raw and folded `match_phrase` on `hotelName`
- raw and folded `match_phrase_prefix` / `match_bool_prefix` on `hotelName`
- additive `hotelName.boundary` matching for compound/glued names
- expanded `cross_fields` over raw and folded hotel/city/address fields
- a narrow `combined_fields` folded hotel+city lane over `hotelName.folded`, `cityName.folded`, and `address.folded`
- compact merged-token variants applied to hotel-name lanes and the folded hotel+city blended lane
- a bounded strict fuzzy window limited to queries with normalized character length `5..9`

The strict blended compact lane is the key Stage A improvement for inputs like `welcom hotel bangalore`, because it can evaluate both the compact hotel form and city context without adding broad fuzzy behavior to the main query.

Stage A handles:

- exact hotel names
- spaced vs glued hotel names
- accented hotel names
- partial hotel prefixes
- obvious city fragments that should still be matched exactly or as prefixes

It deliberately does not try to solve heavy typo recovery or hotel-plus-city decomposition by itself, because that would make the primary query too permissive and reintroduce noisy matches.

#### Stage B fallback redesign

Stage B is the recovery path. It remains a single sequential Elasticsearch call after Stage A. It is not a parallel path and there is no Stage C.

Why Stage B exists:

- Stage A should stay narrow and high-precision
- some user queries are clearly hotel intent, but they contain a typo, an ambiguous trailing city fragment, or both
- a single fuzzy hotel clause cannot tell the difference between a good hotel rescue and an unrelated brand/global match
- Stage B solves that by separating hotel identity, city corroboration, and matched-query attribution

Stage B is designed to answer a different question:

- not “what is the best overall fuzzy match?”
- but “is this hit a hotel identity hit, a city-corroborated hotel hit, or just weak noise?”

Stage B now classifies fallback shape as:

| Shape | Example | Behavior |
| --- | --- | --- |
| `HOTEL_ONLY` | `welcom hotel`, `treeo white inn` | Whole-query hotel rescue; allows hotel and brand identity lanes. |
| `AMBIGUOUS_LOCATION` | `welcom hotel ben`, `radison blue be` | Keeps hotel-name rescue available; weak city evidence can support but not dominate. |
| `STRONG_LOCATION` | `radisson blue bangalore`, `welcome heritage tadoba` | Prefers strong city-corroborated lanes; otherwise only strong hotel-name-led identity can survive. |

This classification matters because the same query shape should not be treated the same way:

- `welcom hotel ben` is ambiguous and needs help from city evidence
- `radisson blue bangalore` is stronger because the city is explicit
- `treeo white inn` is hotel-only and should not be forced through city corroboration

For each location-bearing split, fallback planning preserves:

| Field | Example for `welcom hotel bangalore` | Used for |
| --- | --- | --- |
| `rawIdentityQuery` | `welcom hotel` | Hotel-name exact/fuzzy rescue and compact variants such as `welcomhotel`. |
| `strippedIdentityQuery` | `welcom` | Exact blended identity and brand/chain fuzzy lanes. |
| `locationQuery` | `bangalore` | Exact city, prefix city, and typo city corroboration. |
| `splitIndex` | `0` | Unique named-query attribution. |

Stage B lane families are now typed through `_name` prefixes:

| Prefix | Category | Meaning |
| --- | --- | --- |
| `stage_b_identity_hotel_` | `IDENTITY_HOTEL` | Hotel-name exact/fuzzy rescue. |
| `stage_b_identity_brand_` | `IDENTITY_BRAND` | Lower-boost brand/chain rescue. |
| `stage_b_city_strong_` | `CITY_STRONG` | Exact or prefix city corroboration. |
| `stage_b_city_weak_hotel_` | `CITY_WEAK_HOTEL` | Hotel-name rescue with typo-city support. |
| `stage_b_city_weak_brand_` | `CITY_WEAK_BRAND` | Brand/chain rescue with typo-city support. |

Each lane name includes the lane type and either `_full` or `_split_N`, for example:

```
stage_b_identity_hotel_exact_split_0
stage_b_identity_hotel_fuzzy_split_0
stage_b_identity_brand_fuzzy_split_0
stage_b_city_strong_exact_identity_exact_city_split_0
stage_b_city_strong_exact_identity_prefix_city_split_0
stage_b_city_weak_hotel_exact_identity_typo_city_split_0
```

Retention policy:

- `HOTEL_ONLY` keeps hotel and brand identity rescue without requiring city corroboration.
- `AMBIGUOUS_LOCATION` keeps `CITY_STRONG` hits if any exist; otherwise keeps hotel-led identity or weak-city hotel hits only when local lexical scoring clears `HOTEL_INTENT_MIN_SCORE`.
- `STRONG_LOCATION` keeps `CITY_STRONG` hits if any exist; otherwise keeps only hotel-led identity hits that clear `HOTEL_INTENT_MIN_SCORE + 0.10`.
- Brand-only rows are dropped for ambiguous and strong location-bearing shapes unless strong city corroboration exists.

This is the main behavior change that prevents `welcom hotel bangalore` from being lost while still blocking low-signal brand leakage.

The Stage B design is intentionally more complex than a single fuzzy query because we need two things at once:

- higher recall for broken hotel typing
- lower leakage for generic or unrelated brand hits

That tradeoff is what the split planning and lane retention solve.

#### Approximate hotel intent

`AnchorIntentResolver` now uses Levenshtein-based approximate token matching:

- tokens shorter than 3 characters require exact match
- tokens of length 3 to 7 allow max 1 edit
- longer tokens allow max 2 edits

This is applied inside hotel candidate scoring and intent detection, so typo-like hotel inputs can still be recognized as hotel intent and avoid generic place pollution.

Examples covered by tests:

- `radisson blue` -> `Radisson Blu`
- `jw mariott` -> `JW Marriott`

#### Hotel-cluster intent

The resolver no longer trusts only the top hotel row for hotel-dominant mixed results. It now builds `HotelIntentEvidence` from the top hotel cluster:

- brand consensus across top hotels
- city/state/country or tight geographic location consensus
- query coverage across hotel brand/name + location context
- dominance over competing place candidates

When the cluster is strong, the backend keeps `MIXED_RESULTS` but suppresses generic place rows, preserving only high-confidence exact administrative or landmark-style place rows after hotels.

#### Google Places filtering and type selection

Google Places still uses two calls:

- **Call A:** fixed geo/admin types from `AnchorSearchSupport.fixedGeoPrimaryTypes`
- **Call B:** query-aware visit-worthy primary types from `selectVisitWorthyPrimaryTypes`

Call B type selection examples:

| Query pattern | Included primary types |
| --- | --- |
| `golden temple` | worship-oriented types such as `place_of_worship`, `hindu_temple`, `church`, `mosque`, `synagogue` |
| `wankhede stadium` | stadium/sports/event venue types |
| `vega city mall` | shopping mall / market / event venue / attraction types |
| `port blair harbour` | marina / ferry / attraction / park / event venue types |
| default sightseeing | `tourist_attraction`, `historical_landmark`, `cultural_landmark`, `train_station`, `park` |

Filtering now rejects non-visit-worthy Google suggestions before ranking:

- hard-drops dining/business noise like `restaurant`, `food`, `cafe`, `bar`, `bakery`, `meal_takeaway`, `night_club`
- treats bare `point_of_interest` and bare `establishment` as insufficient
- keeps generic POI only when accompanied by a meaningful travel type such as `shopping_mall`

This matters because the Google half of the autocomplete pipeline is no longer being asked to carry generic business noise. The backend now spends Google capacity on actual travel destinations and lets Elasticsearch handle hotel identity recovery.

#### Type mapping updates

`GooglePlaceTypeMapper` is now more pessimistic for generic types:

- `point_of_interest` / `establishment` alone maps to `LOCATION`, not `LANDMARK`
- `cultural_landmark` maps to `LANDMARK`
- `athletic_field` contributes to `STADIUM`
- specific attraction/venue types remain preferred over generic POI fallback

#### Public contract

No public response-contract change in v1.1.0.

The endpoint still returns:

```json
{
  "mode": "GEO_CONTEXT | MIXED_RESULTS",
  "items": [],
  "debug": {
    "query": "string",
    "latencyMs": 0,
    "modeReason": "string?"
  }
}
```

Internal DTO additions:

- `DestinationSearchV2.brandName`
- `DestinationSearchV2.chainName`
- `Hit.matchedQueries`

These are internal ranking/fallback signals and do not require a PWA contract update.

---

## User Impact

**Who:** Hotel search users typing exact hotel names, hotel + city queries, branded hotel names, accented hotel names, and landmark/visit-worthy place queries.

**How it benefits them:**

- `welcom hotel bangalore` can recover Bengaluru Welcomhotel-style results instead of going empty.
- `welcomhotel bangalore` remains supported through compact matching.
- `radisson blue bangalore` and `radison blue beng` can recover city-consistent Radisson results despite hotel/city typos.
- `jw mariott ben` can still be interpreted as hotel intent instead of becoming generic place search.
- `Le Meridien` can match `Le Méridien`.
- `Taj WestEnd` / `Taj West End`-style compound names are more resilient.
- `taj hotel ben` is less likely to be polluted by generic Google businesses.
- `wankhede stadium`, `golden temple`, `vega city mall`, and similar visit-worthy searches spend Google Places capacity on relevant venue types.
- Mixed hotel-dominant results show hotels first and avoid burying them under weak generic place rows.

---

## Metrics & Success Criteria

Watch these after rollout:

- **Zero-result rate for hotel + city queries** such as `welcom hotel bangalore`, `radisson blue bangalore`, and `jw mariott ben`.
- **Stage B fallback hit rate** and the split between `zero_hit` and `weak_strict_hit` fallback reasons.
- **Stage B retained category distribution**: `CITY_STRONG`, `IDENTITY_HOTEL`, `CITY_WEAK_HOTEL`, and dropped brand-only rows.
- **Top-result CTR for hotel-name queries**, especially compact/spaced and typo variants.
- **Generic place suppression rate** for strong hotel-cluster intent.
- **Google Places Call B relevance**, segmented by query-trigger bucket: worship, stadium, mall, hospital, port, transit, default sightseeing.
- **Latency p50/p95** for autocomplete. Stage B is sequential and capped, but weak strict matches now trigger it more often than v1.0.0.
- **Fallback precision complaints** for brand-only leakage, especially global brands without strong city corroboration.
- **Alias gap rate** for city exonyms such as `bangalore` vs `bengaluru`, which remains outside this PR.

---

## Rollout Status & Strategy

- **Status:** Backend PR [#4692](https://github.com/OnArrival/ods-flight-service/pull/4692) is open and awaiting review.
- **Branch:** `ON-6207-anchor-search-improvement`
- **Commits in PR:**
    - `8f15ceaaf` refactor: Enhance anchor candidate fetching and filtering logic
    - `3a4202ca8` feat: Enhance query normalization and search logic for accent sensitivity
    - `51cf22e66` feat: Add boundary hotel name matching to search queries
    - `f4cb7b82a` feat: Implement staged hotel fallback and enhanced intent resolution
    - `c46a3fbf5` feat: Enhance hotel search fallback with staged recovery and approximate matching
    - `6e719c760` docs: Enhance documentation for hotel search components
- **Deploy coupling:** Backend-only. Unlike v1.0.0, no PWA coupled deploy is required because the public autocomplete contract is unchanged.
- **Config impact:** Existing `anchor-search.features.boostIndianElasticHotelsEnabled` still controls India-first hotel boosting. This PR changes the boost weight from `4.0` to `5.0`.
- **Index impact:** No new Elasticsearch fields are introduced by this release. The implementation relies on the folded, boundary, and typo subfields already prepared in the hotel index migration and documented in `es_index_mappings.json`.

---

## Validation

PR validation listed:

```bash
./gradlew test --tests "*GooglePlaceTypeMapperTest" --tests "*AnchorSearchAccommodationFilterTest" --tests "*AnchorSearchServiceResilienceTest" --tests "*AnchorSearchSupportTest"
./gradlew test --tests "*ElasticSearchQueriesAutocompleteTest"
./gradlew test --tests "*AnchorIntentResolverTest"
./gradlew test --tests "*AnchorSectionComposerTest"
./gradlew test --tests "*ElasticSearchResponseDeserializationTest"
./gradlew test --tests "*Anchor*"
./gradlew ktlintCheck
```

Manual verification examples listed in the PR:

- `taj hotel ben`
- `wankhede stadium`
- `golden temple`
- `vega city mall`
- `Le Meridien`
- `Taj WestEnd`
- `Mariott goa`

Additional regression examples covered in tests:

- `welcom hotel bangalore`
- `welcom hotel ben`
- `hotel welcome ben`
- `welcome heritage tadoba`
- `welcomHeritage tadoba`
- `radisson blue bangalore`
- `radisson blue beanga`
- `radison blue beng`
- `jw mariott`

---

## Known Issues / Edge Cases

- **City aliases are not solved here.** `bangalore` vs `bengaluru` still needs a separate alias data rollout. This release preserves hotel intent and avoids leakage; it does not add semantic city aliases.
- **No new Elasticsearch mapping fields.** The PR depends on existing mapped subfields such as `hotelName.folded`, `hotelName.boundary`, `brandName.folded`, `chainName.folded`, `cityName.folded`, `cityName.typo`, and `address.folded`.
- **Stage B is sequential.** It only runs after strict search is empty or weak, but any increase in weak strict matches can affect fallback frequency and latency.
- **Typo city evidence is weak by design.** `cityName.typo` can support a result but should not independently allow broad brand leakage.
- **Brand-only recovery is intentionally constrained.** For ambiguous or strong location-bearing shapes, brand/chain-only hits are dropped unless there is strong city corroboration.
- **Google Places filtering is deliberately conservative.** Some local businesses that users might personally consider destinations can be filtered if they only carry generic business/POI types.
- **Approximate token matching is local scoring, not a new ES index.** It improves intent/ranking after retrieval but does not create a separate identity typo index.
- **India boost remains query-shape based.** It is useful for short hotel autocomplete but is not intended to solve long hotel + location typo leakage.

---

## Links

- Backend PR: [OnArrival/ods-flight-service#4692](https://github.com/OnArrival/ods-flight-service/pull/4692)
- v1.0.0 Notion doc: [Release Notes: Hotel Autocomplete Search Improvement v1.0.0](https://www.notion.so/Release-Notes-Hotel-Autocomplete-Search-Improvement-v1-0-0-342ee3bd5dec8127bb02d73b29bac3e6?pvs=21)
- Source of truth: `docs/plans/2026-04-09-intent-first-destination-autocomplete-source-of-truth.md`