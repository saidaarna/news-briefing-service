"""
Web UI for the AI News Briefing Service.

Runs via:
    streamlit run src/app.py

Two modes:
  1. View Mode  — browse existing digest files in digests/
  2. Live Mode  — trigger a real pipeline run (requires DB + API keys)
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

import streamlit as st

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI News Briefing",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Sidebar */
  [data-testid="stSidebar"] {background: #0f1117;}
  [data-testid="stSidebar"] h1,
  [data-testid="stSidebar"] label {color: #e0e0e0;}

  /* Article cards */
  .article-card {
      background: #1a1d27;
      border: 1px solid #2d3148;
      border-left: 4px solid #5865f2;
      border-radius: 8px;
      padding: 1rem 1.2rem;
      margin-bottom: 1rem;
  }
  .article-card h3 {margin-top:0; color:#e8eaf6; font-size:1.05rem;}
  .tag {
      display: inline-block;
      padding: 2px 10px;
      border-radius: 12px;
      font-size: 0.75rem;
      font-weight: 600;
      margin-right: 6px;
  }
  .tag-topic  {background:#1e3a5f; color:#90caf9;}
  .tag-pos    {background:#1b3a2a; color:#66bb6a;}
  .tag-neg    {background:#3e1e1e; color:#ef9a9a;}
  .tag-neutral{background:#2c2c2c; color:#b0bec5;}
  .stat-card  {
      background:#1a1d27; border:1px solid #2d3148;
      border-radius:8px; padding:0.8rem 1.2rem;
      text-align:center;
  }
  .stat-card .num {font-size:2rem; font-weight:700; color:#7986cb;}
  .stat-card .lbl {font-size:0.8rem; color:#9e9e9e; margin-top:4px;}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

DIGESTS_DIR = Path("digests")
SENTIMENT_CLASS = {"positive": "pos", "negative": "neg", "neutral": "neutral",
                   "POSITIVE": "pos", "NEGATIVE": "neg", "NEUTRAL": "neutral"}


def _list_digests() -> list[Path]:
    """Return all digest .md files sorted newest first."""
    if not DIGESTS_DIR.exists():
        return []
    return sorted(DIGESTS_DIR.glob("*.md"), reverse=True)


def _parse_digest(path: Path) -> dict:
    """Parse a digest .md file into structured data for display."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    articles: list[dict] = []
    current: dict | None = None

    for line in lines:
        line = line.strip()
        if line.startswith("## "):
            if current:
                articles.append(current)
            current = {"title": line[3:], "source": "", "topic": "",
                       "sentiment": "", "summary": "", "url": ""}
        elif current and line.startswith("- **Source:**"):
            current["source"] = line.replace("- **Source:**", "").strip()
        elif current and line.startswith("- **Topic:**"):
            parts = line.replace("- **Topic:**", "").split("|")
            current["topic"] = parts[0].strip()
            if len(parts) > 1:
                current["sentiment"] = parts[1].replace("**Sentiment:**", "").strip()
        elif current and line.startswith("- **Summary:**"):
            current["summary"] = line.replace("- **Summary:**", "").strip()
        elif current and line.startswith("- [Read Original"):
            m = re.search(r"\((https?://[^\)]+)\)", line)
            if m:
                current["url"] = m.group(1)

    if current:
        articles.append(current)

    # Extract header metadata
    date_str = ""
    user = ""
    for line in lines[:5]:
        if line.startswith("# Daily News Briefing"):
            m = re.search(r"\d{4}-\d{2}-\d{2}", line)
            date_str = m.group(0) if m else ""
        if line.startswith("User:"):
            user = line.replace("User:", "").strip()

    return {"date": date_str, "user": user, "articles": articles, "raw": text}


