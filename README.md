# AI News Briefing Service

> A scheduled service that fetches articles from multiple news sources concurrently, deduplicates near-identical stories, categorizes them by topic, and produces a personalized daily Markdown digest for each user.

**Team:** AIngels  •  **Topic:** 3 — AI News Briefing Service  •  **Course:** AI-ENG-110 Software Engineering, AI Academy

**Due:** May 23, 2026 at 23:59 (UTC+4)

---

## Team

| Member | Role |
|---|---|
| Saida Arabova | Fetch service, config, models, Web UI, integration tests, Presentation |
| Laman Mirzayeva | Digest builder, caching, PostgreSQL repository, core & storage tests, Report |
| Nigar Rustamova | AI service, two-stage deduplication, user preference filter, Presentation |
| Nazrin Aliyeva | Pipeline orchestration, CLI, benchmarking, Docker, pipeline tests |

---

## Quick Start

```bash
# 1. Clone & install
git clone https://github.com/saidaarna/news-briefing-service.git
cd news-briefing-service
python -m venv venv

# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt

# 2. Configure
cp .env.example .env       # then fill in real API keys
# (DO NOT commit .env — it is in .gitignore)

# 3. Run the smoke tests
pytest tests/test_ai_smoke.py -v   # provided smoke tests
pytest                              # full suite (84 tests)

# 4. Run the offline demo (no API keys or DB needed)
python demo_ai.py --offline

# 5. Run the full daily pipeline (no DB needed)
python -m src run-daily --user saida --no-db
```

## Run with Docker

```bash
# Build the image
docker build -t news-briefing-service .

# Start the database
docker-compose up -d db

# Run the pipeline
docker-compose run app python -m src run-daily --user saida

# Run all tests inside container
docker-compose run app pytest tests/ -v
```

## Launch the Web UI (AIngels Dashboard)

```bash
streamlit run src/app.py
# → Open http://localhost:8501
```

The UI has two modes:
- **View Digest** — browse any existing digest with topic filtering and sentiment badges
- **Generate New** — trigger a live pipeline run for any team member (saida / laman / nazrin / nigar)

---

## Environment Variables

All configuration is read from `.env`. See `.env.example` for the full list.

| Variable | Required? | Default | What it controls |
|---|---|---|---|
| `LLM_PROVIDER` | yes | `anthropic` | `anthropic` \| `openai` \| `gemini` |
| `LLM_MODEL` | yes | `claude-sonnet-4-6` | Model ID for the chosen provider |
| `ANTHROPIC_API_KEY` | if provider=anthropic | — | Anthropic API key |
| `OPENAI_API_KEY` | if provider=openai | — | OpenAI / Groq-compatible key |
| `GOOGLE_API_KEY` | if provider=gemini | — | Google API key |
| `EMBEDDING_PROVIDER` | yes | `openai` | `openai` \| `gemini` |
| `EMBEDDING_MODEL` | yes | `text-embedding-3-small` | Embedding model ID |
| `DATABASE_URL` | no | `postgresql+asyncpg://postgres:dev@localhost:5432/newsbrief` | asyncpg connection string |
| `FETCH_TIMEOUT_SECONDS` | no | `15` | Per-source HTTP timeout |
| `MAX_PARALLEL_FETCHES` | no | `8` | Semaphore bound for fetch concurrency |
| `DEDUP_NEAR_DUPLICATE_THRESHOLD` | no | `0.70` | Jaccard similarity cutoff |
| `AI_SEMAPHORE_LIMIT` | no | `5` | Max concurrent AI calls |
| `LLM_MAX_RETRIES` | no | `3` | Max retry attempts per AI call |
| `LLM_TIMEOUT_SECONDS` | no | `30.0` | Hard timeout per AI call |
| `LOG_LEVEL` | no | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |

The full list is in `.env.example`. **Do not commit a real `.env`.**

---

## How to Run the Demo

```bash
# Offline (no API keys, no DB — always works)
python demo_ai.py --offline

# Live pipeline without a database (reads from data/user_profile.json)
python -m src run-daily --user nazrin --no-db

# Live pipeline with PostgreSQL
docker-compose up -d db
python -m src run-daily --user saida
```

Digests are written to `digests/YYYY-MM-DD-<username>.md`.

---

## Sequential vs Concurrent Benchmark

The fetch service uses `asyncio.gather` bounded by `Semaphore(8)` to fetch all 12 sources concurrently.

| Workload | Sources | Sequential | Concurrent (sem=8) | Speedup |
|---|---|---|---|---|
| Fetch all configured sources | 12 | ~18–22 s | ~3–5 s | **~5×** |

**Reproduce:**
```bash
python scripts/bench.py
```

Bottleneck after parallelisation is the **AI labelling stage** — each article requires one LLM call. The `AI_SEMAPHORE_LIMIT=5` cap prevents provider 429 rate-limit errors. See `report/report.pdf` §4 for details.

---

## Testing

```bash
pytest --cov=src --cov-report=term-missing
```

