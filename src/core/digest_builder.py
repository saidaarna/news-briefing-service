import os
import logging
from datetime import datetime
from src.models import UserProfile, ProcessedArticle

logger = logging.getLogger(__name__)


class DigestBuilder:
    """Service responsible for filtering processed articles and generating personalized Markdown digests."""

    def create_markdown(self, processed: list[ProcessedArticle], user_profile: UserProfile) -> str:
        """
        Takes AI-processed articles, filters them according to user preferences,
        generates a personalized news briefing in Markdown format, and saves it to disk.
        """
        filtered_articles = []
        topic_counts = {}

        # Get user specific configurations
        max_items = getattr(user_profile, "max_items_per_topic", 5)

        for p in processed:
            # 1. Filter: Check if the source is excluded by the user
            if p.article.source in user_profile.excluded_sources:
                logger.info(f"Article '{p.article.title}' skipped. Source '{p.article.source}' is excluded.")
                continue

            # 2. Filter: Check if the article topic matches user's preferred topics (Topic Enum).
            # An empty preferred_topics list means "no filter — accept all topics" (consistent with filter.py).
            if user_profile.preferred_topics and p.labeled.topic not in user_profile.preferred_topics:
                logger.info(f"Article '{p.article.title}' skipped. Topic '{p.labeled.topic}' is not preferred.")
                continue

            # 3. Optimization: Enforce max items per topic constraint
            current_topic = p.labeled.topic
            topic_counts[current_topic] = topic_counts.get(current_topic, 0) + 1
            if topic_counts[current_topic] > max_items:
                logger.debug(f"Article '{p.article.title}' skipped. Topic '{current_topic}' limit reached.")
                continue

            filtered_articles.append(p)

        # Get current date for the header and filename
        date_str = datetime.now().strftime("%Y-%m-%d")

        # Build markdown content efficiently using list matching
        markdown_lines = [
            f"# Daily News Briefing - {date_str}",
            f"User: {user_profile.username}\n"
        ]

        if not filtered_articles:
            markdown_lines.append("*No articles available matching your profile preferences for today.*")
        else:
            for p in filtered_articles:
                markdown_lines.append(f"## {p.article.title}")
                markdown_lines.append(f"- **Source:** {p.article.source}")
                markdown_lines.append(f"- **Topic:** {p.labeled.topic} | **Sentiment:** {p.labeled.sentiment}")
                markdown_lines.append(f"- **Summary:** {p.labeled.summary}")
                markdown_lines.append(f"- [Read Original Article]({p.article.url})\n")

        content = "\n".join(markdown_lines)

        # Safe file I/O operations to persist the generated digest
        try:
            os.makedirs("digests", exist_ok=True)
            filename = f"digests/{date_str}-{user_profile.username}.md"

            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(f"Digest successfully created at {filename}")
            return filename
        except IOError as e:
            logger.error(f"Failed to write markdown digest file: {str(e)}")
            raise e