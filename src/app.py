"""
Web UI for the AI News Briefing Service — AIngels Team.

Run via:
    streamlit run src/app.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import streamlit as st

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AIngels · News Briefing",
    page_icon="🌸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS — AIngels feminine palette ────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Nunito:wght@300;400;600&display=swap');

/* Global */
html, body, [class*="css"] {
    font-family: 'Nunito', sans-serif;
}

/* Background */
.stApp {
    background: linear-gradient(135deg, #1a0a1e 0%, #2d0e3f 40%, #1e0a2e 100%);
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #2d0e3f 0%, #1a0a1e 100%);
    border-right: 1px solid rgba(255,182,193,0.15);
}
[data-testid="stSidebar"] * { color: #f8d7e3 !important; }
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] .stTextInput label { color: #f8b4d0 !important; }

/* Sidebar radio active */
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #f8d7e3 !important;
}

/* Header */
.aingels-header {
    text-align: center;
    padding: 1.5rem 0 0.5rem 0;
}
.aingels-title {
    font-family: 'Playfair Display', serif;
    font-size: 2.8rem;
    font-weight: 700;
    background: linear-gradient(135deg, #ff9ec4, #d4a8f5, #ffb3d9, #f9c8e0);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: 2px;
}
.aingels-sub {
    font-size: 0.95rem;
    color: #d4a8f5;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-top: -6px;
}
.aingels-divider {
    height: 2px;
    background: linear-gradient(90deg, transparent, #ff9ec4, #d4a8f5, #ff9ec4, transparent);
    border: none;
    margin: 0.8rem auto;
    width: 60%;
}

/* Stat cards */
.stat-row { display: flex; gap: 1rem; margin: 1.2rem 0; }
.stat-card {
    flex: 1;
    background: linear-gradient(135deg, rgba(255,158,196,0.08), rgba(212,168,245,0.12));
    border: 1px solid rgba(255,158,196,0.25);
    border-radius: 16px;
    padding: 1rem;
    text-align: center;
    backdrop-filter: blur(10px);
}
.stat-card .num {
    font-family: 'Playfair Display', serif;
    font-size: 2rem;
    font-weight: 700;
    color: #ff9ec4;
}
.stat-card .lbl {
    font-size: 0.75rem;
    color: #c490d1;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-top: 2px;
}

/* Article cards */
.article-card {
    background: linear-gradient(135deg, rgba(255,158,196,0.06), rgba(212,168,245,0.08));
    border: 1px solid rgba(255,158,196,0.2);
    border-left: 4px solid #ff9ec4;
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
    margin-bottom: 0.9rem;
    transition: all 0.2s ease;
}
.article-card:hover {
    border-left-color: #d4a8f5;
    background: linear-gradient(135deg, rgba(255,158,196,0.10), rgba(212,168,245,0.14));
}
.article-card h3 {
    font-family: 'Playfair Display', serif;
    margin: 0 0 0.5rem 0;
    color: #f8e1f0;
    font-size: 1.05rem;
    font-weight: 600;
}
.article-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-bottom: 0.6rem; }
.tag {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.5px;
}
.tag-topic  { background: rgba(212,168,245,0.2); color: #d4a8f5; border: 1px solid rgba(212,168,245,0.3); }
.tag-pos    { background: rgba(255,182,193,0.2); color: #ffb3c6; border: 1px solid rgba(255,182,193,0.3); }
.tag-neg    { background: rgba(200,100,150,0.2); color: #e89ab5; border: 1px solid rgba(200,100,150,0.3); }
.tag-neutral{ background: rgba(180,150,200,0.2); color: #c8a8d8; border: 1px solid rgba(180,150,200,0.3); }
.article-source { font-size: 0.78rem; color: #c490d1; }
.article-summary { color: #e8d0f0; font-size: 0.9rem; line-height: 1.6; margin: 0.5rem 0; }
.article-link a { font-size: 0.8rem; color: #ff9ec4; text-decoration: none; }
.article-link a:hover { color: #d4a8f5; }

/* Filter section */
.filter-label {
    font-family: 'Playfair Display', serif;
    color: #f8b4d0;
    font-size: 1rem;
    margin-bottom: 0.4rem;
}

/* Run button */
.stButton > button {
    background: linear-gradient(135deg, #c05085, #9040c0) !important;
    color: white !important;
    border: none !important;
    border-radius: 25px !important;
    font-family: 'Nunito', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: 1px !important;
    padding: 0.5rem 1.5rem !important;
    transition: all 0.3s ease !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #d06090, #a050d0) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(192,80,133,0.4) !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #1a0a1e; }
::-webkit-scrollbar-thumb { background: rgba(255,158,196,0.3); border-radius: 3px; }

/* Info/warning boxes */
.stInfo, .stWarning { border-radius: 12px !important; }

/* Expander */
.streamlit-expanderHeader { color: #f8b4d0 !important; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

DIGESTS_DIR = Path("digests")
SENTIMENT_CLASS = {
    "positive": "pos", "negative": "neg", "neutral": "neutral",
    "POSITIVE": "pos", "NEGATIVE": "neg", "NEUTRAL": "neutral",
}
SENTIMENT_EMOJI = {"pos": "🌸", "neg": "🥀", "neutral": "🌷"}


def _list_digests() -> list[Path]:
    if not DIGESTS_DIR.exists():
        return []
    return sorted(DIGESTS_DIR.glob("*.md"), reverse=True)


def _parse_digest(path: Path) -> dict:
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

    date_str, user = "", ""
    for line in lines[:5]:
        if line.startswith("# Daily News Briefing"):
            m = re.search(r"\d{4}-\d{2}-\d{2}", line)
            date_str = m.group(0) if m else ""
        if line.startswith("User:"):
            user = line.replace("User:", "").strip()

    return {"date": date_str, "user": user, "articles": articles, "raw": text}


def _render_article(art: dict) -> None:
    topic = art["topic"].split(".")[-1] if "." in art["topic"] else art["topic"]
    sentiment_raw = art["sentiment"].split(".")[-1].lower() if "." in art["sentiment"] else art["sentiment"].lower()
    sent_class = SENTIMENT_CLASS.get(sentiment_raw, "neutral")
    sent_emoji = SENTIMENT_EMOJI.get(sent_class, "🌷")

    link_html = (
        f'<div class="article-link"><a href="{art["url"]}" target="_blank">✦ Read full story</a></div>'
        if art["url"] else ""
    )

    st.markdown(f"""
