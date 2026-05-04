# Phase 1 - Improving Sorting

**New Recommended Sort, and updated secondary sorting for other sorting options to increase relevance. Using scores instead of simple superficial sorting to balance out different params and choose what is best for the users intent.**

$$
adjustedrating = (n × hotelrating + m × globalavg) / (n + m)
$$

| Variable | Definition | Value in your case |
| --- | --- | --- |
| `n` | Number of reviews a specific hotel has | Varies per hotel — e.g. 8, 165, 2,400 |
| `hotelrating` | The hotel's actual avg rating from scraper. | e.g. 4.43 for a hotel with 8 reviews |
| `m` | Confidence weight — the "virtual review count"  injected as a prior. Controls how hard low-count hotels get pulled toward the mean. Higher = more skeptical of small samples. | 50 (our P25 number of reviews — meaning we trust a hotel's rating only once it has as many reviews as the median bottom quartile)

**Has to be dynamic and based on actual data. Else the results can be drastically different.** |
| `global_avg` | The platform-wide avg rating across all rated hotels. | **4.30** (computed from data of 5L hotels with ratings.)

**Has to be dynamic and based on actual data. Else the results can be drastically different.** |
| `adjusted_rating` | The output — a dampened rating that's conservative for low-count hotels and nearly equal to `raw_avg` for high-count hotels | Approaches `raw_avg` as `n → ∞` |

**Intuition for `m`:** at exactly `n = m` reviews, the formula weights the hotel's own signal and the global prior equally (50/50). Below that, the prior dominates. Above that, the hotel's own data dominates. So setting `m = 50` means:

- Hotel with **8 reviews**: prior contributes 86% of the score → heavily dampened
- Hotel with **50 reviews**: prior contributes 50% → balanced
- Hotel with **500 reviews**: prior contributes 9% → mostly trusts the hotel's own data
- Hotel with **5,000 reviews**: prior contributes 1% → effectively raw_avg

Tune `m` up (more skeptical, e.g. m=100) or down (more permissive, e.g. m=20) depending on how aggressively we want to penalise cold-start hotels in search ranking.

## Utilizing users search intent hotel stars into the above formula

| Component | Where it lives | When computed | Why |
| --- | --- | --- | --- |
| `adjusted_rating` (Bayesian) | Indexed field in ES | Once, at indexing | Static — depends only on hotel's own data |
| `star_affinity` multiplier | Function score at query time | Per query | Dynamic — depends on user's selected star |

**The combined formula**

```
**adjusted_rating = (n × hotelrating + m × global_avg) / (n + m)**
final_score = adjusted_rating × affinity[selected_star][ <hotel_star> ]^λ
```

Where:

- **`adjusted_rating`** — precomputed, dampened relevance score (the Bayesian one). Indexed as a numeric field on each hotel doc.
- **`hotel_star`** — the hotel's own star rating (already indexed).
- **`selected_star`** — passed in as a query parameter from the user's filter selection.
- **`affinity[s][h]`** — a 3×3 lookup matrix (defined below).
- **`λ` (lambda)** — a tuning knob that controls how aggressively star matching dominates rating quality. Start at λ=1.0; tune via A/B test.
    - **λ is a global lever** — set λ=0 for "ignore star preference" experiments, λ=2 for "strict tier" experiments, all without changing the matrix.

**Cases**

1. Location/Landmark → Uses `affinity[`4 star`][ <hotel_star> ].` → Instead, use pure `adjusted_rating` with no star preference.
    1. Recommended [Default]
        1. Uses `final_score`
    2. User rating → Change to `Popularity`
        1. Uses `adjusted_rating`
    3. Pricing
        1. Uses pricing, followed by `final_score`
    4. Nearby
        1. Uses distance, followed by `final_score`
2. Hotel → Uses `affinity[selected_star][ <hotel_star> ]`
    1. Recommended [Default]
        1. Uses `final_score`
    2. User rating → Change to `Popularity`
        1. Uses `adjusted_rating`
    3. Pricing
        1. Uses pricing, followed by `final_score`
    4. Nearby
        1. Uses distance, followed by `final_score`

**The affinity matrix**

This encodes the asymmetric preference  — users searching higher stars are willing to drop down a notch but don't want the bottom; users searching lower stars are happy with a slight upgrade.

| Selected ↓ / Hotel Weights → | 5★ | 4★ | 3★ |
| --- | --- | --- | --- |
| **5★** | 1.00 | 0.85 | 0.55 |
| **4★** | 0.90 | 1.00 | 0.75 |
| **3★** | 0.55 | 0.85 | 1.00 |

Read it as: "If user selected row R star rating and we're scoring a hotel with star rating as column C, multiply its base score by this number."

Note the asymmetry — for selected=4, 5★ gets 0.90 but 3★ gets 0.75. 

For selected=3, 4★ gets 0.85 but 5★ drops to 0.55 (3-star searchers don't want luxury bleeding into results).

**Worked example — selected = 4★**

| Hotel | Star | adj_rating | affinity (λ=1) | final | Rank |
| --- | --- | --- | --- | --- | --- |
| Skyline Boutique | 4 | 4.42 | 1.00 | **4.420** | 1 |
| The Ritz | 5 | 4.45 | 0.90 | 4.005 | 2 |
| Citywalk Inn | 4 | 4.18 | 1.00 | 4.180 | 3 |
| Comfort Stay | 3 | 4.35 | 0.75 | 3.262 | 4 |
| BudgetMax | 2 | 4.05 | 0.45 | 1.823 | 6 |

The 4★ Skyline (lower raw rating) outranks the 5★ Ritz (higher raw rating) because the user signaled tier intent.

**Gotchas**

1. When `selected_star` is *unset* (user has selected Location/Landmark), default to selected 4 star case.
2. The global average user rating and p25 user rating need to be based on the actual data that is present in the hotel data. Else the results can be very different and unexpected.
    
    Whenever the scraper runs, user ratings and number of reviews data might get updated in the db. Hence, these values will become stale whenever the data gets updated. 
    
    **For now, we can have a daily cron that runs and calculates that days global average user rating and the p25 user rating number and recalculate the adjusted scores for all hotels.**