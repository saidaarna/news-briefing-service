"""
Sweeps dedup threshold 0.5→0.9 and prints a Markdown table for the report.

HOW TO RUN (after building the fixture file — see below):
    python scripts/tune_threshold.py > artifacts/threshold_sweep.md
"""
import json
from pathlib import Path

from ai import Article
from src.core.dedup import deduplicate

FIXTURE = Path("tests/fixtures/articles_for_threshold.json")

if not FIXTURE.exists():
    print("ERROR: Fixture file missing.")
    print(f"Create {FIXTURE} — a JSON array of article objects.")
    print('Fields needed: "title", "url", "content", "source"')
    raise SystemExit(1)

articles = [Article(**d) for d in json.loads(FIXTURE.read_text())]
print(f"Loaded {len(articles)} articles.\n")

print("| threshold | survivors | dropped |")
print("|-----------|-----------|---------|")
for t in (0.5, 0.6, 0.7, 0.8, 0.9):
    out = deduplicate(articles, threshold=t)
    dropped = len(articles) - len(out)
    print(f"| {t:.1f}       | {len(out):<9} | {dropped:<7} |")

print()
print("Fill in which drops were correct/wrong by hand. Pick the threshold")
print("where the most drops are true duplicates (precision is highest).")