<div class="article-card">
  <h3>{art['title']}</h3>
  <div class="article-meta">
    <span class="tag tag-topic">✦ {topic}</span>
    <span class="tag tag-{sent_class}">{sent_emoji} {sentiment_raw}</span>
    <span class="article-source">· {art['source']}</span>
  </div>
  <div class="article-summary">{art['summary']}</div>
  {link_html}
</div>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
<div style="text-align:center; padding: 1rem 0 0.5rem 0;">
  <div style="font-size:2.5rem;">🌸</div>
  <div style="font-family:'Georgia',serif; font-size:1.5rem; font-weight:700;
    background:linear-gradient(135deg,#ff9ec4,#d4a8f5);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    background-clip:text; letter-spacing:2px;">AIngels</div>
  <div style="font-size:0.65rem; color:#c490d1; letter-spacing:3px; margin-top:-2px;">
    NEWS BRIEFING SERVICE
  </div>
</div>
<hr style="border:none; height:1px; background:linear-gradient(90deg,transparent,rgba(255,158,196,0.3),transparent); margin:0.5rem 0;">
""", unsafe_allow_html=True)

    mode = st.radio("✨ Mode", ["📖 View Digest", "🚀 Generate New"])

    st.markdown("<hr style='border:none; height:1px; background:rgba(255,158,196,0.15); margin:0.5rem 0;'>",
                unsafe_allow_html=True)

    if mode == "📖 View Digest":
        digests = _list_digests()
        if not digests:
            st.warning("No digests yet.")
            selected_path = None
        else:
            labels = [p.name for p in digests]
            chosen = st.selectbox("🌷 Select digest", labels)
            selected_path = DIGESTS_DIR / chosen
    else:
        st.markdown("<div style='color:#f8b4d0; font-size:0.85rem; margin-bottom:4px;'>👤 Team member</div>",
                    unsafe_allow_html=True)
        username = st.text_input("", value="saida", label_visibility="collapsed",
                                 placeholder="saida / laman / nazrin / nigar")
        run_btn = st.button("🌸 Generate Digest", use_container_width=True)

    st.markdown("""
<hr style='border:none; height:1px; background:rgba(255,158,196,0.15); margin:0.8rem 0;'>
<div style='text-align:center;'>
  <div style='font-size:0.65rem; color:#9060a0; letter-spacing:2px; text-transform:uppercase;'>
    AI Academy · Spring 2026
  </div>
  <div style='font-size:0.75rem; color:#c490d1; margin-top:4px;'>
    🌸 saida · laman · nigar · nazrin
  </div>
</div>
""", unsafe_allow_html=True)


# ── Main area ─────────────────────────────────────────────────────────────────

# Header
st.markdown("""
<div class="aingels-header">
  <div class="aingels-title">✦ AIngels ✦</div>
  <div class="aingels-sub">AI News Briefing Service</div>
  <hr class="aingels-divider">
</div>
""", unsafe_allow_html=True)


# ── VIEW MODE ────────────────────────────────────────────────────────────────

if mode == "📖 View Digest":
    if not _list_digests():
        st.info("🌸 No digests yet. Switch to **Generate New** or run `python -m src run-daily --user saida --no-db` first.")
        st.stop()

    data = _parse_digest(selected_path)
    arts = data["articles"]
    topics = sorted({a["topic"].split(".")[-1] for a in arts if a["topic"]})

    # Stats
    pos_count = sum(1 for a in arts if SENTIMENT_CLASS.get(
        a["sentiment"].split(".")[-1].lower(), "") == "pos")
    tech_count = sum(1 for a in arts if "TECH" in a["topic"].upper())

    col1, col2, col3, col4 = st.columns(4)
    for col, num, label in [
        (col1, str(len(arts)), "Articles"),
        (col2, str(len(topics)), "Topics"),
        (col3, str(pos_count), "Positive 🌸"),
        (col4, data["date"] or "Today", "Date"),
    ]:
        with col:
            st.markdown(f"""
<div class="stat-card">
  <div class="num">{num}</div>
  <div class="lbl">{label}</div>
</div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Topic filter
    if topics:
        chosen_topics = st.multiselect(
            "🌷 Filter by topic",
            topics, default=topics,
        )
    else:
        chosen_topics = []

    filtered = [a for a in arts if not topics or a["topic"].split(".")[-1] in chosen_topics]

    if not filtered:
        st.warning("🥀 No articles match the selected topics.")
    else:
        st.markdown(
            f"<div style='color:#c490d1; font-size:0.85rem; margin-bottom:0.8rem;'>"
            f"✦ Showing {len(filtered)} article{'s' if len(filtered) != 1 else ''}"
            f" for <b style='color:#ff9ec4;'>{data['user'] or 'user'}</b></div>",
            unsafe_allow_html=True
        )
        for art in filtered:
            _render_article(art)

    with st.expander("📜 Raw Markdown"):
        st.code(data["raw"], language="markdown")


# ── GENERATE MODE ─────────────────────────────────────────────────────────────

else:
    st.markdown("""
<div style='background:linear-gradient(135deg,rgba(255,158,196,0.06),rgba(212,168,245,0.08));
  border:1px solid rgba(255,158,196,0.2); border-radius:14px; padding:1.2rem 1.5rem; margin-bottom:1.2rem;'>
  <div style='font-family:Georgia,serif; color:#f8b4d0; font-size:1.1rem; margin-bottom:0.5rem;'>
    🌸 Live Pipeline Mode
  </div>
  <div style='color:#c8a8d8; font-size:0.88rem; line-height:1.7;'>
    Fetches real news → deduplicates → AI labels → generates your digest.<br>
    Requires API keys in <code style='color:#ff9ec4;'>.env</code>.
    No database needed — profiles load from <code style='color:#ff9ec4;'>data/user_profile.json</code>.
  </div>
</div>
""", unsafe_allow_html=True)

    if "run_btn" in dir() and run_btn:
        with st.spinner(f"🌸 Generating digest for **{username}**… this takes 1-2 minutes"):
            try:
                import asyncio
                from src.config import get_settings, configure_logging
                from src.services.fetch_service import FetchService
                from src.concurrency.pipeline import run_pipeline

                configure_logging()

                async def _run():
                    import json as _json
                    from pathlib import Path as _Path
                    from ai.schemas import Topic

                    user = None

                    # Try DB first, fall back to JSON
                    try:
                        import asyncpg
                        from src.storage.repository import PostgresUserRepository
                        conn = await asyncpg.connect(get_settings().database_url)
                        repo = PostgresUserRepository(conn)
                        await repo.initialize_db()
                        user = await repo.get_user_profile(username)
                        await conn.close()
                    except Exception as db_err:
                        st.info(f"ℹ️ DB unavailable — loading profile from JSON")
                        profile_path = _Path("data/user_profile.json")
                        if profile_path.exists():
                            profiles = _json.loads(profile_path.read_text(encoding="utf-8"))
                            match = next((p for p in profiles if p["username"] == username), None)
                            if match is None:
                                match = {"username": username, "preferred_topics": [], "excluded_sources": []}
                            from src.models import UserProfile
                            user = UserProfile(
                                username=match["username"],
                                preferred_topics=[Topic(t) for t in match.get("preferred_topics", [])],
                                excluded_sources=match.get("excluded_sources", []),
                                max_items_per_topic=match.get("max_items_per_topic", 5),
                            )
                        else:
                            raise RuntimeError("data/user_profile.json not found.")

                    fetch_svc = FetchService(get_settings())
                    return await run_pipeline(user, fetch_svc)

                digest_path = asyncio.run(_run())

                st.success(f"✅ Digest ready: `{digest_path}`")
                result_data = _parse_digest(Path(digest_path))
                st.markdown(
                    f"<div style='color:#c490d1; margin-bottom:0.8rem;'>"
                    f"✦ {len(result_data['articles'])} articles in your briefing</div>",
                    unsafe_allow_html=True
                )
                for art in result_data["articles"]:
                    _render_article(art)

            except Exception as exc:
                st.error(f"🥀 Pipeline failed: {exc}")
                st.caption("Check that your `.env` has valid API keys.")
    else:
        # Preview most recent
        recent = _list_digests()
        if recent:
            st.markdown(
                "<div style='font-family:Georgia,serif; color:#f8b4d0; font-size:1rem; margin-bottom:0.8rem;'>"
                "✦ Most recent digest (preview)</div>",
                unsafe_allow_html=True
            )
            prev = _parse_digest(recent[0])
            for art in prev["articles"][:4]:
                _render_article(art)
            if len(prev["articles"]) > 4:
                st.markdown(
                    f"<div style='color:#9060a0; font-size:0.8rem; text-align:center; margin-top:0.5rem;'>"
                    f"🌸 … and {len(prev['articles']) - 4} more articles</div>",
                    unsafe_allow_html=True
                )
        else:
            st.markdown("""
<div style='text-align:center; padding: 3rem 0; color:#9060a0;'>
  <div style='font-size:3rem;'>🌸</div>
  <div style='font-family:Georgia,serif; font-size:1.2rem; color:#c490d1; margin-top:1rem;'>
    No digests yet
  </div>
  <div style='font-size:0.85rem; margin-top:0.5rem;'>
    Enter your name and click Generate Digest ✦
  </div>
</div>
""", unsafe_allow_html=True)
