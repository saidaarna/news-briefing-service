from pydantic import BaseModel
from typing import List, Optional

class Article(BaseModel):
    title: str
    url: str
    content: str
    source_name: str
    content_hash: Optional[str] = None

class UserProfile(BaseModel):
    username: str
    preferred_topics: List[str]
    excluded_sources: List[str]