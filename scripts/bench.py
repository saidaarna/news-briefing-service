"""
Sequential vs concurrent fetch benchmark.
Run: python scripts/bench.py
Paste the printed table into README.md under the Benchmarks section.
"""
import asyncio
import statistics
import time
import logging

logging.disable(logging.CRITICAL)  # silence logs during benchmark

RUNS = 3

async def run_sequential(svc, sources):
    results = []
    for source in sources:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            result = await svc._fetch_one(session, source)
            results.append(result)
    return results

async def run_concurrent(svc):
    return await svc.fetch_all()

def main():
    from src.config import settings
    from src.services.fetch_service import FetchService, load_rss_sources

    svc = FetchService(settings)
    sources = load_rss_sources(settings.rss_feeds_file)

    if not sources:
        print("No sources found. Check data/rss_feeds.txt")
        return

    seq_times, con_times = [], []

    for i in range(RUNS):
        print(f"Run {i+1}/{RUNS}...", end=" ", flush=True)

        t0 = time.perf_counter()
        asyncio.run(run_sequential(svc, sources))
        seq_times.append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        asyncio.run(run_concurrent(svc))
        con_times.append(time.perf_counter() - t0)

        print("done")

    seq_avg = statistics.mean(seq_times)
    con_avg = statistics.mean(con_times)
    speedup = seq_avg / con_avg if con_avg > 0 else 0

    print()
    print(f"{'Mode':<14} {'Avg (s)':>10} {'Min (s)':>10} {'Max (s)':>10}")
    print("-" * 46)
    print(f"{'Sequential':<14} {seq_avg:>10.2f} {min(seq_times):>10.2f} {max(seq_times):>10.2f}")
    print(f"{'Concurrent':<14} {con_avg:>10.2f} {min(con_times):>10.2f} {max(con_times):>10.2f}")
    print(f"\nSpeedup: {speedup:.1f}x  |  Sources: {len(sources)}  |  Runs: {RUNS}")
    print()
    print("Copy this table into README.md under ## Benchmarks")

if __name__ == "__main__":
    main()