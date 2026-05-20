import logging
from collections import defaultdict

from ai import DigestItem

# ── Temporary User stub ───────────────────────────────────────────────────────
# TODO: Remove this class and replace with "from models import User"
#       once Ləman's models.py is merged. Confirm these exact field names
#       with her: preferred_topics, excluded_sources, max_items_per_topic, username.
from pydantic import BaseModel

class User(BaseModel):
    username: str
    preferred_topics: list[str]   # e.g. ["Tech", "Science"]  — match Topic.value strings
    excluded_sources: list[str]   # e.g. ["tabloid_news"]
    max_items_per_topic: int      # e.g. 3
# ─────────────────────────────────────────────────────────────────────────────

log = logging.getLogger(__name__)


def apply_user_preferences(
    items: list[DigestItem], user: User
) -> list[DigestItem]:
    """Filter digest items down to what this user actually wants to read.

    Three rules applied in order for each item:
      1. Drop it if its source is in user.excluded_sources
      2. Drop it if user has preferred_topics set and this item's topic is not in it
      3. Drop it if we have already hit user.max_items_per_topic for this topic

    Args:
        items: list of DigestItem from the AI labeling stage
        user:  user profile with their preferences

    Returns:
        Filtered list of DigestItem
    """
    out: list[DigestItem] = []
    by_topic: dict[str, int] = defaultdict(int)  # tracks how many items per topic

    # Build lowercase sets for fast O(1) lookup
    excluded = {s.lower() for s in user.excluded_sources}

    # If preferred_topics is an empty list → no topic filter, keep all topics
    # If it has entries → only keep items whose topic is in the list
    preferred = (
        {t.lower() for t in user.preferred_topics}
        if user.preferred_topics
        else None
    )

    for item in items:
        # Rule 1: skip excluded sources
        # item.article.source is the source name (e.g. "BBC", "TechCrunch")
        if item.article.source.lower() in excluded:
            continue

        # Rule 2: skip topics not in preferred list (only if list is set)
        # item.labeled.topic is a Topic enum, .value gives the string e.g. "Tech"
        if preferred is not None and item.labeled.topic.value.lower() not in preferred:
            continue

        # Rule 3: skip if we've hit the cap for this topic
        topic_key = item.labeled.topic.value  # e.g. "Tech"
        if by_topic[topic_key] >= user.max_items_per_topic:
            continue

        by_topic[topic_key] += 1
        out.append(item)

    log.info(
        "filter user=%s in=%d out=%d topics=%s",
        user.username,
        len(items),
        len(out),
        dict(by_topic),
    )
    return out