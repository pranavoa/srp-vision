# Mirador — SRP Phase 1 Simulator

> **Mirador** (Spanish for *lookout*) — you go there to see clearly.

An interactive simulator for the OnArrival hotel SRP. Pulls candidates from
the live Elastic index using the production query shape, applies the
**Phase 1** scoring formula, and lets you tune every knob in real time
without re-querying.

> **Formula**
>
> `final = adjusted_rating × max(aff_floor, affinity^λ_s) × max(decay_floor, decay(d)^λ_d)`
>
> - `adjusted_rating` — Bayesian-shrunk user rating
> - `affinity` — star-tier match (full 3×3 matrix in Hotel mode, flat per-★ vector elsewhere)
> - `decay(d)` — Gaussian distance decay from anchor (only when an anchor exists)

See [`docs/ranking-phase-1.md`](docs/ranking-phase-1.md) and
[`docs/ranking-phase-1-distance.md`](docs/ranking-phase-1-distance.md) for the
full PRD; [`docs/elastic-schema.md`](docs/elastic-schema.md) covers the index
shape and the production query template.

## Features

- **Three search modes**: Hotel (with autocomplete + anchor pin), Location
  (Country / State / City / Area with cascading dropdowns and bbox/centroid
  resolution), Landmark (preset library + custom coords).
- **Production-parity ES query**: `hotelRating ≥ 3` + `hasImages = true` +
  provider availability + `geo_bounding_box` + `geo_distance` sort.
- **Per-context affinity**: Hotel uses the full 3×3 matrix; Landmark / Area /
  City / State / Country each have their own flat per-hotel-★ weight vector.
- **Live re-rank**: change any knob (`m`, `λ_s`, `λ_d`, `offset_km`, `scale_km`,
  affinity weights, floors) and the table re-sorts instantly without hitting ES.
- **Save / load profiles**: download current weights as JSON, or promote them
  to `user_defaults.json` so new sessions start tuned.
- **Light + dark themes**: Notion-inspired light, Apple-inspired glass-dark.

## Quickstart

```bash
git clone <repo> && cd srp-phase1-simulator
pip install -r requirements.txt

# Configure credentials — pick one:
cp .env.example .env                                        # for env vars
# OR
cp .streamlit/secrets.toml.example .streamlit/secrets.toml  # for st.secrets

# Edit either file with a real ES_API_KEY, then:
streamlit run app.py
```

Open `http://localhost:8501`.

## Project layout

```
srp-phase1-simulator/
├── app.py                         # Streamlit entry point — UI orchestration
├── srp_simulator/                 # Application package
│   ├── config.py                  # Env vars, factory defaults, presets
│   ├── elastic.py                 # ES query builders + helpers
│   ├── scoring.py                 # Pure scoring (testable, no Streamlit)
│   ├── persistence.py             # load / save user defaults
│   └── theme.py                   # Light + dark CSS
├── docs/                          # PRD + ES schema reference
├── static/fonts/                  # Ubuntu Sans Mono (numerics, KPIs)
├── .streamlit/
│   ├── config.toml                # Static serving + theme defaults
│   └── secrets.toml.example       # Template (real one is gitignored)
├── requirements.txt
├── .env.example
└── .gitignore
```

## Configuration

Credentials are read from environment variables first, then `st.secrets`,
then a safe non-secret default for URL / index. **`ES_API_KEY` has no
default** — the app fails fast with a clear message if it's not configured.

| Key | Required | Source |
|---|---|---|
| `ES_API_KEY` | yes | `.env` or `.streamlit/secrets.toml` |
| `ES_URL` | no | env / secrets / safe default |
| `ES_INDEX` | no | env / secrets / safe default |
| `APP_PASSWORD` | no | legacy single-password gate (unused once Google auth is on) |

### Google OIDC auth (domain-restricted)

The app can require Google sign-in restricted to a single email domain
(e.g. `@onarrival.travel`). It's a no-op when not configured, so local
dev and pre-auth deploys keep working.

To enable, add an `[auth]` block to `.streamlit/secrets.toml` (or paste it
into the Streamlit Cloud secrets UI):

```toml
[auth]
redirect_uri        = "https://<your-app>.streamlit.app/oauth2callback"
cookie_secret       = "<random 32+ char string>"
client_id           = "<from Google Cloud Console>"
client_secret       = "<from Google Cloud Console>"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

The allowed domain lives in [`app.py`](app.py) — change the
`require_auth(allowed_domain=...)` call to allow a different one.

**Google Cloud Console setup (one-time):**
1. APIs & Services → Credentials → Create OAuth client ID → Web application
2. Authorized redirect URI: `https://<your-app>.streamlit.app/oauth2callback`
3. Copy the client ID + secret into the `[auth]` block above

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app** →
   pick the repo, branch, and `app.py`.
3. Open **Advanced settings → Secrets** and paste:
   ```toml
   ES_URL    = "..."
   ES_INDEX  = "..."
   ES_API_KEY = "..."

   [auth]
   # ... fill from the section above
   ```
4. Deploy. Future pushes to the branch auto-redeploy.

## Scoring knobs (sidebar)

| Knob | Default | Effect |
|---|---|---|
| `m` | 50 | Bayesian prior weight (higher = more skeptical of low-review hotels) |
| `global_avg` | 4.30 | Platform-wide rating mean |
| `λ_s` | 1.0 | Star-affinity strength (0 = ignore stars, 2 = strict tier match) |
| `λ_d` | 1.0 | Distance-decay strength |
| `offset_km` | 0.5 | Free zone — distance ≤ offset doesn't penalize |
| `scale_km` | 5.0 | Decay reaches 0.5 at `offset + scale` |
| `aff_floor` | 0.15 | Minimum star factor |
| `decay_floor` | 0.15 | Minimum distance factor |
| `default_affinity` | 0.45 | Fallback for hotels with ★ outside 3-5 |

## Sort tabs

| Sort | Order |
|---|---|
| Recommended | `final_score` desc; in Hotel mode, the picked anchor is pinned at #1 |
| Popularity | `adjusted_rating` desc |
| Nearby | distance asc, then `final_score` |
| Hotel Stars | `hotelRating` desc, then `final_score` |

## License

MIT — see [`LICENSE`](LICENSE).
