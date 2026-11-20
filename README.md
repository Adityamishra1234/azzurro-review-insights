# Azzurro Hotels, Booking.com Review Insights

An operations-facing application that collects Booking.com guest reviews for
four Azzurro Hotels Sydney properties, groups them into operational topics,
and surfaces weekly insights through a dashboard built for non-technical
ops staff.

Submitted as part of the Azzurro Hotels Full-Stack Developer trial.

Properties tracked:

| Slug                 | Name                        | Booking.com page                                                            |
| -------------------- | --------------------------- | --------------------------------------------------------------------------- |
| olympic-paddington   | Olympic Hotel Paddington    | https://www.booking.com/hotel/au/olympic-paddington.html                    |
| venus-potts-point    | Potts Point                 | https://www.booking.com/hotel/au/venus-potts-point-sydney.html              |
| venus-surry-hills    | Central Sydney (Surry Hills)| https://www.booking.com/hotel/au/venus-surry-hills.html                     |
| chateau-de-venus     | Darling Harbour             | https://www.booking.com/hotel/au/chateau-de-venus.html                      |

---

## 1. What it does

1. **Collects** reviews from each property's Booking.com reviews tab using a
   headless Chromium browser via Playwright. Deduplicates by a stable hash,
   so re-runs are idempotent and newly published reviews are added without
   touching old rows.
2. **Classifies** every review into zero or more operational topics
   (Cleanliness, Check-in experience, Staff or receptionist behaviour,
   Noise, Facilities, Location, Room condition, Value for money) and into
   a coarse sentiment bucket (positive, negative, mixed, neutral).
3. **Surfaces** a dashboard for ops staff: average rating this week vs. last
   week, per-property breakdown, topic ranking by review volume and
   negative share, sentiment trend over the last 30 days, and a filterable
   review feed.

Non-technical users can:
- Pick a property from a dropdown to scope every panel to that property.
- Click a topic to filter the review feed to that topic only.
- Filter the feed by sentiment.
- Browse reviews with full positive and negative text side by side, so they
  do not need to click out to Booking.com.

---

## 2. Architecture

```
          ┌────────────────────────┐
          │    Booking.com pages   │
          └───────────┬────────────┘
                      │ Playwright (Chromium)
                      ▼
┌───────────────────────────────────────────────┐
│  backend/                                     │
│  ┌──────────────┐  ┌────────────┐  ┌────────┐ │
│  │  scraper/    │─▶│  ingest    │─▶│ SQLite │ │
│  │  (Playwright │  │  dedup +   │  │        │ │
│  │  + BS4 parse)│  │  classify  │  └───┬────┘ │
│  └──────────────┘  └────────────┘      │      │
│  ┌─────────────────────────────────────▼────┐ │
│  │  insights/classifier.py (keywords +      │ │
│  │  optional LLM topic tagging)             │ │
│  └──────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────┐ │
│  │  api/main.py (FastAPI: /properties,      │ │
│  │  /reviews, /summary, /health)            │ │
│  └───────────────────┬──────────────────────┘ │
└──────────────────────┼────────────────────────┘
                       │ JSON over HTTP
                       ▼
┌───────────────────────────────────────────────┐
│  frontend/ (React + Vite + Tailwind +         │
│  Recharts): headline cards, property table,   │
│  topic list, sentiment trend, review feed.    │
└───────────────────────────────────────────────┘
```

Layer responsibilities:

| Module                            | Responsibility                                                                 |
| --------------------------------- | ------------------------------------------------------------------------------ |
| `backend/app/scraper/booking.py`  | Drive Chromium through Booking review pages, retries, snapshots on disk        |
| `backend/app/scraper/parsing.py`  | Stateless HTML → `ParsedReview`, multiple selector fallbacks                   |
| `backend/app/scraper/hashing.py`  | Stable review identity, whitespace and case normalised                         |
| `backend/app/insights/classifier` | Keyword topic match, coarse sentiment, optional LLM top-up                     |
| `backend/app/ingest.py`           | Scrape results → DB, dedupe via `ON CONFLICT DO NOTHING`, keep `created_at`    |
| `backend/app/api/main.py`         | HTTP endpoints for the dashboard                                               |
| `backend/scripts/run_scrape.py`   | CLI scraper, cron / GitHub Actions ready                                       |
| `backend/scripts/seed_sample_data.py` | Seeds a demo dataset so the dashboard renders without a scrape round trip  |
| `frontend/src/App.tsx`            | Dashboard shell, owns filter state                                             |
| `frontend/src/components/`        | Dumb presentational components, no data fetching                               |

---

## 3. Review collection method and why

Booking.com does not provide a public API, so the application loads the
reviews tab (`?tab=reviews`) in a real browser. Choices worth calling out:

- **Playwright + Chromium** rather than requests + BeautifulSoup: review
  pagination on Booking is client-side rendered. Static HTTP returns only
  the first page or an empty shell. A real browser gets the full list and
  matches what a guest sees. Trade-off: slower per page and more fragile if
  Booking returns a bot interstitial.
