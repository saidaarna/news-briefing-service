# Contribution Statement

**Team:** AIngels
**Topic:** Topic 3 — AI News Briefing Service
**Repository:** [https://github.com/saidaarna/news-briefing-service](https://github.com/saidaarna/news-briefing-service)
**Final tag:** `v1.0-final`
**Submission date:** 2026-05-24

---

## Member 1 — Saida Arabova 

**Owned (sole author):**
- `src/services/fetch_service.py` — async aiohttp fetch service supporting RSS (feedparser) and HTML (BeautifulSoup) sources with concurrent `asyncio.gather + Semaphore(8)`, retry, and structured logging
- `src/config.py` — all pydantic-settings typed configuration, env validation, provider key checks
- `src/models.py` — SE-layer Pydantic models (`Article`, `UserProfile`, `Source`, `FetchResult`, `LabeledSummary`)
- `src/app.py` — Streamlit Web UI (AIngels dashboard) with dark feminine theme, topic filtering, sentiment badges, View/Generate dual mode, JSON profile fallback
- `tests/test_concurrency.py` — asyncio.gather, semaphore bounding, partial failure isolation tests
- `tests/test_end_to_end.py` — full E2E pipeline mocked tests (happy path, all-fail, AI-fail)
- `tests/test_services.py` — AIService unit tests (cache hit, retry, timeout, corrupt cache)
- `data/rss_feeds.txt` — 12 configured news sources (English + Azerbaijani)
- `data/user_profile.json` — 4 user profiles with real excluded sources
- `README.md` — full project documentation following template
- `CONTRIBUTION_STATEMENT.md` — this file
- Project setup, CI wiring, final integration, tag management, `--no-db` CLI flag

**Co-owned:**
- `src/cli.py` (with Nazrin — added `--no-db` flag and JSON fallback on top of Nazrin's original skeleton)
- `src/concurrency/pipeline.py` (with Nazrin — added mypy type-guards and reviewed integration)
- `docker-compose.yml` — reviewed and fixed healthcheck, volume mounts

**Reviewed:**
- All PRs from Laman, Nigar, and Nazrin before final merge into `main`

---

## Member 2 — Laman Mirzayeva

**Owned (sole author):**
- `src/core/digest_builder.py` — `DigestBuilder` class that generates a personalized Markdown digest filtered by user preferences (preferred topics, blocked sources, max items per topic)
- `src/core/caching.py` — SHA-256 file-based content cache; cache hits bypass the semaphore entirely
- `src/storage/repository.py` — abstract `UserRepository` base class (ABC) + `PostgresUserRepository` implementation via `asyncpg`; `initialize_db()` creates table and seeds all 4 user profiles
- `tests/test_core.py` — unit tests for `DigestBuilder`, `ContentCache`, and the filter logic
- `tests/test_storage.py` — integration tests for `PostgresUserRepository` using `AsyncMock`

**Co-owned:**
- `src/core/filter.py` (with Nigar — defined interface, Nigar implemented `apply_user_preferences`)

**Reviewed:**
- Nigar's `ai_service.py` and dedup module during integration

---

## Member 3 — Nigar Rustamova

**Owned (sole author):**
- `src/services/ai_service.py` — `AIService` wrapper around `ai.summarize_and_label` with:
  - SHA-256 file-based cache (cache check before semaphore acquisition)
  - `asyncio.Semaphore(5)` concurrency cap
  - `asyncio.to_thread` for running synchronous LLM calls without blocking the event loop
  - `tenacity` exponential backoff (1s → 2s → 4s → 8s, max 4 attempts, `ProviderError` only)
  - `asyncio.wait_for` hard per-attempt timeout
  - Automatic corrupt cache file recovery
- `src/core/dedup.py` — two-stage deduplication:
  - Stage 1 O(n): UTM param stripping, canonical URL dedup, body SHA-256 hash dedup
  - Stage 2 O(n²): Jaccard word k-shingle similarity with configurable threshold (0.70, justified by threshold sweep)
- `src/core/filter.py` — `apply_user_preferences()`: excluded source drop, topic filter, per-topic item cap (case-insensitive)
- `tests/test_dedup.py` — UTM drop, paraphrase catch, high-threshold behaviour, bad URL handling tests
- `tests/test_ai_service.py` — cache hit, retry on error, give-up after max retries, timeout propagation, corrupt cache recovery tests
- `artefacts/failure_llm_429.log` — failure injection run (3× rate-limit errors → success)
- `artefacts/threshold_sweep.md` — dedup threshold sweep 0.5→0.9 across hand-labelled fixture

**Co-owned:**
- `src/core/filter.py` interface definition (with Laman)

**Reviewed:**
- Saida's `fetch_service.py` semaphore integration
- Nazrin's pipeline wiring of the dedup and filter stages

---

## Member 4 — Nazrin Aliyeva

**Owned (sole author):**
- `src/concurrency/pipeline.py` — end-to-end pipeline orchestrating fetch → dedup → AI label → digest; isolates failures per source/article; structured logging at every stage
- `src/cli.py` — argparse CLI (`python -m src run-daily --user <name>`); module entry point
- `scripts/bench.py` — sequential vs concurrent fetch benchmark; prints comparison table
- `Dockerfile` — multi-stage Python 3.12 image (builder + slim runtime)
- `.dockerignore` — excludes venv, cache, digests from Docker context
- `tests/test_pipeline.py` — pipeline happy path, AI failure graceful skip, source failure isolation; all offline with `AsyncMock`

**Co-owned:**
- `src/cli.py` (with Saida — Saida added `--no-db` and JSON fallback on top)
- `docker-compose.yml` (with Saida — Nazrin wrote initial version, Saida reviewed)

**Reviewed:**
- Saida's `fetch_service.py` integration into the pipeline
- Laman's `repository.py` connection setup



## AI Tool Disclosure

We used AI coding assistants as follows:

| Module / file | Assistant | What we did with it |
|---|---|---|
| `src/app.py` | Claude (Antigravity) | Full Web UI drafted by assistant; team reviewed all CSS, logic, and DB fallback; confirmed it runs correctly against our digest format |
| `src/cli.py` (`--no-db` flag) | Claude (Antigravity) | JSON fallback logic drafted; team reviewed and confirmed it matches our `UserProfile` model exactly |
| `tests/test_concurrency.py`, `test_end_to_end.py`, `test_services.py` | Claude (Antigravity) | Test skeletons generated; team reviewed every assertion, fixed 3 env-patching bugs, and confirmed 84 tests pass |
| `README.md` | Claude (Antigravity) | Drafted from team-provided bullet points; team reviewed every command and table for accuracy |
| `src/services/ai_service.py` | Claude (Anthropic) | Tenacity backoff pattern suggested; Nigar rewrote the semaphore ordering and corrupt-cache recovery after testing |
| `src/core/dedup.py` | Claude (Anthropic) | Jaccard shingle approach suggested; Nigar implemented the two-stage split and ran the threshold sweep to justify 0.70 |


---

## Signatures

By signing below, we affirm that:
- The contributions described above are accurate.


| Member | Signature | Date |
|---|---|---|
| Saida Arabova | __________________________ | 2026-05-24 |
| Laman Mirzayeva | __________________________ | 2026-05-24 |
| Nigar Rustamova | __________________________ | 2026-05-24 |
| Nazrin Aliyeva | __________________________ | 2026-05-24 |
