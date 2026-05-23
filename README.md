# AI News Briefing Service

**AI Academy · National AI Center · Spring 2026 — Topic 3**

A scheduled service that fetches articles from multiple news sources concurrently, deduplicates near-identical stories, categorizes them by topic, and produces a personalized daily Markdown digest for a given user.

---

## Team

| Member | Contribution |
|---|---|
| Saida (arabovasaida@gmail.com) | Fetch service, pipeline orchestration, config, CLI, Docker |
| Leman Mirzeyeva | Digest builder, repository layer, core unit tests |
| Nigar Rustamova | AI service (retry/cache/dedup), filter, dedup wiring tests |
| Nazrin | CLI skeleton, pipeline integration |

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/saidaarna/news-briefing-service.git
cd news-briefing-service
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
pip install -r requirements.txt -r requirements-ai.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

### 3. Run the offline demo (no API keys needed)

```bash
python demo_ai.py --offline
```

### 4. Run the full daily pipeline

```bash
python -m src run-daily --user saida
```

This produces a digest at `digests/YYYY-MM-DD-saida.md`.

---

## Environment Variables

All configuration is read from `.env`. See `.env.example` for the full list.

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_PROVIDER` | yes | `anthropic` | `anthropic` \| `openai` \| `gemini` |
| `LLM_MODEL` | yes | `claude-sonnet-4-6` | Provider-specific model ID |
| `ANTHROPIC_API_KEY` | if provider=anthropic | — | Anthropic API key |
| `OPENAI_API_KEY` | if provider=openai or embedding_provider=openai | — | OpenAI API key |
| `GOOGLE_API_KEY` | if provider=gemini | — | Google API key |
| `EMBEDDING_PROVIDER` | yes | `openai` | `openai` \| `gemini` |
| `EMBEDDING_MODEL` | yes | `text-embedding-3-small` | Embedding model ID |
| `DATABASE_URL` | yes | `postgresql+asyncpg://postgres:dev@localhost:5432/newsbrief` | asyncpg connection string |
| `FETCH_TIMEOUT_SECONDS` | no | `15` | Per-source HTTP timeout |
| `MAX_PARALLEL_FETCHES` | no | `8` | Semaphore bound for fetch concurrency |
| `DEDUP_NEAR_DUPLICATE_THRESHOLD` | no | `0.70` | Jaccard similarity cutoff |
| `AI_SEMAPHORE_LIMIT` | no | `5` | Max concurrent AI calls |
| `LLM_MAX_RETRIES` | no | `3` | Max retry attempts per AI call |
| `LLM_TIMEOUT_SECONDS` | no | `30.0` | Hard timeout per AI call |
| `LOG_LEVEL` | no | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |

---

## How to Test

```bash
# Run all tests (offline, no network required)
python -m pytest tests/ -v

# With coverage report
python -m pytest tests/ --cov=src --cov-report=term-missing

# Run just the AI smoke tests (must always pass)
python -m pytest tests/test_ai_smoke.py -v
```

**Coverage:** 81% (target ≥60%)

---

## Parallel vs. Sequential Benchmark

Fetch service uses `asyncio.gather` bounded by a `Semaphore(8)` to fetch all sources concurrently.

| Mode | Sources | Time |
|---|---|---|
| Sequential (one at a time) | 6 | ~18–22 s |
| Concurrent (`asyncio.gather + Semaphore(8)`) | 6 | ~3–5 s |
| **Speedup** | | **~5×** |

To reproduce the benchmark yourself:

```bash
python scripts/bench.py
```

This script times sequential vs. concurrent fetch over the configured sources and prints the results.

---

## Docker

```bash
# Build the image
docker build -t news-briefing-service .

# Run with environment variables
docker run --env-file .env news-briefing-service
```

The container runs `python -m src run-daily --user saida` by default.

To override the user:

```bash
docker run --env-file .env news-briefing-service python -m src run-daily --user khagani
```

---

## Architecture

```
src/
├── config.py              # pydantic-settings, typed env config
├── models.py              # SE-layer Pydantic models (Source, UserProfile, …)
├── cli.py                 # argparse CLI entry point
├── services/
│   ├── ai_service.py      # AIService: cache + semaphore + retry around ai.*
│   └── fetch_service.py   # FetchService: async aiohttp + RSS/HTML parsing
├── core/
│   ├── dedup.py           # Two-stage dedup: URL/hash → near_duplicate
│   ├── digest_builder.py  # Markdown digest generation
│   ├── caching.py         # File-based content cache
│   └── filter.py          # User preference filtering
├── concurrency/
│   └── pipeline.py        # Orchestrates fetch → dedup → AI → digest
└── storage/
    └── repository.py      # PostgreSQL user profile repository
```

**AI module boundary:** all calls to the LLM go through `AIService.label()` — never directly to `ai.*` from business logic.

---

## Key Design Decisions

- **Two-stage dedup:** cheap URL canonicalization + SHA-256 hash runs first (eliminates 50–80% of duplicates). Only survivors go through Jaccard near-duplicate check (threshold=0.70, configurable).
- **Cache by content hash:** re-running the digest on the same article never re-calls the LLM.
- **Semaphore-bounded AI calls:** `AI_SEMAPHORE_LIMIT` (default 5) prevents provider 429 errors.
- **Graceful degradation:** a failed source returns a `FetchResult(error=...)` — the pipeline continues with the remaining sources.
- **Provider-agnostic:** `LLM_PROVIDER` switches between Anthropic, OpenAI, and Gemini with no code change.