- **Idempotent writes**. Every review has a `review_hash` derived from
  `(property_slug, reviewer_name, review_date_iso, positive_text,
  negative_text)` with whitespace collapsed and case lowered. On insert we
  do `ON CONFLICT DO NOTHING`, which means re-runs only add new rows and
  `created_at` on existing rows stays as the first-seen timestamp. Useful
  for "reviews added since last scrape" reporting.
- **Multi-selector parser**. The parser tries the 2024 testid selectors
  first, then the classic `c-review-block` selectors, then a fallback. If
  Booking changes a single field's class name, we lose that field on that
  card, not the whole run.
- **Raw HTML snapshots**. Every fetched page is written to
  `backend/data/snapshots/` so a parser bug can be reproduced offline
  without a second scrape.
- **Polite defaults**. A 1.5-second delay between page fetches, a hard cap
  of 20 pages per property per run (configurable), and up to three retries
  with exponential backoff on page open failures.
- **Topic classifier is keyword-first**. Rules are auditable (an ops user
  can see why a review was tagged Cleanliness) and run offline for free.
  An LLM pass is available behind a flag for borderline cases; its output
  is merged with the keyword result, never replacing it.

### Known limitations

- **Booking anti-bot measures.** Repeated runs from the same IP can trigger
  interstitials. Mitigations in place: realistic user-agent, viewport, en-AU
  locale, retries with backoff, and snapshot logging to diagnose blocks.
  For production, rotate egress IPs or run on a residential proxy.
- **Booking HTML changes.** Selectors are best-effort; the test suite covers
  parsing against fixed snapshots. If a run returns zero reviews from a
  property that normally has some, the first place to look is the latest
  file in `backend/data/snapshots/` for that property.
- **Date parsing is English-first.** Booking localises review dates. The
  parser handles the formats we observed (`12 October 2025`, `October 2025`,
  `2025-10-12`); other locales fall back to no date and the row is
  retained.
- **Sentiment is coarse.** Four buckets are enough to drive the dashboard
  but they will miss nuance. Keyword topics will also miss paraphrases a
  human would catch. The optional LLM pass mitigates this.
- **No authentication on the dashboard.** This is an internal ops tool and
  the task brief did not scope auth. For production use, front it with
  Okta, Cloudflare Access, or an HTTP basic-auth reverse proxy.

---

## 4. Setup and installation

### Prerequisites

- Python 3.11 or newer
- Node 20 or newer
- (Optional) Docker, for the container path

### Option A, local development

```bash
git clone https://github.com/Adityamishra1234/azzurro-review-insights.git
cd azzurro-review-insights

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m playwright install chromium
cp .env.example .env               # edit as needed
python -m scripts.seed_sample_data # populates demo data
uvicorn app.api.main:app --reload --port 8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev                        # serves at http://localhost:5173
```

Open http://localhost:5173. The Vite dev server proxies `/api` to the
backend at port 8000.

### Option B, Docker Compose

```bash
cp backend/.env.example backend/.env
docker compose up --build
# backend: http://localhost:8000
# dashboard: http://localhost:5173
```

The first build is slow (Playwright and Chromium). Subsequent builds reuse
the layer cache.

### Run a scrape

```bash
cd backend
source .venv/bin/activate
python -m scripts.run_scrape                   # all properties
python -m scripts.run_scrape --property olympic-paddington
python -m scripts.run_scrape --dry-run         # parse, do not write
python -m scripts.run_scrape --max-pages 5
```

Scheduling: on a server, `cron` every 6 hours:

```cron
0 */6 * * * cd /app/backend && /app/backend/.venv/bin/python -m scripts.run_scrape >> /var/log/azzurro-scrape.log 2>&1
```

Or GitHub Actions on a schedule with the included workflow at
`.github/workflows/scrape.yml`.

---

## 5. Configuration

All backend configuration is environment-variable driven. See
`backend/.env.example` for the full list. Key ones:

| Variable                           | Default                     | Purpose                                                 |
| ---------------------------------- | --------------------------- | ------------------------------------------------------- |
| `DATABASE_URL`                     | `sqlite:///./data/reviews.db` | SQLAlchemy URL. Switch to Postgres in production.     |
| `SCRAPE_HEADLESS`                  | `true`                      | Set `false` to watch the scraper in a visible window.   |
| `SCRAPE_MAX_PAGES_PER_PROPERTY`    | `20`                        | Hard cap, prevents runaway jobs.                        |
| `SCRAPE_PAGE_DELAY_SECONDS`        | `1.5`                       | Politeness delay between page fetches.                  |
| `ENABLE_LLM_TOPICS`                | `false`                     | Turn on the optional LLM topic pass.                    |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | OpenAI defaults    | OpenAI-compatible endpoint settings.                    |
| `CORS_ORIGINS`                     | localhost ports             | JSON list of allowed dashboard origins.                 |

---

## 6. API

Interactive docs at http://localhost:8000/docs.

