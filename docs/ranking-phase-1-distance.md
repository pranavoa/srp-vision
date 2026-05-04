## Utilizing distance/nearby in above formula

```
final_score = adjusted_rating * affinity[selected_star][hotel_star]^λ_s * distance_decay(d, anchor)^λ_d
```

You add distance as a **third multiplicative factor** with its own intensity knob. Each factor stays 0–1 (except adjusted_rating which is 0–5), so the structure remains interpretable: "ideal score = raw rating, each non-ideal dimension pulls it down."

**New variables**

| Variable | Definition | Typical value |
| --- | --- | --- |
| `d` | Geo distance from hotel to anchor, in km (computed at query time from lat/lng) | Per hotel |
| `anchor` | The point the user is searching near — a landmark, neighborhood centroid, or pinned location | Passed in query |
| `offset_km` | "Free zone" — within this radius distance doesn't penalize at all | 0.5 km |
| `scale_km` | Distance at which decay reaches 0.5. Smaller = stricter | 5 km (city), 2 km (neighborhood) |
| `λ_d` | Distance affinity strength. 0 = ignore distance, 2 = dominate by distance | 1.0 |

**The decay function (Gaussian)**

```
distance_decay = exp( -max(0, d − offset_km)² / (2 × scale_km²) )
```

This shape captures three real-world properties:

- **Within `offset_km`**: decay = 1.0. Being 100m vs 400m away doesn't matter; both are "right there."
- **Around `scale_km`**: decay ≈ 0.5. The hotel is noticeably far but still a viable candidate.
- **Beyond 3× scale**: decay → 0. The hotel is effectively irrelevant for this anchor.

A linear or reciprocal decay would punish the close-range zone too aggressively (a hotel 200m away vs 50m away shouldn't differ) and tail off too slowly at distance.

**Worked example — user filter: 4★, anchor: MG Road**

Default params: `offset=0.5km, scale=5km, λ_s=1, λ_d=1`

| Hotel | Star | adj_rating | dist | aff | decay | final | Rank |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Skyline Boutique | 4★ | 4.45 | 0.3 km | 1.00 | 1.000 | **4.450** | 1 |
| The Ritz | 5★ | 4.45 | 0.5 km | 0.90 | 1.000 | 4.005 | 2 |
| Comfort Stay | 3★ | 4.40 | 1.0 km | 0.75 | 0.995 | 3.284 | 3 |
| Premium Heights | 4★ | 4.50 | 8.0 km | 1.00 | 0.325 | 1.463 | 4 |
| Suburb Inn | 4★ | 4.55 | 18 km | 1.00 | 0.011 | 0.052 | 5 |

Notice Premium Heights — best raw rating, perfect star match — collapses to rank 4 because it's 8 km out. Suburb Inn at 18 km essentially disqualifies itself even with a 4.55 rating. That's exactly the behavior you want for proximity search.

**Conditional application — the "no anchor" case**

Just like `selected_star`, distance is conditional. Three states to handle:

| State | Behavior |
| --- | --- |
| Anchor + star both set | Full formula |
| Only anchor set (e.g., "hotels near MG Road") | `final = adjusted_rating × decay^λ_d` |
| Only star set (e.g., "5★ hotels in Bangalore") | `final = adjusted_rating × aff^λ_s` |
| Neither set | Sort by `adjusted_rating` directly |

Branch in your query builder, not in Painless — it's cleaner and saves the script overhead when factors don't apply.

**Tuning notes**

**`scale_km` is the most context-sensitive parameter** — it should adapt to search type:

- "Hotels near Bangalore Airport" → scale=10km (people accept further from airports)
- "Hotels near Phoenix Mall" → scale=3km (shopping anchor, walkable preference)
- "Hotels in Indiranagar" → scale=2km, offset=1km (neighborhood search, anywhere inside is fine)

You can encode this as **anchor type metadata** — your geocoder/POI service tags each anchor as `landmark | neighborhood | airport | city` and you map that to scale presets.

**`λ_d` vs `λ_s` interaction** is the key A/B variable. If both are 1.0, distance and star matter equally. If users abandon when shown far hotels (regardless of stars), raise λ_d. If users complain about wrong tier (regardless of distance), raise λ_s. Most hotel platforms run with `λ_d ≈ 1.5, λ_s ≈ 0.8` — distance dominates, star is a tilt.

**One subtle issue worth flagging**

When `λ_d` and `λ_s` are both high, the multiplicative chain can crush borderline-good hotels into invisibility. A 4★ hotel at 6km with a 4.5 rating could end up below a 3★ hotel at 0.5km with a 4.0 rating — which is sometimes correct (proximity wins) but sometimes wrong (a great hotel barely off-axis got buried).

Mitigation: add a **floor** to each decay term so no factor can drop below, say, 0.15:

```
aff_eff = max(0.15, affinity^λ_s)
decay_eff = max(0.15, decay^λ_d)
```

This guarantees that no single dimension can fully zero out a hotel's score. Useful for keeping diversity in results, especially on the first page.