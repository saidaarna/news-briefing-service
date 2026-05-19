import os
import logging
from datetime import datetime
from src.models import UserProfile

logger = logging.getLogger(__name__)


class DigestBuilder:
    def create_markdown(self, articles: list, user_profile: UserProfile) -> str:
        filtered_articles = []
        for art in articles:
            if art.source_name in user_profile.excluded_sources:
                logger.info(f"Article '{art.title}' skipped. Source '{art.source_name}' is excluded.")
                continue
            filtered_articles.append(art)

        date_str = datetime.now().strftime("%Y-%m-%d")
        content = f"# Daily News Briefing - {date_str}\n"
        content += f"User: {user_profile.username}\n\n"

        if not filtered_articles:
            content += "*No articles available matching your profile preferences for today.*\n"
        else:
            for art in filtered_articles:
                content += f"## {art.title}\n"
                content += f"- **Source:** {art.source_name}\n"
                content += f"- **Summary:** {art.content}\n"
                content += f"- [Read Original Article]({art.url})\n\n"

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