def _render_article(art: dict, idx: int) -> None:
    """Render a single article as a styled card."""
    topic = art["topic"].split(".")[-1] if "." in art["topic"] else art["topic"]
    sentiment = art["sentiment"].split(".")[-1].lower() if "." in art["sentiment"] else art["sentiment"].lower()
    sent_class = SENTIMENT_CLASS.get(sentiment, "neutral")
    sent_emoji = {"pos": "🟢", "neg": "🔴", "neutral": "⚪"}.get(sent_class, "⚪")

    st.markdown(f"""
<div class="article-card">
  <h3>{art['title']}</h3>
  <span class="tag tag-topic">{topic}</span>
  <span class="tag tag-{sent_class}">{sent_emoji} {sentiment}</span>
  <span style="font-size:0.8rem;color:#9e9e9e;"> · {art['source']}</span>
  <p style="color:#cfd8dc;margin-top:0.8rem;font-size:0.92rem;">{art['summary']}</p>
  {'<a href="' + art["url"] + '" target="_blank" style="font-size:0.8rem;color:#7986cb;">🔗 Read original</a>' if art["url"] else ''}
</div>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📰 News Briefing")
    st.markdown("---")
    mode = st.radio("Mode", ["📁 View Existing Digest", "🚀 Generate New Digest"])
    st.markdown("---")

    if mode == "📁 View Existing Digest":
        digests = _list_digests()
        if not digests:
            st.warning("No digests found in `digests/`.")
            selected_path = None
        else:
            labels = [p.name for p in digests]
            chosen = st.selectbox("Select digest", labels)
            selected_path = DIGESTS_DIR / chosen
    else:
        username = st.text_input("Username", value="saida",
                                 help="Must exist in the database")
        run_btn = st.button("▶ Run Pipeline", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown(
        "<small style='color:#616161;'>AI News Briefing Service<br/>Spring 2026 · AI Academy</small>",
        unsafe_allow_html=True,
    )

# ── Main area ─────────────────────────────────────────────────────────────────

st.markdown("# 📰 AI News Briefing Service")

# ── VIEW MODE ────────────────────────────────────────────────────────────────

if mode == "📁 View Existing Digest":
    if not _list_digests():
        st.info("No digests yet. Switch to **Generate New Digest** mode or run `python -m src run-daily --user saida` first.")
        st.stop()

    data = _parse_digest(selected_path)

    # Header stats
    arts = data["articles"]
    topics = list({a["topic"].split(".")[-1] for a in arts if a["topic"]})
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="stat-card"><div class="num">{len(arts)}</div><div class="lbl">Articles</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="stat-card"><div class="num">{len(topics)}</div><div class="lbl">Topics</div></div>', unsafe_allow_html=True)
    with col3:
        pos = sum(1 for a in arts if "pos" in SENTIMENT_CLASS.get(a["sentiment"].split(".")[-1].lower(), ""))
        st.markdown(f'<div class="stat-card"><div class="num">{pos}</div><div class="lbl">Positive</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="stat-card"><div class="num">{data["date"]}</div><div class="lbl">Date</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # Topic filter
    if topics:
        chosen_topics = st.multiselect(
            "Filter by topic", sorted(topics), default=sorted(topics),
            help="Uncheck to hide a topic"
        )
    else:
        chosen_topics = []

    filtered = [a for a in arts if not topics or a["topic"].split(".")[-1] in chosen_topics]

    if not filtered:
        st.warning("No articles match the selected topics.")
    else:
        st.markdown(f"### Showing {len(filtered)} article{'s' if len(filtered) != 1 else ''}")
        for i, art in enumerate(filtered):
            _render_article(art, i)

    with st.expander("📄 Raw Markdown"):
        st.code(data["raw"], language="markdown")

# ── LIVE MODE ────────────────────────────────────────────────────────────────

else:
    st.info(
        "**Live mode** runs the full pipeline: fetch → dedup → AI label → digest.\n\n"
        "Requires: PostgreSQL running + API keys in `.env`.\n\n"
        "This may take 30–120 seconds depending on the number of articles."
    )

    if "run_btn" in dir() and run_btn:
        with st.spinner(f"Running pipeline for **{username}**…"):
            try:
                import asyncio
                from src.config import get_settings, configure_logging
                from src.services.fetch_service import FetchService
                from src.concurrency.pipeline import run_pipeline
                from src.storage.repository import PostgresUserRepository
                import asyncpg

                configure_logging()

                async def _run():
                    conn = await asyncpg.connect(get_settings().database_url)
                    repo = PostgresUserRepository(conn)
                    await repo.initialize_db()
                    user = await repo.get_user_profile(username)
                    await conn.close()
                    fetch_svc = FetchService(get_settings())
                    return await run_pipeline(user, fetch_svc)

                digest_path = asyncio.run(_run())
                st.success(f"✅ Digest written to `{digest_path}`")

                # Show the result immediately
                result_data = _parse_digest(Path(digest_path))
                for art in result_data["articles"]:
                    _render_article(art, 0)

            except Exception as exc:
                st.error(f"Pipeline failed: {exc}")
                st.markdown(
                    "_Check that PostgreSQL is running and `.env` has valid API keys._"
                )
    else:
        st.markdown("👈 Enter a username and click **Run Pipeline** in the sidebar.")

        # Show most recent digest as preview
        recent = _list_digests()
        if recent:
            st.markdown("---")
            st.markdown("#### Most recent digest (preview)")
            prev = _parse_digest(recent[0])
            for art in prev["articles"][:3]:
                _render_article(art, 0)
            if len(prev["articles"]) > 3:
                st.caption(f"… and {len(prev['articles']) - 3} more articles")