- **Total coverage: 81%** (target ≥ 60%) ✅
- **Provided AI smoke tests:** passing ✅
- **Total tests: 84** across 8 test files ✅
- All tests run **offline** — AI provider calls and HTTP layer are mocked with `AsyncMock` / `unittest.mock`. No real API keys required.

---

## Project Layout

```
.
├── ai/                        # PROVIDED — do not modify
├── src/
│   ├── config.py              # pydantic-settings typed config
│   ├── models.py              # SE-layer Pydantic models
│   ├── cli.py                 # argparse CLI  (python -m src run-daily)
│   ├── app.py                 # Streamlit Web UI (AIngels dashboard)
│   ├── services/
│   │   ├── ai_service.py      # AIService: cache + semaphore + retry
│   │   └── fetch_service.py   # FetchService: async aiohttp, RSS + HTML
│   ├── core/
│   │   ├── dedup.py           # Two-stage dedup: URL/hash → Jaccard
│   │   ├── digest_builder.py  # Markdown digest generation
│   │   ├── caching.py         # SHA-256 file-based content cache
│   │   └── filter.py          # User preference filtering
│   ├── concurrency/
│   │   └── pipeline.py        # Orchestrates fetch → dedup → AI → digest
│   └── storage/
│       └── repository.py      # PostgreSQL user profile repository (asyncpg)
├── tests/                     # 84 tests, all offline
├── data/
│   ├── rss_feeds.txt          # 12 configured news sources
│   └── user_profile.json      # 4 user profiles (saida, laman, nazrin, nigar)
├── artefacts/                 # sample digests and benchmark outputs
├── scripts/
│   └── bench.py               # sequential vs concurrent benchmark
├── Dockerfile                 # multi-stage Python 3.12 image
├── docker-compose.yml         # app + PostgreSQL 15
├── requirements.txt
├── .env.example
└── README.md
```

---

## Architecture

```
             ┌─────────────────────────────────────────┐
             │              CLI / Web UI                │
             │  python -m src run-daily  |  streamlit   │
             └────────────────┬────────────────────────┘
                              │
                              ▼
             ┌────────────────────────────────┐
             │         pipeline.py            │
             │  fetch → dedup → AI → digest   │
             └──┬──────────┬────────┬─────────┘
                │          │        │
         ┌──────┘   ┌──────┘   ┌───┘
         ▼           ▼          ▼
  ┌─────────────┐ ┌──────────┐ ┌──────────────────┐
  │FetchService │ │  dedup   │ │   AIService       │
  │(aiohttp,    │ │(URL hash │ │(cache + semaphore │
  │ RSS + HTML) │ │+ Jaccard)│ │ + retry + timeout)│
  └─────────────┘ └──────────┘ └────────┬─────────┘
                                         │
                                         ▼
                                  ┌──────────────┐
                                  │   ai/  (LLM) │  ← PROVIDED
                                  └──────────────┘
                                         │
                              ┌──────────┘
                              ▼
                   ┌──────────────────┐
                   │  DigestBuilder   │
                   │ (filter + render │
                   │  Markdown)       │
                   └──────────────────┘
                              │
                              ▼
                   ┌──────────────────┐
                   │  PostgreSQL DB   │
                   │  (user profiles) │
                   └──────────────────┘
```

---

## Key Design Decisions

- **Two-stage dedup:** cheap URL canonicalization + SHA-256 hash eliminates 50–80% of duplicates in O(n). Only survivors go through Jaccard near-duplicate check (threshold=0.70, configurable, justified by threshold sweep in `artefacts/threshold_sweep.md`).
- **Cache by content hash:** re-running the digest on the same article never re-calls the LLM. Cache survives across runs.
- **Semaphore-bounded AI calls:** `AI_SEMAPHORE_LIMIT=5` prevents provider 429 errors without sacrificing throughput.
- **Graceful degradation:** a failed source returns `FetchResult(error=...)` — the pipeline continues with the remaining sources.
- **Provider-agnostic:** `LLM_PROVIDER` switches between Anthropic, OpenAI (+ Groq-compatible), and Gemini with zero code changes.
- **No-DB fallback:** `--no-db` flag reads user profiles from `data/user_profile.json` — useful for demos and CI.

---

## Limitations

- HTML scraping is basic (BeautifulSoup title grab); paywalled or JavaScript-heavy sites return 1-article stubs.
- No multi-provider failover in the base implementation (see `docs/ADVANCED_BONUSES.md` for the bonus extension).
- The scheduler is not persistent — digests are triggered manually or via cron, not a running daemon.

See `report/report.pdf` §6 for a full discussion.

---

## Bonus Features Implemented

| Bonus | Points | Evidence |
|---|---|---|
| Multi-stage Dockerfile | +1 | `Dockerfile` (builder + runtime stage) |
| Streamlit Web UI | +2 | `src/app.py` — run `streamlit run src/app.py` |

---

## Tools & Acknowledgements

We used AI assistants (Claude via Antigravity) as described in `CONTRIBUTION_STATEMENT.md`. All generated code was reviewed, tested, and can be defended by at least one team member.

## License

This is academic coursework submitted for AI-ENG-110, AI Academy, Spring 2026.