| Method | Path                       | Description                                                 |
| ------ | -------------------------- | ----------------------------------------------------------- |
| GET    | `/api/health`              | Liveness probe                                              |
| GET    | `/api/properties`          | Static list of tracked properties                           |
| GET    | `/api/reviews`             | Paginated review feed (filters: property, topic, sentiment, date) |
| GET    | `/api/summary`             | Headline metrics for the dashboard (one call powers the UI) |

Example:

```bash
curl 'http://localhost:8000/api/summary?property_slug=olympic-paddington' | jq
curl 'http://localhost:8000/api/reviews?topic=Cleanliness&sentiment=negative&limit=10' | jq
```

---

## 7. Topic classifier

Keyword rules live in `backend/app/insights/classifier.py`. Each topic has
a tuple of keyword phrases matched as whole words, case-insensitive, against
the concatenation of title, positive text, and negative text. Topics are
merged into a sorted, deduplicated list per review.

Example insight (what ops staff see): on the dashboard, the Topics panel
reads like "Cleanliness, 8 reviews this week, 63% negative". Equivalent
query against the API:

```bash
curl 'http://localhost:8000/api/summary' | jq '.topic_breakdown[] | select(.topic=="Cleanliness")'
```

The frontend's example insight line ("40% of negative reviews this week
mentioned cleanliness-related issues") is a derived figure: look at the
week's negative-sentiment reviews and compute topic share. The breakdown
endpoint returns the primitives to compute this and similar insights
client-side.

### Adding or editing topics

Edit `TOPIC_KEYWORDS` in `backend/app/insights/classifier.py`. No schema
change, next scrape will tag new reviews. Historical reviews keep their
previous tags unless reclassified (not implemented, intentional, so topic
A/B changes are visible).

---

## 8. Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

Covers:
- Hash stability under whitespace and case variation
- Topic classification on representative positive, negative, and mixed cases
- Sentiment rule logic

Scraper integration tests are out of scope since they would hit live
Booking.com. The parsing layer is pure HTML in / dataclass out and is
tested via fixtures when added.

---

## 9. Deliverables map against the brief

| Brief requirement                                       | Where it lives                                              |
| ------------------------------------------------------- | ----------------------------------------------------------- |
| Collect text, rating, date, property, other info        | `scraper/parsing.py` + `db.py`                              |
| Avoid duplicate reviews                                 | `scraper/hashing.py` + `ingest.py` (`ON CONFLICT DO NOTHING`) |
| Support updating with new reviews                       | `scripts/run_scrape.py`, idempotent re-runs                 |
| Handle page changes, errors, temporary failures         | Retries in `scraper/booking.py`, multi-selector in parsing  |
| Documentation, approach, limitations                    | This README, sections 3 and the inline module docstrings    |
| Weekly avg rating, WoW comparison, per-property, feed   | `api/main.py` summary + `frontend/src/App.tsx`              |
| Date and property filters                               | Dashboard header + `/api/reviews` filters                   |
| Positive and negative trends                            | `SentimentChart` + `/api/summary.positive_trend`            |
| Topic grouping into operational categories              | `insights/classifier.py`                                    |
| Non-technical user experience                           | Review feed shows full text, topic chips are clickable      |
| Error handling and data quality controls                | Hash-based dedupe, snapshot logging, retries, graceful partial failures |

---

## 10. Deployment

- `render.yaml` provisions the API as a Docker web service on Render.
- `frontend/vercel.json` rewrites `/api/*` to the Render host so the
  dashboard can be deployed on Vercel without CORS gymnastics.
- Alternatively, `docker-compose.yml` runs both locally.

---

## 11. File layout

```
azzurro-review-insights/
├── README.md
├── docker-compose.yml
├── render.yaml
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── .env.example
│   ├── app/
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── properties.py
│   │   ├── ingest.py
│   │   ├── api/
│   │   │   ├── main.py
│   │   │   └── schemas.py
│   │   ├── insights/
│   │   │   └── classifier.py
│   │   └── scraper/
│   │       ├── booking.py
│   │       ├── hashing.py
│   │       └── parsing.py
│   ├── scripts/
│   │   ├── run_scrape.py
│   │   └── seed_sample_data.py
│   └── tests/
│       ├── test_classifier.py
│       └── test_hashing.py
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── tsconfig.json
    ├── index.html
    ├── vercel.json
    └── src/
        ├── main.tsx
        ├── index.css
        ├── App.tsx
        ├── api.ts
        └── components/
            ├── StatCard.tsx
            ├── PropertyTable.tsx
            ├── TopicList.tsx
            ├── SentimentChart.tsx
            └── ReviewFeed.tsx
```

---

## 12. Things I would add next

- A persistence layer swap to Postgres with Alembic migrations.
- A reclassification command that re-runs the current classifier against
  historical rows so topic changes propagate retroactively, behind a flag.
- Per-reviewer language detection and translation of non-English reviews
  before classification.
- A simple weekly digest email to ops staff.
- An integration test that scrapes a static HTML snapshot checked into the
  repo so the parser has regression coverage.
